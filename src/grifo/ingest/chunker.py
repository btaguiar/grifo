"""Chunking consciente de estrutura (ADR 003, FR-13, FR-16).

Dois estagios: primeiro divide por estrutura (secao / aula / capitulo), depois por
tamanho dentro de cada unidade, com overlap. Nenhum chunk pode cruzar fronteira de aula
-- citacao errada e pior que ausencia de citacao.

Todo chunk carrega o schema DC-1 completo. A validacao falha alto: um chunk sem
`timestamp_inicio` nem `pagina` produz citacao inutil e nao deve entrar no indice.

Chunks sao dicts {"id", "text", "metadata"}: o id deterministico
(`arquivo_stem:chunkN`) e o que garante a idempotencia da ingestao (FR-15).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

#: Campos obrigatórios do DC-1.
REQUIRED_FIELDS = ("curso", "modulo", "aula", "fonte_tipo", "arquivo", "chunk_index", "ingested_at")

#: Hesitações comuns em transcrição de aula ao vivo.
_FILLERS = frozenset({"éh", "eh", "ahn", "hã", "hmm", "umm", "uhm", "né"})

_CUE_LINE_RE = re.compile(r"^\s*-?\s*\d{1,2}:\d{2}:\d{2}[.,]\d{1,3}\s*-->.*$")
_BARE_TS_RE = re.compile(r"^\s*\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d{1,3})?\s*$")
_BRACKET_TS_RE = re.compile(r"\[\d{1,2}:\d{2}(?::\d{2})?\]")


def chunk_documents(documents: list[Document], chunk_size: int, chunk_overlap: int) -> list[dict]:
    """Documents -> chunks com metadados DC-1 completos.

    O splitter por tamanho age DENTRO de cada Document (que já representa uma
    aula/seção/janela de legendas): é isso que impede chunk cruzando fronteira.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " "],
    )
    chunks: list[dict] = []
    per_file: dict[str, int] = {}
    for doc in documents:
        arquivo = doc.metadata["arquivo"]
        for piece in splitter.split_text(doc.page_content):
            idx = per_file.get(arquivo, 0)
            per_file[arquivo] = idx + 1
            metadata = {
                **doc.metadata,
                "chunk_index": idx,
                "ingested_at": datetime.now(UTC).isoformat(),
            }
            validate_chunk_metadata(metadata)
            chunks.append(
                {"id": f"{Path(arquivo).stem}:chunk{idx}", "text": piece, "metadata": metadata}
            )
    return chunks


def validate_chunk_metadata(metadata: dict) -> None:
    """Levanta se faltar campo obrigatorio de DC-1 ou se nao houver timestamp nem pagina."""
    faltando = [c for c in REQUIRED_FIELDS if metadata.get(c) in (None, "")]
    if faltando:
        raise ValueError(f"chunk sem campo(s) obrigatório(s) do DC-1: {faltando}")
    if metadata.get("timestamp_inicio") is None and metadata.get("pagina") is None:
        raise ValueError(
            "chunk sem localizador acionável: preencha timestamp_inicio ou pagina (DC-1)"
        )


def clean_transcript_noise(text: str) -> str:
    """Remove marcas de tempo soltas, repeticoes e hesitacoes de transcricao (FR-16)."""
    kept: list[str] = []
    prev: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or _CUE_LINE_RE.match(line) or _BARE_TS_RE.match(line):
            continue
        line = _BRACKET_TS_RE.sub("", line).strip()
        if not line or line == prev:
            continue
        words = [w for w in line.split() if w.lower() not in _FILLERS]
        line = " ".join(words)
        if not line or line == prev:
            continue
        kept.append(line)
        prev = line
    return "\n".join(kept)
