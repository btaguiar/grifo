"""Varreduras de calibração do retrieval (EVALUATION.md 4.1, 4.2, 4.4).

    python eval/calibrar_retrieval.py [--k] [--ablacao] [--threshold]

Mede SÓ retrieval: nenhuma chamada de LLM, nenhum custo, ~30ms por consulta. É o que
permite varrer parâmetros de verdade em vez de aceitar os valores de partida da SPEC.

O que cada métrica quer dizer aqui:

  fonte@k      o `expected_source` do golden set apareceu nos k primeiros chunks. É o
               proxy honesto de context precision enquanto o RAGAS não está instalado —
               mede acerto de aula, não relevância de trecho. Não confunda os dois.

  recusa       das perguntas com `should_answer: false`, quantas o retrieval devolve
               vazio. É o PRIMEIRO gate do ADR 002; o segundo é o LLM, e ele não entra
               aqui. Por isso este número é um piso, não a taxa de recusa final.

  cobertura    das perguntas dentro do escopo, quantas recebem ao menos um chunk. Sobe
               e desce ao contrário da recusa: é a metade do trade-off que a métrica de
               recusa correta, sozinha, não mostra.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from grifo.config import settings  # noqa: E402
from grifo.retrieval import hybrid  # noqa: E402
from grifo.retrieval.hybrid import retrieve  # noqa: E402
from grifo.retrieval.rerank import rerank  # noqa: E402

GOLDEN_SET = (REPO_ROOT / settings.golden_set).resolve()
FILTRO = {"curso": settings.curso_nome}


def _num(valor: str) -> str:
    m = re.match(r"\s*(\d+)", valor or "")
    return m.group(1) if m else valor


def carregar() -> tuple[list[dict], list[dict]]:
    itens = [
        json.loads(linha)
        for linha in GOLDEN_SET.read_text(encoding="utf-8").splitlines()
        if linha.strip()
    ]
    return [i for i in itens if i["should_answer"]], [i for i in itens if not i["should_answer"]]


def _acertou(hits: list[dict], esperada: dict) -> bool:
    return any(
        _num(h["metadata"]["modulo"]) == esperada["modulo"]
        and _num(h["metadata"]["aula"]) == esperada["aula"]
        for h in hits
    )


def medir(dentro: list[dict], fora: list[dict], k_corte: int, usar_rerank: bool) -> dict:
    """Uma passada completa do golden set na configuração atual de `settings`."""
    hybrid._bm25_cache.clear()  # o índice depende dos parâmetros de resgate
    top_k = com_chunk = 0
    for it in dentro:
        hits = retrieve(it["question"], settings.retrieve_k, filters=FILTRO)
        if hits:
            com_chunk += 1
        finais = rerank(it["question"], hits, k_corte) if usar_rerank else hits[:k_corte]
        top_k += _acertou(finais, it["expected_source"])
    recusou = sum(
        1 for it in fora if not retrieve(it["question"], settings.retrieve_k, filters=FILTRO)
    )
    return {
        "fonte": top_k / len(dentro),
        "recusa": recusou / len(fora),
        "cobertura": com_chunk / len(dentro),
    }


def sweep_threshold(dentro, fora) -> None:
    print("\n### 4.1 SCORE_THRESHOLD\n")
    print("| Threshold | fonte@5 | Recusa correta (só retrieval) | Cobertura |")
    print("|---|---|---|---|")
    original = settings.score_threshold
    for thr in (0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.53, 0.55, 0.60):
        settings.score_threshold = thr
        m = medir(dentro, fora, 5, usar_rerank=True)
        marca = " (partida)" if thr == 0.35 else ""
        print(f"| {thr:.2f}{marca} | {m['fonte']:.0%} | {m['recusa']:.0%} | {m['cobertura']:.0%} |")
    settings.score_threshold = original


def sweep_final_k(dentro, fora) -> None:
    import tiktoken

    from grifo.generation.prompts import format_context

    enc = tiktoken.get_encoding("cl100k_base")
    print("\n### 4.2 FINAL_K\n")
    print("| FINAL_K | fonte@k | Tokens de contexto (média) | Cobertura |")
    print("|---|---|---|---|")
    for k in (3, 5, 8):
        m = medir(dentro, fora, k, usar_rerank=True)
        toks = []
        for it in dentro[:12]:  # amostra: o custo aqui é o cross-encoder, não o retrieval
            hits = retrieve(it["question"], settings.retrieve_k, filters=FILTRO)
            toks.append(len(enc.encode(format_context(rerank(it["question"], hits, k)))))
        marca = " (partida)" if k == 5 else ""
        media = sum(toks) // max(len(toks), 1)
        print(f"| {k}{marca} | {m['fonte']:.0%} | {media} | {m['cobertura']:.0%} |")


def sweep_ablacao(dentro, fora) -> None:
    print("\n### 4.4 Contribuição de cada componente\n")
    print("| Configuração | fonte@5 | Recusa | Cobertura |")
    print("|---|---|---|---|")
    idf_orig, pesos_orig = settings.bm25_rescue_min_idf, settings.hybrid_weight_bm25

    settings.bm25_rescue_min_idf = 99.0  # desliga o resgate
    settings.hybrid_weight_bm25 = 0.0  # e a fusão RRF: sobra só o vetorial
    m = medir(dentro, fora, 5, usar_rerank=False)
    print(f"| Só vetorial | {m['fonte']:.0%} | {m['recusa']:.0%} | {m['cobertura']:.0%} |")

    settings.hybrid_weight_bm25 = pesos_orig
    m = medir(dentro, fora, 5, usar_rerank=False)
    linha = f"{m['fonte']:.0%} | {m['recusa']:.0%} | {m['cobertura']:.0%}"
    print(f"| + BM25 (RRF), sem resgate | {linha} |")

    settings.bm25_rescue_min_idf = idf_orig
    m = medir(dentro, fora, 5, usar_rerank=False)
    print(f"| + resgate léxico | {m['fonte']:.0%} | {m['recusa']:.0%} | {m['cobertura']:.0%} |")

    m = medir(dentro, fora, 5, usar_rerank=True)
    linha = f"{m['fonte']:.0%} | {m['recusa']:.0%} | {m['cobertura']:.0%}"
    print(f"| + reranker cross-encoder | {linha} |")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--threshold", action="store_true")
    ap.add_argument("--k", action="store_true")
    ap.add_argument("--ablacao", action="store_true")
    args = ap.parse_args()
    todos = not (args.threshold or args.k or args.ablacao)

    dentro, fora = carregar()
    print(f"golden set: {GOLDEN_SET.name} — {len(dentro)} dentro do escopo, {len(fora)} fora")
    print(f"coleção: {settings.qdrant_collection} | curso: {settings.curso_nome}")
    print(f"retrieve_k={settings.retrieve_k} threshold={settings.score_threshold}")

    if todos or args.threshold:
        sweep_threshold(dentro, fora)
    if todos or args.k:
        sweep_final_k(dentro, fora)
    if todos or args.ablacao:
        sweep_ablacao(dentro, fora)
    return 0


if __name__ == "__main__":
    sys.exit(main())
