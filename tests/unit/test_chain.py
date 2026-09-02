"""FR-30/31/32/33/36: chain LCEL com citação obrigatória, recusa exata e tokens."""

import re
from types import SimpleNamespace

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

import grifo.generation.chain as chain_mod
from grifo.config import REFUSAL_MESSAGE, settings
from grifo.generation.chain import answer, build_chain

CHUNKS = [
    {
        "id": "aula-04-cac-e-ltv:chunk0",
        "text": "O CAC é o custo total de aquisição dividido pelo número de clientes.",
        "score": 0.81,
        "metadata": {
            "curso": "Curso Exemplo",
            "modulo": "2 - Metricas",
            "aula": "4 - CAC e LTV",
            "timestamp_inicio": "00:22:14",
            "pagina": None,
        },
    }
]


def fake_llm(texto: str):
    return RunnableLambda(
        lambda _prompt: AIMessage(
            content=texto,
            usage_metadata={"input_tokens": 320, "output_tokens": 42, "total_tokens": 362},
        )
    )


def test_sem_contexto_recusa_exata_sem_chamar_llm():
    """FR-32: retriever vazio -> string exata, found=False, sources=[]."""
    chamado = SimpleNamespace(ok=False)
    llm = RunnableLambda(lambda p: (setattr(chamado, "ok", True), AIMessage("x"))[1])
    chain = build_chain(retriever=lambda s: {**s, "chunks": []}, llm=llm)
    out = chain.invoke({"question": "receita de bolo", "curso": "C"})
    assert out["answer"] == REFUSAL_MESSAGE
    assert out["found"] is False
    assert out["sources"] == []
    assert chamado.ok is False  # o LLM não é chamado quando não há contexto


def test_resposta_com_citacao_fontes_e_tokens():
    """FR-31, FR-33, FR-36."""
    texto = (
        "O CAC é o custo total dividido pelos clientes [Módulo 2 - Metricas, Aula 4 - CAC e LTV]."
    )
    chain = build_chain(
        retriever=lambda s: {**s, "chunks": CHUNKS},
        llm=fake_llm(texto),
    )
    out = chain.invoke({"question": "como calcular o CAC?", "curso": "C"})
    assert re.search(r"\[Módulo [^\]]+, Aula [^\]]+\]", out["answer"])
    assert out["found"] is True
    assert out["sources"][0]["timestamp"] == "00:22:14"  # FR-33
    assert out["sources"][0]["modulo"] == "2 - Metricas"
    assert out["tokens"] == {"input": 320, "output": 42}  # FR-36


def test_garantia_de_citacao_quando_llm_omite():
    """FR-31 como invariante: sem citação na saída do LLM, a chain anexa a do top chunk."""
    chain = build_chain(
        retriever=lambda s: {**s, "chunks": CHUNKS},
        llm=fake_llm("O CAC é custo dividido por clientes."),
    )
    out = chain.invoke({"question": "cac?", "curso": "C"})
    assert re.search(r"\[Módulo [^\]]+, Aula [^\]]+\]", out["answer"])


def test_prompt_do_llm_leva_limite_recusa_e_contexto():
    """FR-35: o limite de palavras e a regra de recusa viajam no prompt final."""
    visto: dict = {}

    def espia(prompt: str) -> AIMessage:
        visto["prompt"] = prompt
        return AIMessage(
            "ok", usage_metadata={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}
        )

    chain = build_chain(retriever=lambda s: {**s, "chunks": CHUNKS}, llm=RunnableLambda(espia))
    chain.invoke({"question": "como calcular o CAC?", "curso": "Curso Exemplo"})
    p = visto["prompt"]
    assert "200 palavras" in p
    assert REFUSAL_MESSAGE in p
    assert "custo total de aquisição" in p  # contexto formatado
    assert "como calcular o CAC?" in p
    assert "Timestamp: 00:22:14" in p  # FR-33: timestamp disponível ao modelo


def test_answer_empacota_dc2(monkeypatch):
    """FR-30: resposta no formato DC-2, com latência e tokens sempre presentes."""

    def fake_run(s):
        if s["question"] == "pergunta":
            return {
                "answer": "x [Módulo 2 - Metricas, Aula 4 - CAC e LTV]",
                "sources": [],
                "found": True,
                "tokens": {"input": 10, "output": 2},
            }
        return {"answer": REFUSAL_MESSAGE, "sources": [], "found": False}

    fake = RunnableLambda(fake_run)
    monkeypatch.setattr(chain_mod, "build_chain", lambda: fake)

    resp = answer("pergunta", "Curso Exemplo")
    assert {"answer", "sources", "found", "latency_ms", "tokens"} <= set(resp)
    assert resp["latency_ms"] >= 0
    assert resp["tokens"] == {"input": 10, "output": 2}

    resp_recusa = answer("outra", "Curso Exemplo", session_id="s1")
    assert resp_recusa["found"] is False
    assert resp_recusa["tokens"] == {"input": 0, "output": 0}  # presente e não nulo


def test_settings_plugados_na_chain():
    """A chain usa os parâmetros calibráveis, não números mágicos."""
    assert settings.final_k > 0 and settings.max_answer_words == 200


def test_caminho_default_sem_retriever_injetado(monkeypatch):
    """Regressao: build_chain() SEM retriever injetado precisa rodar.

    Todos os outros testes passam um retriever proprio, entao o default nunca era
    exercitado -- e ele estourava TypeError, derrubando /ask inteiro em producao.
    """
    visto: dict = {}

    def fake_retrieve(question, k, filters=None):
        visto["question"], visto["k"], visto["filters"] = question, k, filters
        return CHUNKS

    monkeypatch.setattr(chain_mod, "retrieve", fake_retrieve)
    monkeypatch.setattr(chain_mod, "rerank", lambda q, c, k: c[:k])

    chain = build_chain(llm=fake_llm("O CAC e custo por cliente."))
    out = chain.invoke({"question": "como calcular o CAC?", "curso": "Curso Exemplo"})

    assert out["found"] is True
    assert visto["question"] == "como calcular o CAC?"
    assert visto["filters"] == {"curso": "Curso Exemplo"}  # filtro por curso chega ao retriever
    assert visto["k"] == settings.retrieve_k


def test_answer_ponta_a_ponta_com_defaults(monkeypatch):
    """FR-30: answer() no caminho real (retriever default), so o LLM e falso."""
    monkeypatch.setattr(chain_mod, "retrieve", lambda q, k, filters=None: CHUNKS)
    monkeypatch.setattr(chain_mod, "rerank", lambda q, c, k: c[:k])
    monkeypatch.setattr(chain_mod, "_default_llm", lambda: fake_llm("Resposta fundamentada."))

    resp = answer("como calcular o CAC?", "Curso Exemplo")

    assert {"answer", "sources", "found", "latency_ms", "tokens"} <= set(resp)
    assert resp["found"] is True
    assert re.search(r"\[Módulo [^\]]+, Aula [^\]]+\]", resp["answer"])
    assert resp["sources"][0]["timestamp"] == "00:22:14"
    assert resp["tokens"] == {"input": 320, "output": 42}


def test_recusa_do_llm_vira_found_false():
    """ADR 002: o modelo tambem recusa, e a recusa dele obedece o contrato DC-2.

    Caso real: o threshold deixou chunks passarem (parecidos), mas nenhum responde.
    Antes isso saia como found=True com a citacao do top chunk colada na recusa.
    """
    chain = build_chain(
        retriever=lambda s: {**s, "chunks": CHUNKS},
        llm=fake_llm(REFUSAL_MESSAGE),
    )
    out = chain.invoke({"question": "qual a receita do bolo?", "curso": "C"})

    assert out["answer"] == REFUSAL_MESSAGE  # string exata, sem citacao anexada
    assert out["found"] is False
    assert out["sources"] == []
    assert out["tokens"] == {"input": 320, "output": 42}  # FR-36: tokens gastos contam


def test_recusa_do_llm_tolera_espaco_e_caixa():
    """A deteccao normaliza: o modelo raramente devolve a string byte a byte."""
    chain = build_chain(
        retriever=lambda s: {**s, "chunks": CHUNKS},
        llm=fake_llm("  não encontrei isso no material do curso.\n"),
    )
    assert chain.invoke({"question": "x", "curso": "C"})["found"] is False


def test_resposta_que_apenas_menciona_a_recusa_nao_e_recusa():
    """Guarda contra deteccao larga demais: mencionar a frase no meio nao e recusar."""
    texto = (
        "O material cobre isso sim. Se não cobrisse, eu diria que não encontrei "
        "isso no material do curso [Módulo 2 - Metricas, Aula 4 - CAC e LTV]."
    )
    chain = build_chain(retriever=lambda s: {**s, "chunks": CHUNKS}, llm=fake_llm(texto))
    assert chain.invoke({"question": "x", "curso": "C"})["found"] is True


def test_contexts_traz_o_texto_recuperado_e_nao_vaza_no_dc2(monkeypatch):
    """A avaliacao mede faithfulness contra o TEXTO, nao contra a etiqueta de citacao.

    `contexts` viaja fora do DC-2: e a chave que o run_eval usa. A API nao pode
    expo-la — `AskResponse` descarta chaves extras.
    """
    from grifo.api.schemas import AskResponse

    monkeypatch.setattr(chain_mod, "retrieve", lambda q, k, filters=None: CHUNKS)
    monkeypatch.setattr(chain_mod, "rerank", lambda q, c, k: c[:k])
    monkeypatch.setattr(chain_mod, "_default_llm", lambda: fake_llm("Resposta."))

    resp = answer("como calcular o CAC?", "Curso Exemplo")
    assert resp["contexts"] == [CHUNKS[0]["text"]]  # o texto, nao "[Módulo 2, Aula 4]"

    dc2 = AskResponse(**resp)
    assert "contexts" not in dc2.model_dump()


def test_recusa_traz_contexts_vazio(monkeypatch):
    monkeypatch.setattr(chain_mod, "retrieve", lambda q, k, filters=None: [])
    monkeypatch.setattr(chain_mod, "rerank", lambda q, c, k: [])
    monkeypatch.setattr(chain_mod, "_default_llm", lambda: fake_llm("x"))
    assert answer("receita de bolo", "Curso Exemplo")["contexts"] == []
