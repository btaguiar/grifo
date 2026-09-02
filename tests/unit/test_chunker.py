"""FR-13 (chunking estrutural + DC-1) e FR-16 (limpeza de transcrição)."""

import pytest
from langchain_core.documents import Document

from grifo.ingest.chunker import (
    chunk_documents,
    clean_transcript_noise,
    validate_chunk_metadata,
)


def _md(arquivo: str) -> dict:
    return {
        "curso": "Curso Exemplo",
        "modulo": "2 - Metricas",
        "aula": "4 - CAC e LTV",
        "fonte_tipo": "markdown",
        "arquivo": arquivo,
        "timestamp_inicio": None,
        "pagina": 1,
        "chunk_index": 0,
        "ingested_at": "2026-08-23T10:00:00+00:00",
    }


def test_nenhum_chunk_cruza_fronteira_de_aula():
    """FR-13: aula é a unidade estrutural; o splitter só age dentro dela."""
    docs = [
        Document(page_content="x " * 600, metadata=_md("aula-04-a.md")),
        Document(page_content="y " * 600, metadata=_md("aula-05-b.md")),
    ]
    chunks = chunk_documents(docs, 200, 30)
    assert len(chunks) > 2  # houve split por tamanho
    por_arquivo = {}
    for c in chunks:
        validate_chunk_metadata(c["metadata"])  # não levanta: schema DC-1 completo
        por_arquivo.setdefault(c["metadata"]["arquivo"], []).append(c)
    assert set(por_arquivo) == {"aula-04-a.md", "aula-05-b.md"}
    for grupo in por_arquivo.values():
        textos = "".join(c["text"] for c in grupo)
        assert "x x" in textos or "y y" in textos  # nunca mistura as aulas
        assert not ("x x" in textos and "y y" in textos)


def test_schema_dc1_completo_em_todo_chunk():
    docs = [Document(page_content="abc", metadata=_md("a.md") | {"pagina": 2})]
    chunks = chunk_documents(docs, 900, 150)
    md = chunks[0]["metadata"]
    for campo in ("curso", "modulo", "aula", "fonte_tipo", "arquivo", "chunk_index", "ingested_at"):
        assert campo in md, campo
    assert md["chunk_index"] == 0
    assert "T" in md["ingested_at"]  # ISO


def test_validacao_falha_alto():
    """DC-1: campos obrigatórios + ao menos um localizador (timestamp ou página)."""
    com_localizador = _md("x.md")
    validate_chunk_metadata(com_localizador)  # não levanta
    sem_localizador = _md("x.md") | {"pagina": None, "timestamp_inicio": None}
    with pytest.raises(ValueError, match="timestamp_inicio|pagina"):
        validate_chunk_metadata(sem_localizador)
    incompleto = {k: v for k, v in _md("x.md").items() if k != "curso"}
    with pytest.raises(ValueError, match="curso"):
        validate_chunk_metadata(incompleto)


def test_chunk_id_deterministico():
    """FR-15 nasce aqui: mesmo id -> mesmo ponto no Qdrant -> reindex não duplica."""
    docs = [Document(page_content="abc", metadata=_md("a.md"))]
    c1 = chunk_documents(docs, 900, 150)
    c2 = chunk_documents(docs, 900, 150)
    assert [c["id"] for c in c1] == [c["id"] for c in c2] == ["a:chunk0"]


def test_chunk_index_sequencial_por_arquivo():
    docs = [
        Document(page_content="x " * 400, metadata=_md("a.md")),
        Document(page_content="y " * 400, metadata=_md("a.md")),
    ]
    chunks = chunk_documents(docs, 200, 0)
    indices = [c["metadata"]["chunk_index"] for c in chunks]
    assert indices == sorted(indices)
    assert len(set(indices)) == len(indices)


def test_limpeza_de_ruido_de_transcricao():
    """FR-16: marcas de tempo, repetições e hesitações saem do texto."""
    sujo = (
        "00:00:01.000 --> 00:00:04.000\n"
        "Bem-vindos à aula.\n"
        "Bem-vindos à aula.\n"
        "éh O funil tem etapas [00:22] éh claras.\n"
        "00:01:15\n"
    )
    limpo = clean_transcript_noise(sujo)
    assert "-->" not in limpo
    assert "[00:22]" not in limpo
    assert "00:01:15" not in limpo
    assert "éh" not in limpo
    assert limpo.count("Bem-vindos à aula.") == 1
    assert "O funil tem etapas claras." in limpo
