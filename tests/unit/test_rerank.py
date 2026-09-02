"""FR-23: reranking desligado por config devolve top_k sem carregar o modelo."""

from grifo.config import settings
from grifo.retrieval import rerank


def test_rerank_desligado_devolve_top_k(monkeypatch):
    monkeypatch.setattr(settings, "rerank_enabled", False)
    candidates = [{"id": c, "text": f"t{c}", "metadata": {}, "score": 0.5} for c in "abcde"]
    out = rerank.rerank("pergunta", candidates, 2)
    assert [c["id"] for c in out] == ["a", "b"]


def test_rerank_lista_vazia(monkeypatch):
    monkeypatch.setattr(settings, "rerank_enabled", False)
    assert rerank.rerank("pergunta", [], 3) == []


def test_modelo_nao_e_carregado_quando_desligado(monkeypatch):
    """O CrossEncoder pesa centenas de MB: import lazy é requisito, não otimização."""
    monkeypatch.setattr(settings, "rerank_enabled", False)
    # Se o rerank tentar usar o modelo, .predict explode no objeto sentinela
    monkeypatch.setattr(rerank, "_MODEL", object())
    rerank.rerank("pergunta", [{"id": "a", "text": "t", "metadata": {}, "score": 0.5}], 1)
