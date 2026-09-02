"""NFR-7 + provedor agnóstico: base URL e provider trocam o endpoint sem tocar no código.

Pinamos `embedding_provider` em cada teste para não depender do .env da máquina
(o CI e cada dev podem rodar com provedores diferentes).
"""

from grifo.config import settings
from grifo.generation.chain import _default_llm
from grifo.retrieval import vector_store

GLM_URL = "https://api.z.ai/api/paas/v4"


def test_llm_usa_base_url_custom(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "chave-teste")
    monkeypatch.setattr(settings, "openai_base_url", GLM_URL)
    llm = _default_llm()
    assert "api.z.ai" in str(llm.openai_api_base)


def test_llm_sem_base_url_usa_endpoint_padrao(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "chave-teste")
    monkeypatch.setattr(settings, "openai_base_url", "")
    llm = _default_llm()
    assert "z.ai" not in str(llm.openai_api_base)


def test_embedder_usa_base_url_custom(monkeypatch):
    monkeypatch.setattr(settings, "embedding_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", "chave-teste")
    monkeypatch.setattr(settings, "openai_base_url", GLM_URL)
    vector_store._embedder.cache_clear()
    emb = vector_store._embedder()
    assert "api.z.ai" in str(emb.openai_api_base)
    assert emb.check_embedding_ctx_length is False  # sem batching tiktoken fora da OpenAI
    vector_store._embedder.cache_clear()


def test_embedder_padrao_mantem_comportamento_openai(monkeypatch):
    monkeypatch.setattr(settings, "embedding_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", "chave-teste")
    monkeypatch.setattr(settings, "openai_base_url", "")
    vector_store._embedder.cache_clear()
    emb = vector_store._embedder()
    assert emb.check_embedding_ctx_length is True
    vector_store._embedder.cache_clear()


def test_embedder_local_nao_toca_em_api(monkeypatch):
    """EMBEDDING_PROVIDER=local nunca instancia cliente HTTP — é sentence-transformers."""
    monkeypatch.setattr(settings, "embedding_provider", "local")
    vector_store._embedder.cache_clear()

    carregado = {}

    def fake_local(model_name):
        carregado["modelo"] = model_name
        return object()  # sentinela: o teste não baixa modelo nenhum

    monkeypatch.setattr(vector_store, "_LocalEmbedder", fake_local)
    emb = vector_store._embedder()
    assert emb is not None
    assert carregado["modelo"] == settings.embedding_model
    vector_store._embedder.cache_clear()
