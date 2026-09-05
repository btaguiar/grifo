"""FR-40 a FR-44: contrato DC-2, health com Qdrant, ingest protegido, analytics."""

import pytest
from fastapi.testclient import TestClient

from grifo.api import main as api_main
from grifo.api.main import app
from grifo.config import REFUSAL_MESSAGE

client = TestClient(app)


@pytest.fixture(autouse=True)
def log_isolado(tmp_path, monkeypatch):
    """Nenhum teste de API escreve no log real."""
    from grifo.analytics import question_log

    monkeypatch.setattr(question_log.settings, "question_log_path", tmp_path / "log.jsonl")


def _respota_modelo(found=True):
    if not found:
        return {
            "answer": REFUSAL_MESSAGE,
            "sources": [],
            "found": False,
            "latency_ms": 50,
            "tokens": {"input": 0, "output": 0},
        }
    return {
        "answer": (
            "O CAC é o custo total dividido pelos clientes "
            "[Módulo 2 - Metricas, Aula 4 - CAC e LTV]."
        ),
        "sources": [
            {
                "modulo": "2 - Metricas",
                "aula": "4 - CAC e LTV",
                "timestamp": "00:22:14",
                "score": 0.81,
            }
        ],
        "found": True,
        "latency_ms": 1840,
        "tokens": {"input": 2100, "output": 90},
    }


def test_ask_contrato_dc2(monkeypatch):
    """FR-40: request/response conforme DC-2."""
    monkeypatch.setattr(api_main.chain, "answer", lambda q, c, s=None: _respota_modelo(True))
    r = client.post("/ask", json={"question": "como calcular o CAC?", "curso": "Curso Exemplo"})
    assert r.status_code == 200
    body = r.json()
    assert body["found"] is True
    assert body["sources"][0]["timestamp"] == "00:22:14"
    assert set(body) == {"answer", "sources", "found", "latency_ms", "tokens"}


def test_ask_recusa_contrato(monkeypatch):
    """found=false implica answer == recusa exata e sources vazio (DC-2)."""
    monkeypatch.setattr(api_main.chain, "answer", lambda q, c, s=None: _respota_modelo(False))
    r = client.post("/ask", json={"question": "receita de bolo", "curso": "Curso Exemplo"})
    body = r.json()
    assert body["found"] is False
    assert body["answer"] == REFUSAL_MESSAGE
    assert body["sources"] == []


def test_ask_loga_a_pergunta_anonimizada(monkeypatch, tmp_path):
    """FR-50/52 pela porta da API."""
    monkeypatch.setattr(api_main.chain, "answer", lambda q, c, s=None: _respota_modelo(True))
    client.post(
        "/ask",
        json={"question": "meu email é a@b.com, e o CAC?", "curso": "C", "session_id": "s1"},
    )
    log = (tmp_path / "log.jsonl").read_text(encoding="utf-8")
    assert "a@b.com" not in log and "[EMAIL]" in log


def test_ask_payload_invalido_400():
    assert client.post("/ask", json={"curso": "C"}).status_code == 400
    assert client.post("/ask", json={"question": "", "curso": "C"}).status_code == 400


def test_ask_falha_do_provedor_500_com_request_id(monkeypatch):
    def explode(q, c, s=None):
        raise RuntimeError("OpenAI fora")

    monkeypatch.setattr(api_main.chain, "answer", explode)
    r = client.post("/ask", json={"question": "q", "curso": "C"})
    assert r.status_code == 500
    assert "request_id" in r.json()["detail"]


def test_health_ok(monkeypatch):
    monkeypatch.setattr(api_main.vector_store, "healthcheck", lambda: None)
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["qdrant"] == "up"
    assert body["collection"] and body["version"]


def test_health_qdrant_fora_503(monkeypatch):
    """FR-41: Qdrant indisponível → 503."""
    monkeypatch.setattr(api_main.vector_store, "healthcheck", lambda: "down")
    r = client.get("/health")
    assert r.status_code == 503
    assert r.json()["detail"]["qdrant"] == "down"


def test_health_sem_indice_503(monkeypatch):
    """Regressão: o Qdrant no ar com a coleção ausente respondia `ok`.

    E aí todo /ask devolvia 500 com um 404 do Qdrant por baixo. O FR-41 pede que o
    serviço se declare degradado SEM o índice — não que confirme o índice pela
    conectividade de quem o hospeda.
    """
    monkeypatch.setattr(api_main.vector_store, "healthcheck", lambda: "sem indice")
    r = client.get("/health")
    assert r.status_code == 503
    detalhe = r.json()["detail"]
    assert detalhe["qdrant"] == "sem indice"
    assert detalhe["collection"]  # qual coleção falta, para o erro ser acionável


def test_ingest_sem_token_401():
    assert client.post("/ingest", json={"path": "samples", "curso": "C"}).status_code == 401
    r = client.post(
        "/ingest", json={"path": "samples", "curso": "C"}, headers={"X-Ingest-Token": "errado"}
    )
    assert r.status_code == 401


def test_ingest_com_token_200(monkeypatch, tmp_path):
    """FR-42: token correto dispara a ingestão."""
    monkeypatch.chdir(tmp_path)  # o path precisa ficar sob o cwd da API
    (tmp_path / "corpus").mkdir()
    monkeypatch.setattr(api_main.settings, "ingest_token", "secreto")
    chamado = {}
    monkeypatch.setattr(
        api_main.pipeline,
        "ingest",
        lambda p, c=None: (
            chamado.update(path=p, curso=c),
            {"documentos": 3, "chunks": 9, "tokens_embedding": 1200},
        )[1],
    )
    r = client.post(
        "/ingest",
        json={"path": "corpus", "curso": "Curso Exemplo"},
        headers={"X-Ingest-Token": "secreto"},
    )
    assert r.status_code == 200
    assert r.json() == {"documentos": 3, "chunks": 9, "tokens_embedding": 1200}
    assert chamado["curso"] == "Curso Exemplo"


def test_ingest_path_fora_do_permitido_400(monkeypatch):
    monkeypatch.setattr(api_main.settings, "ingest_token", "secreto")
    r = client.post(
        "/ingest",
        json={"path": "C:/Windows", "curso": "C"},
        headers={"X-Ingest-Token": "secreto"},
    )
    assert r.status_code == 400


def test_top_questions_endpoint(monkeypatch):
    """FR-43: lista ordenada por frequência."""
    monkeypatch.setattr(
        api_main,
        "top_questions",
        lambda days=7: [{"question": "como calcular o cac", "count": 7, "found_rate": 0.9}],
    )
    r = client.get("/analytics/top-questions", params={"days": 7})
    assert r.status_code == 200
    body = r.json()
    assert body["days"] == 7 and body["questions"][0]["count"] == 7


def test_swagger_docs_abre():
    """FR-44: página abre com os endpoints documentados."""
    r = client.get("/docs")
    assert r.status_code == 200
    spec = client.get("/openapi.json").json()
    caminhos = set(spec["paths"])
    assert {"/ask", "/ingest", "/health", "/analytics/top-questions"} <= caminhos


@pytest.fixture
def warmup_espiao(monkeypatch):
    """Registra (embedder, filtros do BM25) sem tocar em Qdrant nem carregar modelo."""
    chamadas: dict = {"embedder": 0, "filtros": []}
    monkeypatch.setattr(
        api_main.vector_store,
        "warmup",
        lambda: chamadas.__setitem__("embedder", chamadas["embedder"] + 1),
    )
    monkeypatch.setattr(
        api_main.hybrid, "warmup", lambda filters=None: (chamadas["filtros"].append(filters), 7)[1]
    )
    return chamadas


def test_startup_aquece_embedder_e_indice(warmup_espiao, monkeypatch):
    """A primeira pergunta do processo custava ~10s; o custo passa para o boot."""
    monkeypatch.setattr(api_main.settings, "curso_nome", "Curso Exemplo")
    with TestClient(app):
        pass
    assert warmup_espiao["embedder"] == 1
    # O cache do BM25 e chaveado por filtro e a chain sempre consulta com `curso`:
    # aquecer sem filtro construiria um indice que nenhuma pergunta usa.
    assert warmup_espiao["filtros"] == [{"curso": "Curso Exemplo"}]


def test_startup_sobrevive_ao_qdrant_fora(monkeypatch):
    """Aquecimento e otimizacao, nao pre-requisito: quem reporta o Qdrant fora e o /health."""

    def explode():
        raise ConnectionError("qdrant fora")

    monkeypatch.setattr(api_main.vector_store, "warmup", explode)
    with TestClient(app) as c:
        monkeypatch.setattr(api_main.vector_store, "healthcheck", lambda: None)
        assert c.get("/health").status_code == 200


def test_ingest_reaquece_o_indice_com_o_curso_do_payload(warmup_espiao, monkeypatch, tmp_path):
    """`pipeline.ingest` descarta o indice; sem reaquecer, o proximo aluno paga o rebuild."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "corpus").mkdir()
    monkeypatch.setattr(api_main.settings, "ingest_token", "secreto")
    monkeypatch.setattr(
        api_main.pipeline,
        "ingest",
        lambda p, c=None: {"documentos": 1, "chunks": 2, "tokens_embedding": 3},
    )
    r = client.post(
        "/ingest",
        json={"path": "corpus", "curso": "Outro Curso"},
        headers={"X-Ingest-Token": "secreto"},
    )
    assert r.status_code == 200
    assert warmup_espiao["filtros"] == [{"curso": "Outro Curso"}]


def test_ingest_nao_falha_se_o_reaquecimento_falhar(monkeypatch, tmp_path):
    """A ingestao ja aconteceu: quebrar a resposta por causa do cache seria mentir."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "corpus").mkdir()
    monkeypatch.setattr(api_main.settings, "ingest_token", "secreto")
    monkeypatch.setattr(
        api_main.pipeline,
        "ingest",
        lambda p, c=None: {"documentos": 1, "chunks": 2, "tokens_embedding": 3},
    )
    monkeypatch.setattr(api_main.vector_store, "warmup", lambda: 1 / 0)
    r = client.post(
        "/ingest",
        json={"path": "corpus", "curso": "C"},
        headers={"X-Ingest-Token": "secreto"},
    )
    assert r.status_code == 200
