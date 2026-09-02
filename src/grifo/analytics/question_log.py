"""Log de perguntas e relatorio de duvidas frequentes (FR-50, FR-51, FR-52).

Esta e a feature que transforma o projeto de "chatbot" em "produto": o time de CS quer
saber quais duvidas mais aparecem, porque isso vira insumo para melhorar o curso.

FR-52: a pergunta passa por grifo.ingest.anonymize antes de ser gravada. Aluno digita
e-mail e telefone no chat.

FR-51 (agrupamento por proximidade semântica) na v1 usa tokens normalizados + Jaccard:
determinístico, sem custo de API e suficiente para agrupar reformulações. Se o CS pedir
mais precisão, vira embedding no v2.
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import UTC, datetime, timedelta
from pathlib import Path

from grifo.config import settings
from grifo.ingest.anonymize import anonymize

#: Jaccard mínimo para duas perguntas caírem no mesmo grupo.
_SIMILARIDADE_MINIMA = 0.3

#: Stem cruento: 5 caracteres de prefixo agrupam "calcular"/"calculo". Heurística de v1.
_STEM_LEN = 5

_STOPWORDS = frozenset(
    (
        "a",
        "o",
        "as",
        "os",
        "um",
        "uma",
        "de",
        "do",
        "da",
        "dos",
        "das",
        "em",
        "no",
        "na",
        "nos",
        "nas",
        "para",
        "por",
        "com",
        "que",
        "qual",
        "quais",
        "como",
        "onde",
        "quando",
        "quem",
        "porque",
        "me",
        "meu",
        "você",
        "vocês",
        "é",
        "são",
        "e",
        "ou",
        "se",
        "ao",
        "isso",
        "eu",
    )
)


def _tokens(question: str) -> set[str]:
    norm = unicodedata.normalize("NFKD", question.lower())
    norm = "".join(c for c in norm if not unicodedata.combining(c))
    return {
        t[:_STEM_LEN] if len(t) > _STEM_LEN else t
        for t in re.findall(r"[a-z0-9]+", norm)
        if t not in _STOPWORDS and len(t) > 1
    }


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def log_question(question: str, response: dict) -> None:
    """Grava uma linha no log: pergunta anonimizada, found, latencia, tokens, fontes."""
    caminho = Path(settings.question_log_path)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "question": anonymize(question),
        "timestamp": datetime.now(UTC).isoformat(),
        "found": bool(response.get("found")),
        "latency_ms": response.get("latency_ms", 0),
        "tokens": response.get("tokens") or {"input": 0, "output": 0},
        "sources": response.get("sources") or [],
        "session_id": response.get("session_id"),
    }
    with caminho.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _read_within(days: int) -> list[dict]:
    caminho = Path(settings.question_log_path)
    if not caminho.exists():
        return []
    limite = datetime.now(UTC) - timedelta(days=days)
    entradas = []
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        if not linha.strip():
            continue
        try:
            entry = json.loads(linha)
            ts = datetime.fromisoformat(entry["timestamp"])
        except (ValueError, KeyError):
            continue
        if ts >= limite:
            entradas.append(entry)
    return entradas


def top_questions(days: int = 7) -> list[dict]:
    """Duvidas mais frequentes no periodo, agrupadas por proximidade (FR-51).

    Retorna [{"question", "count", "found_rate"}] em ordem decrescente de frequência.
    O representante do grupo é a primeira formulação registrada.
    """
    grupos: list[dict] = []
    for entry in _read_within(days):
        tokens = _tokens(entry["question"])
        for grupo in grupos:
            if _jaccard(tokens, grupo["tokens"]) >= _SIMILARIDADE_MINIMA:
                grupo["entradas"].append(entry)
                grupo["tokens"] |= tokens
                break
        else:
            grupos.append({"tokens": tokens, "entradas": [entry]})

    resultado = [
        {
            "question": g["entradas"][0]["question"],
            "count": len(g["entradas"]),
            "found_rate": sum(1 for e in g["entradas"] if e.get("found")) / len(g["entradas"]),
        }
        for g in grupos
    ]
    return sorted(resultado, key=lambda r: (-r["count"], r["question"]))
