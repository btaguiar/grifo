"""Gate de regressão contra a última rodada da série (plano de execução, Fase 4).

    python eval/gate_regressao.py [metricas_novo.json]

Compara a rodada recém-gerada contra a última anterior da série (`serie: true`) e
falha (exit 1) se:

  - recusa_correta cair mais de 5 pontos percentuais;
  - alucinacao subir mais de 2 pontos percentuais;
  - latency_p95_ms ultrapassar 3000ms (absoluto — é o NFR-1, não comparação).

Os dois primeiros são relativos à última rodada: capturam regressão mesmo com as
metas absolutas todas verdes. O terceiro é a meta do NFR-1 — um PR que degrada a
latência reprova sem intervenção humana, que é o critério de aceite da Fase 4.

Exit 2 quando não existe série anterior para comparar (primeira rodada da série): o
gate não reprova o que não tem contra quê medir — mas o p95 absoluto ainda vale.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTADOS = Path(__file__).resolve().parent / "results"

#: Tolerâncias do plano Fase 4. 5pp de recusa e 2pp de alucinação: folga para o ruído
#: de LLM (temperature=0 não é determinístico entre provedores) sem esconder queda
#: real. 3000ms é o NFR-1 da SPEC.
QUEDA_MAX_RECUSA = 0.05
SUBIDA_MAX_ALUCINACAO = 0.02
TETO_P95_MS = 3000


def carregar_serie() -> list[dict]:
    """Todos os metricas_*.json da série, ordenados por timestamp."""
    rodadas = []
    for caminho in sorted(RESULTADOS.glob("metricas_*.json")):
        try:
            dados = json.loads(caminho.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if dados.get("serie"):
            rodadas.append(dados)
    return sorted(rodadas, key=lambda d: d["timestamp"])


def comparar(nova: dict, anterior: dict | None) -> list[str]:
    """Lista de regressões encontradas — vazia é aprovação."""
    falhas: list[str] = []
    m_nova, m_ant = nova["metricas"], (anterior or {}).get("metricas", {})

    if m_nova["latency_p95_ms"] >= TETO_P95_MS:
        falhas.append(f"p95 {m_nova['latency_p95_ms']:.0f}ms >= {TETO_P95_MS}ms (NFR-1)")

    if anterior is None:
        return falhas

    recusa_nova, recusa_ant = m_nova.get("recusa_correta"), m_ant.get("recusa_correta")
    if (
        recusa_nova is not None
        and recusa_ant is not None
        and recusa_nova < recusa_ant - QUEDA_MAX_RECUSA
    ):
        falhas.append(
            f"recusa_correta {recusa_nova:.3f} caiu "
            f"{(recusa_ant - recusa_nova) * 100:.1f}pp desde {recusa_ant:.3f} "
            f"(tolerância {QUEDA_MAX_RECUSA * 100:.0f}pp)"
        )

    alu_nova, alu_ant = m_nova.get("alucinacao"), m_ant.get("alucinacao")
    if alu_nova is not None and alu_ant is not None and alu_nova > alu_ant + SUBIDA_MAX_ALUCINACAO:
        falhas.append(
            f"alucinacao {alu_nova:.3f} subiu "
            f"{(alu_nova - alu_ant) * 100:.1f}pp desde {alu_ant:.3f} "
            f"(tolerância {SUBIDA_MAX_ALUCINACAO * 100:.0f}pp)"
        )
    return falhas


def main() -> int:
    serie = carregar_serie()
    if not serie:
        print("erro: nenhuma rodada com serie: true para comparar")
        return 2

    if len(sys.argv) > 1:
        nova = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    else:
        nova = serie[-1]

    anteriores = [r for r in serie if r["timestamp"] < nova["timestamp"]]
    anterior = anteriores[-1] if anteriores else None

    origem = anterior["timestamp"] if anterior else "nenhuma (primeira rodada da série)"
    print(f"rodada nova: {nova['timestamp']} @ {nova.get('commit')}")
    print(f"comparando com: {origem}\n")

    falhas = comparar(nova, anterior)
    if falhas:
        print("REPROVADO — regressão:")
        for f in falhas:
            print(f"  - {f}")
        return 1
    print("APROVADO — sem regressão contra a série")
    return 0


if __name__ == "__main__":
    sys.exit(main())
