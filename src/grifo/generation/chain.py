"""Chain LCEL: pergunta -> retrieval -> prompt -> LLM -> resposta + fontes.

Requisitos: FR-30 (chain fim a fim), FR-31 (citação garantida pós-geração), FR-32
(recusa exata), FR-33 (timestamp na fonte), FR-36 (contagem de tokens).

Use LCEL, nao as chains legadas do LangChain. Instrumente a contagem de tokens desde a
primeira versao (NFR-2) -- e o numero que vai no post e no EVALUATION.md secao 6.

Quando o retriever devolve vazio (FR-24), a chain nao chama o LLM: responde
REFUSAL_MESSAGE direto, com found=False, sources=[] e tokens zerados (mas presentes).

`retriever` e `llm` são injetáveis: é assim que os testes unitários exercitam a chain
sem tocar na OpenAI.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable

from langchain_core.runnables import Runnable, RunnableBranch, RunnableLambda
from pydantic import SecretStr

from grifo.config import REFUSAL_MESSAGE, settings
from grifo.generation.prompts import ANSWER_SYSTEM_PROMPT, format_context
from grifo.retrieval.hybrid import retrieve
from grifo.retrieval.rerank import rerank

#: Citação bem formada `[Módulo X, Aula Y]` — a garantia executável do FR-31.
_CITACAO_RE = re.compile(r"\[Módulo [^\],]+, Aula [^\],]+\]")


def _default_llm() -> Runnable:
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        api_key=SecretStr(settings.openai_api_key) if settings.openai_api_key else None,
        base_url=settings.openai_base_url or None,
    )


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
        "chunks": state.get("chunks", []),
    }


def _sources(chunks: list[dict]) -> list[dict]:
    return [
        {
            "modulo": c["metadata"]["modulo"],
            "aula": c["metadata"]["aula"],
            "timestamp": c["metadata"].get("timestamp_inicio"),
            "score": round(float(c["score"]), 4),
        }
        for c in chunks
    ]


def _ensure_citation(answer_text: str, chunks: list[dict]) -> str:
    """FR-31 como invariante: se o LLM omitiu a citação, anexa a do melhor chunk."""
    if _CITACAO_RE.search(answer_text):
        return answer_text
    top = chunks[0]["metadata"]
    return f"{answer_text.rstrip()} [Módulo {top['modulo']}, Aula {top['aula']}]"


def _normalizar(texto: str) -> str:
    return " ".join(texto.split()).casefold()


_REFUSAL_NORM = _normalizar(REFUSAL_MESSAGE)


def _is_refusal(answer_text: str) -> bool:
    """O próprio LLM também recusa (ADR 002), e essa recusa precisa virar found=False.

    O SCORE_THRESHOLD só pega o caso "nada relevante veio". Este pega o caso
    "vieram chunks parecidos, mas nenhum responde a pergunta" — que o modelo enxerga
    melhor que o cosseno. Sem isso a recusa do modelo sai como found=True com uma
    citação anexada à força, violando o DC-2 e derrubando a taxa de recusa correta.
    """
    return _normalizar(answer_text).startswith(_REFUSAL_NORM)


def _generate(state: dict, llm: Runnable) -> dict:
    prompt = ANSWER_SYSTEM_PROMPT.format(
        curso=state["curso"],
        max_words=settings.max_answer_words,
        context=format_context(state["chunks"]),
        question=state["question"],
    )
    msg = llm.invoke(prompt)
    usage = getattr(msg, "usage_metadata", None) or {}
    tokens = {
        "input": int(usage.get("input_tokens", 0)),
        "output": int(usage.get("output_tokens", 0)),
    }
    conteudo = str(msg.content)
    if _is_refusal(conteudo):
        # Os tokens foram gastos e continuam contando (FR-36), mas o contrato de
        # recusa do DC-2 vale: string exata, sem fontes, sem citação anexada.
        return {
            "answer": REFUSAL_MESSAGE,
            "sources": [],
            "found": False,
            "contexts": [],
            "tokens": tokens,
        }
    return {
        "answer": _ensure_citation(conteudo, state["chunks"]),
        "sources": _sources(state["chunks"]),
        "found": True,
        "contexts": _contexts(state["chunks"]),
        "tokens": tokens,
    }


def build_chain(
    retriever: Callable[..., dict] | None = None, llm: Runnable | None = None
) -> Runnable:
    """Monta a chain LCEL: retriever -> branch (vazio ? recusa : geração)."""
    retriever_fn: Callable[..., dict] = retriever or _retrieve_state
    llm = llm or _default_llm()

    def sem_contexto(state: dict) -> bool:
        return not state.get("chunks")

    return RunnableLambda(retriever_fn) | RunnableBranch(
        (sem_contexto, RunnableLambda(_refusal)),
        RunnableLambda(lambda state: _generate(state, llm)),
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
        # Fora do DC-2: so a avaliacao usa. AskResponse ignora chaves extras.
        "contexts": resultado.get("contexts", []),
    }
