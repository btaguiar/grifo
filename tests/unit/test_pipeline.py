"""FR-14: CLI e pipeline de ingestão, com o Qdrant mockado."""

from pathlib import Path

import pytest

from grifo.ingest import pipeline
from grifo.ingest.pipeline import ingest, main


@pytest.fixture
def upsert_mock(monkeypatch):
    chamadas: list[list[dict]] = []
    monkeypatch.setattr(
        pipeline.vector_store,
        "upsert_chunks",
        lambda chunks: (chamadas.append(chunks), len(chunks))[1],
    )
    return chamadas


def test_ingest_roda_o_pipeline_completo(md_file, vtt_file, upsert_mock):
    contagens = ingest(str(md_file.parent.parent.parent), curso="Curso Exemplo")
    assert contagens["documentos"] > 0
    assert contagens["chunks"] > 0
    assert contagens["tokens_embedding"] > 0
    chunks = upsert_mock[0]
    # anonymização + limpeza + metadados DC-1 já garantidos pelos testes de cada passo
    assert all("metadata" in c and "id" in c for c in chunks)
    cursos = {c["metadata"]["curso"] for c in chunks}
    assert cursos == {"Curso Exemplo"}


def test_ingest_dir_inexistente_levanta():
    with pytest.raises(NotADirectoryError):
        ingest("caminho/que/nao/existe")


def test_main_imprime_contagens_e_retorna_zero(md_file, upsert_mock, capsys):
    rc = main([str(md_file.parent.parent.parent)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "documentos=" in out and "chunks=" in out and "tokens_embedding=" in out


def test_main_dir_invalido_retorna_2(capsys):
    rc = main(["caminho/que/nao/existe"])
    assert rc == 2
    assert "não é um diretório" in capsys.readouterr().err


def test_corpus_de_samples_egra_valido(samples_dir: Path):
    """O corpus commitado precisa passar ileso pelo pipeline de chunking (validação DC-1)."""
    from grifo.ingest.chunker import chunk_documents
    from grifo.ingest.loaders import load_directory

    docs = load_directory(samples_dir, curso="Curso Exemplo")
    assert docs, "samples/ não pode estar vazio"
    chunks = chunk_documents(docs, 900, 150)
    assert chunks


def test_ingest_descarta_o_indice_bm25(md_file, upsert_mock):
    """Regressão: sem isso o BM25 seguia servindo o corpus anterior à ingestão.

    A busca vetorial passava a enxergar o material novo e a léxica não, então o resgate
    do ADR 001 ficava cego para ele — sem erro, só com resultado pior.
    """
    from grifo.retrieval import hybrid

    hybrid._bm25_cache[(("curso", "Curso Exemplo"),)] = "índice do corpus anterior"
    ingest(str(md_file.parent.parent.parent), curso="Curso Exemplo")
    assert hybrid._bm25_cache == {}
