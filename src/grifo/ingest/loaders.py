"""Carregadores de material: PDF, VTT, SRT, Markdown -> Document.

Requisitos: FR-10 (recebe path de diretorio, nao sabe se o corpus e real ou sanitizado),
FR-11 (um loader por formato).

Regra de arquitetura: nenhuma funcao aqui pode assumir origem do conteudo. O contrato
e sempre `path -> list[Document]`, e a estrutura (modulo/aula) sai do caminho do arquivo
ou do proprio conteudo, nunca de configuracao hardcoded.

Convencao de nomes (samples/README):
    modulo-<n>-<slug>/aula-<nn>-<slug>.<ext>  ->  modulo="n - Slug", aula="nn - Slug"

Em Markdown, o heading `# Aula n — Título` sobrescreve o nome da aula (recupera acentos
que o slug do arquivo não carrega).
"""

from __future__ import annotations

import re
import sys
from collections.abc import Callable
from pathlib import Path

import webvtt
from langchain_core.documents import Document
from pypdf import PdfReader

#: Janela de legendas agrupadas por Document antes do chunking por tamanho.
_WINDOW_CHARS = 1200

FORMATOS = {
    ".pdf": "pdf",
    ".vtt": "transcricao",
    ".srt": "transcricao",
    ".md": "markdown",
}

LOADERS: dict[str, Callable[..., list[Document]]] = {}  # preenchido no fim do módulo

_MODULO_RE = re.compile(r"^modulo-?(\d+)(?:-(.+))?$", re.IGNORECASE)
_AULA_RE = re.compile(r"^aula-?(\d+)(?:-(.+))?$", re.IGNORECASE)
#: `# Aula 4 — CAC e LTV` (aceita travessão, meia-risca ou hífen).
_AULA_HEADING_RE = re.compile(
    r"^#\s+Aula\s+(\d+)\s*[—–-]\s*(.+?)\s*$",  # noqa: RUF001 — a risca é parte do padrão
    re.IGNORECASE | re.MULTILINE,
)
_SRT_TIME_RE = re.compile(r"^(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->", re.MULTILINE)

#: Dossiê de mentoria: a transcrição é seccionada por `### [HH:MM:SS]` (aceita `##`).
_TS_HEADING_RE = re.compile(r"^#{2,3}[ \t]*\[(\d{1,2}:\d{2}:\d{2})\][ \t]*$", re.MULTILINE)
#: Abaixo disso o bloco é juntado ao seguinte: ~1,5% do corpus, e chunk minúsculo
#: só polui o top-k. Acima disso cada bloco mantém o próprio minuto.
_MIN_BLOCO_CHARS = 600
#: Dois timestamps já caracterizam o formato; um heading solto não.
_MIN_TS_PARA_TRANSCRICAO = 2


def _humanize(slug: str) -> str:
    return " ".join(w.capitalize() for w in slug.replace("_", "-").split("-") if w)


def _structure_from(path: Path) -> dict:
    """Deriva modulo/aula/fonte_tipo/arquivo do caminho do arquivo."""
    m = _MODULO_RE.match(path.parent.name)
    if m:
        modulo = (
            f"{int(m.group(1))} - {_humanize(m.group(2))}" if m.group(2) else str(int(m.group(1)))
        )
    else:
        modulo = path.parent.name

    a = _AULA_RE.match(path.stem)
    if a and a.group(2):
        aula = f"{int(a.group(1))} - {_humanize(a.group(2))}"
    elif a:
        aula = str(int(a.group(1)))
    else:
        aula = path.stem

    return {
        "modulo": modulo,
        "aula": aula,
        "fonte_tipo": FORMATOS[path.suffix.lower()],
        "arquivo": path.name,
        "timestamp_inicio": None,
        "pagina": None,
    }


def _base_metadata(path: Path, curso: str | None) -> dict:
    return _structure_from(path) | {"curso": curso}


def load_directory(path: Path, curso: str | None = None) -> list[Document]:
    """Varre o diretorio e despacha cada arquivo para o loader do seu formato.

    Arquivos fora de um diretorio `modulo-<n>-<slug>` sao pulados com aviso: sem
    estrutura de modulo/aula a citacao vira lixo ("Modulo samples, Aula README"),
    e citacao errada e pior que ausencia de citacao (ADR 003).
    """
    path = Path(path)
    if not path.is_dir():
        raise NotADirectoryError(f"não é um diretório: {path}")
    docs: list[Document] = []
    pulados: list[str] = []
    for f in sorted(p for p in path.rglob("*") if p.is_file()):
        loader = LOADERS.get(f.suffix.lower())
        if loader is None:
            continue
        if _MODULO_RE.match(f.parent.name) is None:
            pulados.append(str(f))
            continue
        docs.extend(loader(f, curso=curso))
    if pulados:
        print(
            f"aviso: {len(pulados)} arquivo(s) fora da estrutura modulo-<n>-<slug> "
            f"(pulados): {', '.join(pulados)}",
            file=sys.stderr,
        )
    return docs


def load_pdf(path: Path, curso: str | None = None) -> list[Document]:
    """PDF -> Documents, com `pagina` no metadado."""
    base = _base_metadata(path, curso)
    docs = []
    for i, page in enumerate(PdfReader(str(path)).pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            docs.append(Document(page_content=text, metadata=base | {"pagina": i}))
    return docs


def load_vtt(path: Path, curso: str | None = None) -> list[Document]:
    """WebVTT -> Documents, com `timestamp_inicio` no metadado."""
    cues = []
    for cap in webvtt.read(str(path)):
        line = " ".join(cap.text.split())
        if line:
            cues.append((_hhmmss(cap.start), line))
    return _window(cues, _base_metadata(path, curso))


def load_srt(path: Path, curso: str | None = None) -> list[Document]:
    """SubRip -> Documents, com `timestamp_inicio` no metadado. Parser próprio."""
    text = path.read_text(encoding="utf-8", errors="replace")
    cues: list[tuple[str, str]] = []
    block: list[str] = []
    for line in [*text.splitlines(), ""]:
        if line.strip():
            block.append(line)
            continue
        if block:
            cue = _parse_srt_block(block)
            if cue:
                cues.append(cue)
            block = []
    return _window(cues, _base_metadata(path, curso))


def _parse_srt_block(lines: list[str]) -> tuple[str, str] | None:
    """Um bloco SRT: [indice], `HH:MM:SS,mmm --> ...`, texto."""
    if len(lines) < 2:
        return None
    m = _SRT_TIME_RE.match(lines[1]) if len(lines) > 1 else None
    if m is None:
        # bloco sem linha de tempo (ou indice ausente): tenta a primeira linha
        m = _SRT_TIME_RE.match(lines[0])
        if m is None:
            return None
        body = lines[1:]
    else:
        body = lines[2:]
    ts = f"{m.group(1)}:{m.group(2)}:{m.group(3)}"
    texto = " ".join(" ".join(body).split())
    return (ts, texto) if texto else None


def _hhmmss(stamp: str) -> str:
    """ "00:22:14.500" -> "00:22:14" (formato de citação do DC-1)."""
    parts = stamp.split(":")
    if len(parts) == 3:
        return f"{int(parts[0]):02d}:{int(parts[1]):02d}:{int(float(parts[2])):02d}"
    return stamp


def _window(cues: list[tuple[str, str]], base: dict) -> list[Document]:
    """Agrupa legendas em janelas de ~_WINDOW_CHARS, cada uma com seu timestamp."""
    docs: list[Document] = []
    buf: list[str] = []
    size = 0
    ts: str | None = None
    for stamp, line in cues:
        if ts is None:
            ts = stamp
        buf.append(line)
        size += len(line)
        if size >= _WINDOW_CHARS:
            docs.append(
                Document(page_content=" ".join(buf), metadata=base | {"timestamp_inicio": ts})
            )
            buf, size, ts = [], 0, None
    if buf:
        docs.append(Document(page_content=" ".join(buf), metadata=base | {"timestamp_inicio": ts}))
    return docs


def _split_md_sections(text: str) -> list[tuple[str | None, str]]:
    """Divide o Markdown por headings `##`; a introdução vira a primeira seção."""
    sections: list[tuple[str | None, list[str]]] = [(None, [])]
    for line in text.splitlines():
        if line.startswith("## "):
            sections.append((line[3:].strip(), []))
        else:
            sections[-1][1].append(line)
    out = []
    for title, body in sections:
        content = "\n".join(body).strip()
        if content:
            out.append((title, content))
    return out


def _split_transcript_blocks(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Separa o preâmbulo do dossiê dos blocos `[HH:MM:SS]` que vêm depois."""
    marcas = list(_TS_HEADING_RE.finditer(text))
    preambulo = text[: marcas[0].start()].strip()
    blocos: list[tuple[str, str]] = []
    for i, m in enumerate(marcas):
        fim = marcas[i + 1].start() if i + 1 < len(marcas) else len(text)
        corpo = text[m.end() : fim].strip()
        if corpo:
            blocos.append((m.group(1), corpo))
    return preambulo, blocos


def _merge_blocos(blocos: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Junta blocos curtos ao seguinte, preservando o timestamp do PRIMEIRO."""
    saida: list[tuple[str, str]] = []
    buf: list[str] = []
    ts: str | None = None
    for stamp, corpo in blocos:
        if ts is None:
            ts = stamp
        buf.append(corpo)
        if sum(len(b) for b in buf) >= _MIN_BLOCO_CHARS:
            saida.append((ts, "\n\n".join(buf)))
            buf, ts = [], None
    if buf and ts is not None:
        saida.append((ts, "\n\n".join(buf)))
    return saida


def _load_transcript_md(path: Path, base: dict) -> list[Document]:
    """Dossiê de mentoria: cada `### [HH:MM:SS]` vira um Document com seu minuto.

    É o que faz a citação virar link para o ponto do vídeo (FR-33). Sem isso a
    transcrição inteira colapsa numa seção só e o timestamp vira ruído dentro do texto.

    `fonte_tipo` passa a `transcricao` para o pipeline aplicar `clean_transcript_noise`.
    """
    text = path.read_text(encoding="utf-8")
    base = base | {"fonte_tipo": "transcricao"}
    preambulo, blocos = _split_transcript_blocks(text)
    docs: list[Document] = []
    if preambulo:
        # Capa da sessão (título, programa, bio do mentor): sem minuto, mas é a
        # única parte com contexto de quem fala. `pagina=1` satisfaz o DC-1.
        docs.append(Document(page_content=preambulo, metadata=base | {"pagina": 1}))
    for stamp, corpo in _merge_blocos(blocos):
        docs.append(Document(page_content=corpo, metadata=base | {"timestamp_inicio": stamp}))
    return docs


def load_markdown(path: Path, curso: str | None = None) -> list[Document]:
    """Markdown -> Documents, usando os headings como estrutura.

    Dois formatos: dossiê de mentoria (seccionado por `[HH:MM:SS]`) e Markdown comum
    (seccionado por `##`). O formato é detectado pelo conteúdo, não pela extensão.

    No Markdown comum, `pagina` = número da seção: é o localizador acionável da
    citação (a invariante DC-1 pede timestamp ou página).
    """
    text = path.read_text(encoding="utf-8")
    base = _base_metadata(path, curso)
    m = _AULA_HEADING_RE.search(text)
    if m:
        base["aula"] = f"{m.group(1)} - {m.group(2)}"
    if len(_TS_HEADING_RE.findall(text)) >= _MIN_TS_PARA_TRANSCRICAO:
        return _load_transcript_md(path, base)
    docs = []
    for i, (_title, body) in enumerate(_split_md_sections(text), start=1):
        docs.append(Document(page_content=body, metadata=base | {"pagina": i}))
    return docs


LOADERS = {".pdf": load_pdf, ".vtt": load_vtt, ".srt": load_srt, ".md": load_markdown}
