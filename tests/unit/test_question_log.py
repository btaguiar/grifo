"""FR-50/51/52: log de perguntas, agrupamento semântico leve, PII anonimizado."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from grifo.analytics import question_log
from grifo.analytics.question_log import log_question, top_questions


@pytest.fixture
def log_path(tmp_path: Path, monkeypatch) -> Path:
    f = tmp_path / "question_log.jsonl"
    monkeypatch.setattr(question_log.settings, "question_log_path", f)
    return f


def _agora_iso() -> str:
    return datetime.now(UTC).isoformat()


def test_log_question_grava_linha_completa_e_anonimizada(log_path: Path):
    """FR-50 + FR-52: uma linha por pergunta; PII não sobrevive."""
    resp = {
        "answer": "x",
        "sources": [{"modulo": "2", "aula": "4", "timestamp": None, "score": 0.8}],
        "found": True,
        "latency_ms": 120,
        "tokens": {"input": 300, "output": 40},
        "session_id": "s1",
    }
    log_question("Meu e-mail é aluno@escola.com, como calcular o CAC?", resp)
    linhas = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(linhas) == 1
    entry = json.loads(linhas[0])
    assert entry["question"] == "Meu e-mail é [EMAIL], como calcular o CAC?"
    assert entry["found"] is True
    assert entry["latency_ms"] == 120
    assert entry["tokens"] == {"input": 300, "output": 40}
    assert entry["sources"][0]["aula"] == "4"
    assert "timestamp" in entry


def test_top_questions_agrupa_formulacoes_proximas(log_path: Path):
    """FR-51: duas formulações da mesma dúvida caem no mesmo grupo."""
    for q in ["Como calcular o CAC?", "qual a fórmula do cac?", "como eu calculo o cac?"]:
        log_question(q, {"found": True, "latency_ms": 10, "tokens": {"input": 1, "output": 1}})
    log_question(
        "o que é NPS?", {"found": False, "latency_ms": 10, "tokens": {"input": 1, "output": 1}}
    )
    grupos = top_questions(days=7)
    assert len(grupos) == 2
    grupos.sort(key=lambda g: g["count"])
    assert grupos[-1]["count"] == 3  # as três formulações do CAC juntas
    assert grupos[0]["count"] == 1
    assert grupos[0]["found_rate"] == 0.0 and grupos[-1]["found_rate"] == 1.0


def test_top_questions_respeita_janela_de_dias(log_path: Path):
    velha = datetime.now(UTC) - timedelta(days=10)
    # log manual com timestamp antigo
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        linha = {
            "question": "como calcular o cac?",
            "timestamp": velha.isoformat(),
            "found": True,
            "latency_ms": 1,
            "tokens": {"input": 1, "output": 1},
            "sources": [],
        }
        f.write(json.dumps(linha, ensure_ascii=False) + "\n")
    assert top_questions(days=7) == []
    assert len(top_questions(days=15)) == 1


def test_top_questions_ordenado_por_frequencia(log_path: Path):
    log_question(
        "como calcular o cac", {"found": True, "latency_ms": 1, "tokens": {"input": 1, "output": 1}}
    )
    for _ in range(5):
        log_question(
            "o que é NPS", {"found": True, "latency_ms": 1, "tokens": {"input": 1, "output": 1}}
        )
    grupos = top_questions(days=7)
    assert grupos[0]["count"] == 5
    assert grupos[0]["question"] == "o que é NPS"
    assert [g["count"] for g in grupos] == sorted((g["count"] for g in grupos), reverse=True)
