"""Promove rascunho a rótulo confirmado por VERIFICAÇÃO — nunca por opinião.

    python eval/confirmar_rotulos.py [--aplicar]

Sem `--aplicar` só relata; com ele reescreve o `judge_calibration.jsonl`.

O plano de execução previa revisão humana caso a caso dos 93 rascunhos. Este script
faz uma coisa diferente e mais estreita, e a diferença precisa ficar registrada no
dado: ele confirma o rótulo **que decorre de como o caso foi construído**, quando esse
rótulo é mecanicamente verificável sob a regra de fronteira do EVALUATION 3.2 (só fato
novo ausente dos trechos conta como alucinação). O que não passa no próprio invariante
NÃO é confirmado — fica em rascunho, esperando um humano.

Por isso cada caso passa a carregar `procedencia`:

    "humano"      alguém leu o caso e decidiu o rótulo
    "construcao"  o rótulo decorre da construção e foi verificado por código

A distinção não é burocracia. Kappa mede acordo entre o juiz e um rotulador; se o
rotulador for um processo automático, o número mede outra coisa, e quem lê tem de
saber qual. `calibrar_juiz.py` reporta o kappa separado por procedência.

Invariante de cada família:

  injetado (SIM)      o marcador do fato novo está NA resposta e AUSENTE do contexto.
                      É a mesma guarda que o gerador já aplica, reaplicada aqui sobre
                      o dado final — o rótulo `true` decorre disso e de nada mais.

  fiel, paráfrase     nenhum número ou nome próprio da resposta falta no contexto
  (NÃO)               (`tokens_ausentes`). Sob a regra de fronteira, é o que
                      significa "não afirmou fato novo".

**A limitação, que vai publicada junto com o número:** a verificação é lexical. Ela não
pega afirmação inventada que use só palavras já presentes no contexto — inverter uma
relação, trocar causa por consequência, atribuir a A o que o trecho diz de B. Um
conjunto confirmado assim testa o juiz contra fabricação detectável, não contra a
distribuição real de erro de um LLM. Os casos de procedência humana continuam sendo os
únicos que cobrem esse eixo.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from gerar_rascunhos_calibracao import INJETADOS  # noqa: E402
from triagem_calibracao import (  # noqa: E402
    CALIBRACAO,
    carregar,
    familia,
    item_de_origem,
    normalizar,
    tokens_ausentes,
)

#: Procedência de um rótulo. Fica no JSONL, viaja para o `calibracao_juiz.json` e
#: chega ao bloco `config` de cada rodada — quem lê o kappa vê de onde vieram os rótulos.
HUMANO = "humano"
CONSTRUCAO = "construcao"


def verificar(caso: dict) -> tuple[bool, str]:
    """(o rótulo proposto se sustenta?, motivo quando não)."""
    fam = familia(caso["nota"])
    if fam == "injetado":
        gs = item_de_origem(caso["nota"])
        entrada = INJETADOS.get(gs or "")
        if entrada is None:
            return False, f"sem marcador registrado para {gs}"
        marcador = normalizar(entrada[1])
        if marcador not in normalizar(caso["answer"]):
            return False, f"marcador {entrada[1]!r} não está na resposta"
        if marcador in normalizar(caso["contexto"]):
            return False, f"marcador {entrada[1]!r} EXISTE no contexto — não é fato novo"
        if not caso["alucina"]:
            return False, "família injetado com rótulo NÃO"
        return True, ""

    if fam in ("fiel", "parafrase"):
        if caso["alucina"]:
            return False, f"família {fam} com rótulo SIM"
        fora = tokens_ausentes(caso["answer"], caso["contexto"])
        if fora:
            return False, f"token(s) fora do contexto: {fora}"
        return True, ""

    return False, f"família '{fam}' não tem invariante de construção"


def main() -> int:
    aplicar = "--aplicar" in sys.argv
    casos = carregar()

    confirmados = 0
    pendentes: list[tuple[str, str]] = []
    for caso in casos:
        if not caso.get("rascunho"):
            caso.setdefault("procedencia", HUMANO)
            continue
        ok, motivo = verificar(caso)
        if ok:
            caso.pop("rascunho", None)
            caso["procedencia"] = CONSTRUCAO
            confirmados += 1
        else:
            pendentes.append((caso["id"], motivo))

    humanos = sum(1 for c in casos if c.get("procedencia") == HUMANO)
    print(f"{len(casos)} casos em {CALIBRACAO.name}")
    print(f"  procedência humano ......... {humanos}")
    print(f"  procedência construção ..... {confirmados}")
    print(f"  ainda em rascunho .......... {len(pendentes)}")

    if pendentes:
        print("\nNÃO confirmados — o invariante não se sustenta, precisam de um humano:")
        for cid, motivo in pendentes:
            print(f"  {cid}  {motivo}")

    if not aplicar:
        print("\n(relatório apenas — rode com --aplicar para gravar)")
        return 0

    CALIBRACAO.write_text(
        "\n".join(json.dumps(c, ensure_ascii=False) for c in casos) + "\n",
        encoding="utf-8",
    )
    print(f"\ngravado em {CALIBRACAO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
