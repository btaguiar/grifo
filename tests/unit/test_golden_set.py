"""DC-3: o golden set precisa ser válido, grande o bastante e bem composto."""

import json
from collections import Counter
from pathlib import Path

CAMINHO = Path(__file__).resolve().parents[2] / "eval" / "golden_set.jsonl"


def _itens():
    linhas = CAMINHO.read_text(encoding="utf-8").strip().splitlines()
    return [json.loads(linha) for linha in linhas]


def test_schema_dc3_em_todo_item():
    for it in _itens():
        base = {"id", "question", "expected_source", "should_answer", "categoria"}
        if it["should_answer"]:
            assert set(it) == base | {"expected_answer_contains"}
            assert set(it["expected_source"]) == {"modulo", "aula"}
        else:
            assert set(it) == base
            assert it["expected_source"] is None


def test_ids_unicos():
    ids = [it["id"] for it in _itens()]
    assert len(ids) == len(set(ids))


def test_minimo_de_50_itens():
    assert len(_itens()) >= 50


def test_composicao_60_20_20():
    """60% conceituais, 20% factuais, 20% fora-de-escopo (DC-3), com tolerância de 1."""
    contagem = Counter(it["categoria"] for it in _itens())
    total = sum(contagem.values())
    assert abs(contagem["conceitual"] / total - 0.6) < 0.05
    assert abs(contagem["factual"] / total - 0.2) < 0.05
    assert abs(contagem["fora-de-escopo"] / total - 0.2) < 0.05
    assert all(not it["should_answer"] for it in _itens() if it["categoria"] == "fora-de-escopo")


def test_cobertura_dos_modulos():
    """O golden set cobre os três módulos do corpus de exemplo."""
    modulos = {it["expected_source"]["modulo"] for it in _itens() if it["should_answer"]}
    assert modulos == {"1", "2", "3"}
