"""FR-30/31/32/33/36: chain LCEL com contrato estruturado, recusa exata e tokens.

Desde a Fase 2 do plano de execução o LLM é injetável pelo seam `structured`:
recebe o prompt, devolve (GrifoAnswer, tokens, retries). É com esse seam que os
testes exercitam a chain sem tocar em API nenhuma.
"""

import re
from types import SimpleNamespace

import pytest

import grifo.generation.chain as chain_mod
from grifo.config import REFUSAL_MESSAGE, settings
from grifo.generation.chain import answer, build_chain
from grifo.generation.schemas import GrifoAnswer, SourceRef

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

TOKENS = {"input": 320, "output": 42}

RESP_CITADA = GrifoAnswer(
    found=True,
    answer=(
        "O CAC é o custo total dividido pelos clientes [Módulo 2 - Metricas, Aula 4 - CAC e LTV]."
    ),
    citations=[SourceRef(modulo="2 - Metricas", aula="4 - CAC e LTV", localizador="00:22:14")],
)


def fake_structured(resposta: GrifoAnswer, tokens=None, retries=0, espia=None):
    """Seam estruturado falso: devolve o contrato pronto sem tocar em API."""

    def call(prompt: str):
        if espia is not None:
            espia(prompt)
        return resposta, tokens or TOKENS, retries

    return call


def test_sem_contexto_recusa_exata_sem_chamar_llm():
    """FR-32: retriever vazio -> string exata, found=False, sources=[]."""
    chamado = SimpleNamespace(ok=False)

    def espia(_prompt):
        chamado.ok = True

    chain = build_chain(
        retriever=lambda s: {**s, "chunks": []},
        structured=fake_structured(RESP_CITADA, espia=espia),
    )
    out = chain.invoke({"question": "receita de bolo", "curso": "C"})
    assert out["answer"] == REFUSAL_MESSAGE
    assert out["found"] is False
    assert out["sources"] == []
    assert chamado.ok is False  # o LLM não é chamado quando não há contexto


def test_resposta_com_citacao_fontes_e_tokens():
    """FR-31, FR-33, FR-36."""
    chain = build_chain(
        retriever=lambda s: {**s, "chunks": CHUNKS},
        structured=fake_structured(RESP_CITADA),
    )
    out = chain.invoke({"question": "como calcular o CAC?", "curso": "C"})
    assert re.search(r"\[Módulo [^\]]+, Aula [^\]]+\]", out["answer"])
    assert out["found"] is True
    assert out["sources"][0]["timestamp"] == "00:22:14"  # FR-33
    assert out["sources"][0]["modulo"] == "2 - Metricas"
    assert out["tokens"] == TOKENS  # FR-36


def test_sem_citacao_no_texto_permanece_sem_por_padrao(monkeypatch):
    """Fase 2: FORCE_CITATION=false (default) — a chain NÃO conserta a saída.

    O número de citação medido a partir daqui é o espontâneo do modelo; anexar à
    força era atribuir fonte a afirmação não fundamentada (EVALUATION.md 5.5).
    """
    monkeypatch.setattr(settings, "force_citation", False)
    sem_citacao = GrifoAnswer(
        found=True,
        answer="O CAC é custo dividido por clientes.",
        citations=[SourceRef(modulo="2 - Metricas", aula="4 - CAC e LTV")],
    )
    chain = build_chain(
        retriever=lambda s: {**s, "chunks": CHUNKS},
        structured=fake_structured(sem_citacao),
    )
    out = chain.invoke({"question": "cac?", "curso": "C"})
    assert out["answer"] == "O CAC é custo dividido por clientes."  # intocado


def test_force_citation_anexa_quando_ativada(monkeypatch):
    """FR-31 como opt-in: com FORCE_CITATION=true, a garantia volta a valer."""
    monkeypatch.setattr(settings, "force_citation", True)
    sem_citacao = GrifoAnswer(
        found=True,
        answer="O CAC é custo dividido por clientes.",
        citations=[SourceRef(modulo="2 - Metricas", aula="4 - CAC e LTV")],
    )
    chain = build_chain(
        retriever=lambda s: {**s, "chunks": CHUNKS},
        structured=fake_structured(sem_citacao),
    )
    out = chain.invoke({"question": "cac?", "curso": "C"})
    assert re.search(r"\[Módulo [^\]]+, Aula [^\]]+\]", out["answer"])


def test_prompt_do_llm_leva_limite_recusa_e_contexto():
    """FR-35: o limite de palavras e a regra de recusa viajam no prompt final."""
    visto: dict = {}

    def espia(prompt: str):
        visto["prompt"] = prompt

    chain = build_chain(
        retriever=lambda s: {**s, "chunks": CHUNKS},
        structured=fake_structured(RESP_CITADA, espia=espia),
    )
    chain.invoke({"question": "como calcular o CAC?", "curso": "Curso Exemplo"})
    p = visto["prompt"]
    assert "200 palavras" in p
    assert REFUSAL_MESSAGE in p
    assert "custo total de aquisição" in p  # contexto formatado
    assert "como calcular o CAC?" in p
    assert "Timestamp: 00:22:14" in p  # FR-33: timestamp disponível ao modelo
    assert "found=false" in p  # o contrato estruturado está descrito no prompt


def test_answer_empacota_dc2(monkeypatch):
    """FR-30: resposta no formato DC-2, com latência e tokens sempre presentes."""

    def fake_run(s):
        if s["question"] == "pergunta":
            return {
                "answer": "x [Módulo 2 - Metricas, Aula 4 - CAC e LTV]",
                "sources": [],
                "found": True,
                "tokens": {"input": 10, "output": 2},
                "retries": 1,
            }
        return {"answer": REFUSAL_MESSAGE, "sources": [], "found": False}

    fake = chain_mod.RunnableLambda(fake_run)
    monkeypatch.setattr(chain_mod, "build_chain", lambda: fake)

    resp = answer("pergunta", "Curso Exemplo")
    assert {"answer", "sources", "found", "latency_ms", "tokens"} <= set(resp)
    assert resp["latency_ms"] >= 0
    assert resp["tokens"] == {"input": 10, "output": 2}
    assert resp["retries"] == 1

    resp_recusa = answer("outra", "Curso Exemplo", session_id="s1")
    assert resp_recusa["found"] is False
    assert resp_recusa["tokens"] == {"input": 0, "output": 0}  # presente e não nulo
    assert resp_recusa["retries"] == 0


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

    chain = build_chain(structured=fake_structured(RESP_CITADA))
    out = chain.invoke({"question": "como calcular o CAC?", "curso": "Curso Exemplo"})

    assert out["found"] is True
    assert visto["question"] == "como calcular o CAC?"
    assert visto["filters"] == {"curso": "Curso Exemplo"}  # filtro por curso chega ao retriever
    assert visto["k"] == settings.retrieve_k


def test_answer_ponta_a_ponta_com_defaults(monkeypatch):
    """FR-30: answer() no caminho real (retriever default), só o LLM é falso."""
    monkeypatch.setattr(chain_mod, "retrieve", lambda q, k, filters=None: CHUNKS)
    monkeypatch.setattr(chain_mod, "rerank", lambda q, c, k: c[:k])
    monkeypatch.setattr(chain_mod, "_default_structured", lambda: fake_structured(RESP_CITADA))

    resp = answer("como calcular o CAC?", "Curso Exemplo")

    assert {"answer", "sources", "found", "latency_ms", "tokens"} <= set(resp)
    assert resp["found"] is True
    assert re.search(r"\[Módulo [^\]]+, Aula [^\]]+\]", resp["answer"])
    assert resp["sources"][0]["timestamp"] == "00:22:14"
    assert resp["tokens"] == TOKENS
    assert resp["retries"] == 0


def test_recusa_do_llm_vira_found_false():
    """ADR 002: o modelo também recusa (found=false), e isso obedece o DC-2.

    Caso real: o threshold deixou chunks passarem (parecidos), mas nenhum responde.
    A recusa vem pelo contrato — validador exige a string exata, sem citação.
    """
    recusa = GrifoAnswer(found=False, answer=REFUSAL_MESSAGE)
    chain = build_chain(
        retriever=lambda s: {**s, "chunks": CHUNKS},
        structured=fake_structured(recusa),
    )
    out = chain.invoke({"question": "qual a receita do bolo?", "curso": "C"})

    assert out["answer"] == REFUSAL_MESSAGE  # string exata, sem citação anexada
    assert out["found"] is False
    assert out["sources"] == []
    assert out["tokens"] == TOKENS  # FR-36: tokens gastos contam


def test_retries_de_validacao_viajam_no_resultado():
    """Fase 2: o contrato pode exigir re-tentativa, e o eval mede isso (retry_rate)."""
    chain = build_chain(
        retriever=lambda s: {**s, "chunks": CHUNKS},
        structured=fake_structured(RESP_CITADA, retries=2),
    )
    out = chain.invoke({"question": "cac?", "curso": "C"})
    assert out["retries"] == 2


def test_contexts_traz_o_texto_recuperado_e_nao_vaza_no_dc2(monkeypatch):
    """A avaliacao mede faithfulness contra o TEXTO, nao contra a etiqueta de citacao.

    `contexts` viaja fora do DC-2: e a chave que o run_eval usa. A API nao pode
    expo-la — `AskResponse` descarta chaves extras.
    """
    from grifo.api.schemas import AskResponse

    monkeypatch.setattr(chain_mod, "retrieve", lambda q, k, filters=None: CHUNKS)
    monkeypatch.setattr(chain_mod, "rerank", lambda q, c, k: c[:k])
    monkeypatch.setattr(chain_mod, "_default_structured", lambda: fake_structured(RESP_CITADA))

    resp = answer("como calcular o CAC?", "Curso Exemplo")
    assert resp["contexts"] == [CHUNKS[0]["text"]]  # o texto, nao "[Módulo 2, Aula 4]"

    dc2 = AskResponse(**resp)
    assert "contexts" not in dc2.model_dump()
    assert "retries" not in dc2.model_dump()


def test_recusa_traz_contexts_vazio(monkeypatch):
    monkeypatch.setattr(chain_mod, "retrieve", lambda q, k, filters=None: [])
    monkeypatch.setattr(chain_mod, "rerank", lambda q, c, k: [])
    monkeypatch.setattr(chain_mod, "_default_structured", lambda: fake_structured(RESP_CITADA))
    assert answer("receita de bolo", "Curso Exemplo")["contexts"] == []


def test_contrato_rejeitado_nao_tem_caminho_de_contorno():
    """O seam estruturado é o ÚNICO caminho: exceção do contrato sobe, nada conserta.

    Se o instructor esgotar os retries, a falha precisa estourar — silenciá-la
    devolveria prosa sem validação, ressuscitando o regex por cima de saída livre.
    """
    chain = build_chain(
        retriever=lambda s: {**s, "chunks": CHUNKS},
        structured=lambda p: (_ for _ in ()).throw(ValueError("contrato violado")),
    )
    with pytest.raises(ValueError, match="contrato violado"):
        chain.invoke({"question": "x", "curso": "C"})
