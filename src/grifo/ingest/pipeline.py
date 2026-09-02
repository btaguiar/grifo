"""Orquestracao da ingestao e CLI (FR-14, FR-15).

    python -m grifo.ingest <dir>

Fluxo: load_directory -> anonymize -> chunk -> embed -> upsert no Qdrant.
Imprime contagem de documentos, chunks e tokens de embedding ao final (NFR-2).
Idempotente: reindexar o mesmo diretorio nao duplica chunks (FR-15) -- o id deterministico
de DC-1 (`modulo3_aula7:chunk12`) e o que garante isso.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import tiktoken

from grifo.config import settings
from grifo.ingest.anonymize import anonymize
from grifo.ingest.chunker import chunk_documents, clean_transcript_noise
from grifo.ingest.loaders import load_directory
from grifo.retrieval import hybrid, vector_store


def ingest(path: str, curso: str | None = None) -> dict:
    """Executa o pipeline completo e devolve as contagens."""
    curso = curso or settings.curso_nome
    documentos = load_directory(Path(path), curso=curso)
    for doc in documentos:
        doc.page_content = anonymize(doc.page_content)
        if doc.metadata.get("fonte_tipo") == "transcricao":
            doc.page_content = clean_transcript_noise(doc.page_content)
    chunks = chunk_documents(documentos, settings.chunk_size, settings.chunk_overlap)
    escritos = vector_store.upsert_chunks(chunks) if chunks else 0
    assert escritos == len(chunks), f"upsert escreveu {escritos} de {len(chunks)} chunks"
    # O indice lexico e um snapshot do corpus: sem descarta-lo, o material que acabou de
    # entrar fica visivel so para a busca vetorial, e o resgate do ADR 001 nao o alcanca.
    hybrid.invalidate_cache()
    return {
        "documentos": len(documentos),
        "chunks": len(chunks),
        "tokens_embedding": _count_embedding_tokens([c["text"] for c in chunks]),
    }


def _count_embedding_tokens(texts: list[str]) -> int:
    """text-embedding-3-small usa o vocabulário cl100k_base (NFR-2)."""
    if not texts:
        return 0
    enc = tiktoken.get_encoding("cl100k_base")
    return sum(len(enc.encode(t)) for t in texts)


def main(argv: list[str] | None = None) -> int:
    """Entry point da CLI."""
    parser = argparse.ArgumentParser(
        prog="python -m grifo.ingest",
        description="Indexa um diretório de material do curso no Qdrant (FR-14).",
    )
    parser.add_argument("dir", help="diretório com o material (ex.: samples/ ou data/raw/)")
    parser.add_argument("--curso", default=settings.curso_nome, help="nome do curso nos metadados")
    args = parser.parse_args(argv)

    if not Path(args.dir).is_dir():
        print(f"erro: {args.dir} não é um diretório", file=sys.stderr)
        return 2

    contagens = ingest(args.dir, args.curso)
    print(
        f"curso={args.curso} "
        f"documentos={contagens['documentos']} "
        f"chunks={contagens['chunks']} "
        f"tokens_embedding={contagens['tokens_embedding']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
