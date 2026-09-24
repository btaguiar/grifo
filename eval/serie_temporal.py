"""Série temporal das métricas de avaliação (plano de execução, Fase 4).

    python eval/serie_temporal.py

Lê todos os `metricas_*.json` com `serie: true`, ordena por timestamp e gera
`docs/serie-temporal.png`. O gráfico deriva dos dados versionados — nunca é desenhado
à mão (mesmo princípio do `grafico_calibracao.py`). Rodadas fora da configuração
canônica não têm `serie: true` e ficam de fora: séries comparáveis ou nada.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTADOS = Path(__file__).resolve().parent / "results"
SAIDA = REPO_ROOT / "docs" / "serie-temporal.png"

#: Mínimo para desenhar: dois pontos são uma reta, três é o primeiro formato que
#: mostra direção. O critério de aceite da Fase 4 pede pelo menos 3 pontos.
PONTOS_MINIMOS = 3


def carregar_serie() -> list[dict]:
    rodadas = []
    for caminho in sorted(RESULTADOS.glob("metricas_*.json")):
        import json

        try:
            dados = json.loads(caminho.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if dados.get("serie"):
            rodadas.append(dados)
    return sorted(rodadas, key=lambda d: d["timestamp"])


def _cobertura(rodada: dict) -> float | None:
    c = rodada["metricas"].get("cobertura_conteudo")
    return c["media"] if c else None


def desenhar(rodadas: list[dict]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    xs = [f"{r['timestamp'][:8]}\n{r.get('commit', '')}" for r in rodadas]
    pos = list(range(len(rodadas)))

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7.5), dpi=160, sharex=True)

    taxas = [
        ("recusa_correta", "Recusa correta", "#c0392b", "o"),
        ("fonte_correta_em_respondidas", "Fonte correta (end-to-end)", "#27ae60", "^"),
        ("citacao_em_respondidas", "Citação espontânea", "#8e44ad", "D"),
        ("taxa_resposta", "Taxa de resposta", "#2980b9", "s"),
    ]
    for chave, rotulo, cor, marcador in taxas:
        ys = [r["metricas"].get(chave) for r in rodadas]
        if all(y is not None for y in ys):
            ax1.plot(pos, ys, marker=marcador, color=cor, label=rotulo, linewidth=2)
    coberturas = [_cobertura(r) for r in rodadas]
    if all(c is not None for c in coberturas):
        ax1.plot(
            pos, coberturas, marker="v", color="#16a085", label="Cobertura de conteúdo", linewidth=2
        )
    ax1.set_ylim(0, 1.05)
    ax1.set_yticks([i / 10 for i in range(11)])
    ax1.set_ylabel("taxa")
    ax1.grid(alpha=0.25, linestyle="-", linewidth=0.6)
    ax1.legend(loc="lower right", fontsize=8, framealpha=0.95)

    p95 = [r["metricas"]["latency_p95_ms"] for r in rodadas]
    ax2.plot(pos, p95, marker="o", color="#e67e22", label="Latência p95", linewidth=2)
    ax2.axhline(3000, color="#c0392b", linestyle="--", linewidth=1.2)
    ax2.annotate(
        "meta 3s (NFR-1)", xy=(pos[0], 3000), xytext=(pos[0], 3150), fontsize=8, color="#c0392b"
    )
    ax2.set_ylabel("ms")
    ax2.grid(alpha=0.25, linestyle="-", linewidth=0.6)
    ax2.legend(loc="upper right", fontsize=8, framealpha=0.95)
    ax2.set_xticks(pos)
    ax2.set_xticklabels(xs, fontsize=8)

    custo = [r["metricas"].get("custo_usd") for r in rodadas]
    if all(c is not None for c in custo):
        ax_custo = ax2.twinx()
        ax_custo.plot(
            pos, custo, marker="s", color="#7f8c8d", linestyle=":", label="Custo US$/rodada"
        )
        ax_custo.set_ylabel("US$/rodada", fontsize=9, color="#7f8c8d")
        ax_custo.tick_params(axis="y", labelcolor="#7f8c8d")

    fig.suptitle(
        "Série temporal do eval — configuração canônica congelada",
        fontsize=11,
        fontweight="bold",
    )
    fig.text(
        0.5,
        0.005,
        "Só rodadas com serie: true. Fonte: eval/results/metricas_*.json.",
        ha="center",
        fontsize=8,
        color="#7f8c8d",
    )
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    SAIDA.parent.mkdir(exist_ok=True)
    fig.savefig(SAIDA)
    print(f"gráfico salvo em {SAIDA.relative_to(REPO_ROOT)} ({len(rodadas)} pontos)")


def main() -> int:
    rodadas = carregar_serie()
    if len(rodadas) < PONTOS_MINIMOS:
        print(
            f"erro: série tem {len(rodadas)} ponto(s); precisa de {PONTOS_MINIMOS}. "
            "Rode `python eval/run_eval.py` na configuração canônica para adicionar."
        )
        return 1
    desenhar(rodadas)
    return 0


if __name__ == "__main__":
    sys.exit(main())
