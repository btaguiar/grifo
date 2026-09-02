"""Testes de integração: exigem Qdrant em QDRANT_URL e OPENAI_API_KEY válida.

    docker compose up -d qdrant
    .venv\Scripts\python -m pytest -m integration

FR-15 (idempotência) e FR-20 (busca filtrada por módulo).
"""

from pathlib import Path

import pytest

from grifo.ingest.pipeline import ingest
from grifo.retrieval import vector_store

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def samples_dir() -> Path:
    return REPO_ROOT / "samples"


@pytest.fixture(scope="module")
def corpus_indexado(samples_dir: Path) -> dict:
    return ingest(str(samples_dir), curso="Curso Exemplo")


def test_ingest_e_idempotente(samples_dir: Path, corpus_indexado: dict):
    """FR-15: rodar 2x → mesma contagem na coleção."""
    segunda = ingest(str(samples_dir), curso="Curso Exemplo")
    assert segunda["chunks"] == corpus_indexado["chunks"]
    pontos = vector_store.fetch_all(filters={"curso": "Curso Exemplo"})
    ids = [p["id"] for p in pontos]
    assert len(ids) == len(set(ids)), "chunks duplicados após reindexar"


def test_busca_filtrada_por_modulo(corpus_indexado: dict):
    """FR-20: query filtrada por módulo só devolve chunks daquele módulo."""
    emb = vector_store._embedder()
    vetor = emb.embed_query("como calcular o CAC?")
    hits = vector_store.search(
        vetor, 10, filters={"curso": "Curso Exemplo", "modulo": "2 - Metricas"}
    )
    assert hits
    assert all(h["metadata"]["modulo"] == "2 - Metricas" for h in hits)


def test_busca_sem_filtro_retorna_o_corpus(corpus_indexado: dict):
    emb = vector_store._embedder()
    vetor = emb.embed_query("estratégia de crescimento")
    hits = vector_store.search(vetor, 5, filters={"curso": "Curso Exemplo"})
    assert hits and all(h["score"] > 0 for h in hits)


def test_configuracao_de_testes():
    """Sanidade: estes testes só fazem sentido com a coleção da config."""
    from grifo.config import settings

    assert settings.qdrant_collection
