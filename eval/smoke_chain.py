"""Smoke de 1 pergunta no caminho instructor — valida integração antes de rodada.

    python -X utf8 eval/smoke_chain.py

Usa as variáveis de ambiente da sessão (não toca no .env): aponte OPENAI_BASE_URL,
LLM_MODEL, QDRANT_COLLECTION, CURSO_NOME para o corpus público remoto e rode.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from grifo.config import settings  # noqa: E402
from grifo.generation.chain import answer  # noqa: E402


def main() -> int:
    print(f"llm={settings.llm_model} @ {settings.openai_base_url}")
    print(f"coleção={settings.qdrant_collection} curso={settings.curso_nome}")
    print(f"embeddings={settings.embedding_provider}/{settings.embedding_model}")
    for pergunta in ("Como calcular o CAC?", "Qual a receita do bolo de cenoura?"):
        r = answer(pergunta, curso=settings.curso_nome)
        print(json.dumps(r, ensure_ascii=False, indent=2)[:1500])
        print("-" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
