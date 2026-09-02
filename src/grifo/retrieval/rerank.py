"""Reranking com cross-encoder: RETRIEVE_K candidatos -> FINAL_K no prompt (FR-23).

Ganho grande de precisao por pouco custo. A contribuicao real precisa ser medida na
ablacao de EVALUATION.md secao 4.4 -- se nao mover a agulha, corte.

O modelo (sentence-transformers) é carregado lazy: centenas de MB que testes unitários
e o modo desligado (RERANK_ENABLED=false) nunca tocam.
"""

from __future__ import annotations

from typing import Any

from grifo.config import settings

_MODEL: Any = None


def _get_model() -> Any:
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import CrossEncoder

        _MODEL = CrossEncoder(settings.reranker_model)
    return _MODEL


def rerank(question: str, candidates: list[dict], top_k: int) -> list[dict]:
    """Reordena os candidatos e devolve os top_k.

    Com RERANK_ENABLED=false devolve os top_k como vieram — corte de prazo em um
    parâmetro (SPEC secao 11), sem mudar o resto da chain.
    """
    if not candidates:
        return []
    if not settings.rerank_enabled:
        return candidates[:top_k]
    model = _get_model()
    pares = [(question, c["text"]) for c in candidates]
    scores = model.predict(pares)
    ordenados = sorted(
        ((c, float(s)) for c, s in zip(candidates, scores, strict=False)),
        key=lambda cs: cs[1],
        reverse=True,
    )
    return [{**c, "score": s} for c, s in ordenados[:top_k]]
