"""Chain LCEL: pergunta -> retrieval -> prompt -> LLM estruturado -> resposta + fontes.

Requisitos: FR-30 (chain fim a fim), FR-31 (citação garantida pós-geração), FR-32
(recusa exata), FR-33 (timestamp na fonte), FR-36 (contagem de tokens).

Use LCEL, nao as chains legadas do LangChain. Instrumente a contagem de tokens desde a
primeira versao (NFR-2) -- e o numero que vai no post e no EVALUATION.md secao 6.

Quando o retriever devolve vazio (FR-24), a chain nao chama o LLM: responde
REFUSAL_MESSAGE direto, com found=False, sources=[] e tokens zerados (mas presentes).

Desde a Fase 2 do plano de execução, a saída do LLM é um contrato Pydantic
(`GrifoAnswer`) via instructor, com max_retries=2: validação violada devolve o erro
ao modelo em vez de a chain consertar a saída por regex. O `_ensure_citation` do
FR-31 fica no código, atrás de `FORCE_CITATION` (default false) — mesmo padrão do
reranker: mecanismo medido que ficou explicitamente desligado.

`retriever` e `structured` são injetáveis: é assim que os testes unitários exercitam
a chain sem tocar na OpenAI.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from functools import lru_cache
from typing import Any

from langchain_core.runnables import Runnable, RunnableBranch, RunnableLambda

from grifo.config import REFUSAL_MESSAGE, settings
from grifo.generation.prompts import ANSWER_SYSTEM_PROMPT, format_context
from grifo.generation.schemas import GrifoAnswer, SourceRef, _numero, pares_recuperados
from grifo.retrieval.hybrid import retrieve
from grifo.retrieval.rerank import rerank

#: Citação bem formada `[Módulo X, Aula Y]` — a garantia executável do FR-31.
#: Só é usada pelo `_ensure_citation`, que está atrás de FORCE_CITATION.
_CITACAO_RE = re.compile(r"\[Módulo [^\],]+, Aula [^\],]+\]")

#: O seam estruturado: recebe o prompt formatado, devolve o contrato validado, os
#: tokens gastos (todas as tentativas) e quantas re-tentativas de validação foram
#: necessárias. É injetável para os testes unitários.
StructuredLLM = Callable[[str], tuple[GrifoAnswer, dict[str, int], int]]


@lru_cache(maxsize=1)
def _openai_client() -> Any:
    """Cliente HTTP da OpenAI, reaproveitado entre perguntas.

    O que se cacheia aqui é o pool de conexões do httpx. `answer()` chama
    `build_chain()` a cada pergunta, e um cliente novo por pergunta significa
    handshake TLS novo por pergunta — custo no caminho do aluno que não tem nada a
    ver com o modelo. Mesmo padrão do `_client()` e do `_embedder()` do
    `vector_store`, e com a mesma ressalva: trocar `settings` em runtime exige
    `_openai_client.cache_clear()` (é o que os testes fazem).

    O cliente é compartilhado, os hooks NÃO — ver `_default_structured`.
    """
    from openai import OpenAI

    return OpenAI(
        api_key=settings.openai_api_key or "nao-configurado",
        base_url=settings.openai_base_url or None,
    )


def _default_structured() -> StructuredLLM:
    """Cliente instructor sobre a API OpenAI-compatível das settings.

    `max_retries=2` é o retry INSTRUÍDO: validação Pydantic violada devolve a
    mensagem de erro ao modelo, que corrige a própria saída. Os hooks contam os
    erros de validação (para o `retry_rate` do eval) e somam os tokens de TODAS as
    tentativas — tentativa de correção também é gasto (FR-36).

    Os hooks e o `estado` que eles alimentam nascem AQUI, uma vez por pergunta, e
    não são cacheados junto com o cliente HTTP. É deliberado: o `/ask` do FastAPI é
    `def` síncrono e roda em threadpool, então duas perguntas simultâneas
    compartilhariam o contador e trocariam tokens e retries entre si. Barato de
    construir, e `instructor.from_openai` não muta o cliente que recebe.
    """
    import instructor
    from instructor.core.hooks import HookName, Hooks

    hooks = Hooks()
    estado = {"erros_validacao": 0, "tokens_input": 0, "tokens_output": 0}

    def _erro_de_validacao(error: Exception, **_kwargs) -> None:
        estado["erros_validacao"] += 1

    def _uso_da_tentativa(response) -> None:
        usage = getattr(response, "usage", None)
        if usage is not None:
            estado["tokens_input"] += int(getattr(usage, "prompt_tokens", 0) or 0)
            estado["tokens_output"] += int(getattr(usage, "completion_tokens", 0) or 0)

    hooks.on(HookName.PARSE_ERROR, _erro_de_validacao)
    hooks.on(HookName.COMPLETION_RESPONSE, _uso_da_tentativa)

    # `tools` é o da série; `json_schema` é o que o LM Studio aceita — ver config.
    modo = {"tools": instructor.Mode.TOOLS, "json_schema": instructor.Mode.JSON_SCHEMA}
    client = instructor.from_openai(
        _openai_client(), hooks=hooks, mode=modo[settings.llm_structured_mode]
    )

    class _InstructorLLM:
        """Chamável que carrega o client — exposto para inspeção e teste de config."""

        def __init__(self) -> None:
            self.client = client

        def __call__(self, prompt: str) -> tuple[GrifoAnswer, dict[str, int], int]:
            estado.update(erros_validacao=0, tokens_input=0, tokens_output=0)
            # max_retries é POR CHAMADA: no cliente ele colide com o max_retries
            # de transporte do SDK OpenAI dentro do handle_kwargs do instructor.
            resposta, _completamento = client.chat.completions.create_with_completion(
                model=settings.llm_model,
                temperature=settings.llm_temperature,
                messages=[{"role": "user", "content": prompt}],
                response_model=GrifoAnswer,
                max_retries=2,
            )
            tokens = {
                "input": estado["tokens_input"],
                "output": estado["tokens_output"],
            }
            return resposta, tokens, estado["erros_validacao"]

    return _InstructorLLM()


def _retrieve_state(state: dict) -> dict:
    """Passo de retrieval da chain: retrieve_k candidatos -> rerank -> final_k.

    Recebe o dict de estado, não argumentos soltos: `RunnableLambda` invoca a função
    com UM argumento (a entrada da chain). Assinatura de dois parâmetros aqui derruba
    todo o caminho de produção com TypeError.
    """
    question, curso = state["question"], state["curso"]
    chunks = retrieve(question, settings.retrieve_k, filters={"curso": curso})
    return {
        "question": question,
        "curso": curso,
        "chunks": rerank(question, chunks, settings.final_k),
    }


def _contexts(chunks: list[dict]) -> list[str]:
    """Texto dos chunks que fundamentaram a resposta.

    A avaliação precisa do TEXTO, não das etiquetas de citação: faithfulness e taxa de
    alucinação se medem confrontando a resposta com o que foi realmente recuperado.
    Não faz parte do DC-2 — `AskResponse` ignora esta chave.
    """
    return [c["text"] for c in chunks]


def _refusal(state: dict) -> dict:
    return {
        "answer": REFUSAL_MESSAGE,
        "sources": [],
        "found": False,
        "contexts": [],
        "retries": 0,
        "chunks": state.get("chunks", []),
    }


def _sources(chunks: list[dict], citations: list[SourceRef] | None = None) -> list[dict]:
    """Os chunks que foram ao prompt, marcando quais o modelo de fato CITOU.

    `sources` continua sendo tudo o que fundamentou a resposta — a semântica do DC-2
    não muda, e a série temporal segue comparável. O que entra é o `cited`: desde o
    contrato da Fase 2 o modelo devolve `citations` validadas contra os trechos
    recuperados, e esse dado estava sendo descartado. Com ele dá para separar "a aula
    certa estava entre as recuperadas" de "o modelo citou a aula certa", que é a
    pergunta mais dura e a que o `fonte_correta_em_respondidas` não responde.

    Sem `citations` (recusa, ou chamada antiga) nada é marcado como citado.
    """
    citadas = {(_numero(c.modulo), _numero(c.aula)) for c in citations or []}
    return [
        {
            "modulo": c["metadata"]["modulo"],
            "aula": c["metadata"]["aula"],
            "timestamp": c["metadata"].get("timestamp_inicio"),
            "score": round(float(c["score"]), 4),
            "cited": (_numero(c["metadata"]["modulo"]), _numero(c["metadata"]["aula"])) in citadas,
        }
        for c in chunks
    ]


def _ensure_citation(answer_text: str, chunks: list[dict]) -> str:
    """FR-31 como invariante: se o LLM omitiu a citação, anexa a do melhor chunk.

    Atrás de `FORCE_CITATION` desde a Fase 2: medido na rodada de 2026-08-24, este
    conserto cobria 9 de 44 respostas (20%) — citação atribuída à força é atribuir
    fonte a afirmação não fundamentada. Nunca mais é o mecanismo principal.
    """
    if _CITACAO_RE.search(answer_text):
        return answer_text
    top = chunks[0]["metadata"]
    return f"{answer_text.rstrip()} [Módulo {top['modulo']}, Aula {top['aula']}]"


def _generate(state: dict, structured: StructuredLLM) -> dict:
    prompt = ANSWER_SYSTEM_PROMPT.format(
        curso=state["curso"],
        max_words=settings.max_answer_words,
        context=format_context(state["chunks"]),
        question=state["question"],
    )
    # O validador de SourceRef consulta os pares módulo/aula desta query: citação
    # de aula não recuperada reprova o contrato e volta ao modelo como erro.
    with pares_recuperados(state["chunks"]):
        parsed, tokens, retries = structured(prompt)
    if not parsed.found:
        # O validador de GrifoAnswer garante que answer == REFUSAL_MESSAGE aqui.
        # Os tokens foram gastos e continuam contando (FR-36), mas o contrato de
        # recusa do DC-2 vale: string exata, sem fontes.
        return {
            "answer": REFUSAL_MESSAGE,
            "sources": [],
            "found": False,
            "contexts": [],
            "tokens": tokens,
            "retries": retries,
        }
    answer_text = parsed.answer
    if settings.force_citation:
        answer_text = _ensure_citation(answer_text, state["chunks"])
    return {
        "answer": answer_text,
        "sources": _sources(state["chunks"], parsed.citations),
        "found": True,
        "contexts": _contexts(state["chunks"]),
        "tokens": tokens,
        "retries": retries,
    }


def build_chain(
    retriever: Callable[..., dict] | None = None, structured: StructuredLLM | None = None
) -> Runnable:
    """Monta a chain LCEL: retriever -> branch (vazio ? recusa : geração)."""
    retriever_fn: Callable[..., dict] = retriever or _retrieve_state
    llm_estruturado: StructuredLLM = structured or _default_structured()

    def sem_contexto(state: dict) -> bool:
        return not state.get("chunks")

    return RunnableLambda(retriever_fn) | RunnableBranch(
        (sem_contexto, RunnableLambda(_refusal)),
        RunnableLambda(lambda state: _generate(state, llm_estruturado)),
    )


def answer(question: str, curso: str, session_id: str | None = None) -> dict:
    """Responde uma duvida. Retorno no formato DC-2."""
    inicio = time.perf_counter()
    resultado = build_chain().invoke({"question": question, "curso": curso})
    latency_ms = int((time.perf_counter() - inicio) * 1000)
    tokens: dict[str, int] = resultado.get("tokens") or {"input": 0, "output": 0}
    return {
        "answer": resultado["answer"],
        "sources": resultado.get("sources", []),
        "found": bool(resultado.get("found")),
        "latency_ms": latency_ms,
        "tokens": tokens,
        # Fora do DC-2: só a avaliação usa. AskResponse ignora chaves extras.
        "contexts": resultado.get("contexts", []),
        "retries": resultado.get("retries", 0),
    }
