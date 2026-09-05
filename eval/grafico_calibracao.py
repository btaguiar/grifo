"""Gera o gráfico de calibração do threshold (SPEC seção 12, EVALUATION.md 4.1).

    python eval/grafico_calibracao.py

Os números NÃO são digitados aqui: a tabela 4.1 do EVALUATION.md é a fonte, e este
script a lê. Gráfico e texto não podem divergir, e recalibrar significa reescrever a
tabela e rodar isto de novo — nunca editar os dois à mão e torcer para baterem.

Falha alto se a tabela sumir ou mudar de formato: um gráfico gerado de dado que não é
mais o publicado é pior que gráfico nenhum.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EVALUATION = REPO_ROOT / "EVALUATION.md"
SAIDA = REPO_ROOT / "docs" / "calibracao-threshold.png"

#: Linha da tabela 4.1: | 0.45 (calibrado) | 75% | 55% | 100% |
_LINHA = re.compile(
    r"^\|\s*\**([\d.]+)\**\s*(\([^)]*\))?\**\s*\|"
    r"\s*\**(\d+)%\**\s*\|\s*\**(\d+)%\**\s*\|\s*\**(\d+)%\**\s*\|$"
)


def ler_tabela() -> list[dict]:
    """Extrai as linhas da tabela de threshold da seção 4.1."""
    texto = EVALUATION.read_text(encoding="utf-8")
    inicio = texto.index("### 4.1")
    trecho = texto[inicio : texto.index("### 4.2", inicio)]
    linhas = []
    for bruta in trecho.splitlines():
        m = _LINHA.match(bruta.strip())
        if m:
            thr, marca, fonte, recusa, cobertura = m.groups()
            linhas.append(
                {
                    "threshold": float(thr),
                    "marca": (marca or "").strip("()"),
                    "fonte": int(fonte),
                    "recusa": int(recusa),
                    "cobertura": int(cobertura),
                }
            )
    if len(linhas) < 5:
        raise SystemExit(
            f"erro: só {len(linhas)} linhas lidas da tabela 4.1 do EVALUATION.md. "
            "O formato mudou? O gráfico não pode ser gerado de dado incerto."
        )
    return sorted(linhas, key=lambda d: d["threshold"])


def desenhar(dados: list[dict]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    xs = [d["threshold"] for d in dados]
    partida = next((d for d in dados if d["marca"] == "partida"), None)
    calibrado = next((d for d in dados if d["marca"] == "calibrado"), None)

    fig, ax = plt.subplots(figsize=(9, 5.2), dpi=160)
    series = [
        ("recusa", "Recusa correta (gate de retrieval)", "#c0392b", "o"),
        ("cobertura", "Cobertura (perguntas no escopo)", "#2980b9", "s"),
        ("fonte", "Acerto de fonte @5", "#27ae60", "^"),
    ]
    for chave, rotulo, cor, marcador in series:
        ax.plot(
            xs, [d[chave] for d in dados], marker=marcador, color=cor, label=rotulo, linewidth=2
        )

    # As duas linhas verticais SAO o argumento: mesma cobertura, mesmo acerto de fonte,
    # e a recusa saltando. Sem elas o grafico e so tres curvas.
    for ponto, cor, estilo in ((partida, "#95a5a6", ":"), (calibrado, "#2c3e50", "--")):
        if ponto:
            ax.axvline(ponto["threshold"], color=cor, linestyle=estilo, linewidth=1.5)
            ax.annotate(
                f"{ponto['marca']}\n{ponto['threshold']:.2f}",
                xy=(ponto["threshold"], 103),
                ha="center",
                fontsize=9,
                color=cor,
                fontweight="bold",
            )

    if partida and calibrado:
        ax.annotate(
            f"recusa {partida['recusa']}% → {calibrado['recusa']}%\n"
            f"cobertura {partida['cobertura']}% → {calibrado['cobertura']}%",
            xy=(calibrado["threshold"], calibrado["recusa"]),
            xytext=(calibrado["threshold"] + 0.035, 34),
            fontsize=9,
            color="#2c3e50",
            arrowprops={"arrowstyle": "->", "color": "#2c3e50", "linewidth": 1.2},
        )

    ax.set_xlabel("SCORE_THRESHOLD")
    ax.set_ylabel("%")
    ax.set_title(
        "Calibração do threshold — 0.45 domina 0.35 nos dois eixos",
        fontsize=12,
        fontweight="bold",
    )
    ax.set_ylim(0, 112)
    ax.set_yticks(range(0, 101, 20))
    ax.set_xticks(xs)
    ax.grid(alpha=0.25, linestyle="-", linewidth=0.6)
    ax.legend(loc="center left", fontsize=9, framealpha=0.95)
    fig.text(
        0.5,
        0.005,
        "Corpus real, 64 itens do golden set. Só retrieval, sem LLM. Fonte: EVALUATION.md 4.1.",
        ha="center",
        fontsize=8,
        color="#7f8c8d",
    )
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    SAIDA.parent.mkdir(exist_ok=True)
    fig.savefig(SAIDA)
    print(f"gráfico salvo em {SAIDA.relative_to(REPO_ROOT)} ({len(dados)} pontos)")


def main() -> int:
    desenhar(ler_tabela())
    return 0


if __name__ == "__main__":
    sys.exit(main())
