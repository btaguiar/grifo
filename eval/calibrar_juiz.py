"""Calibra o juiz de alucinação contra um conjunto rotulado à mão.

    python eval/calibrar_juiz.py

O EVALUATION.md exige "amostra revisada à mão para calibrar o juiz". Este script torna
isso reproduzível: roda o `JUDGE_PROMPT` do run_eval contra `judge_calibration.jsonl` e
reporta a acurácia, separando falso positivo de falso negativo.

Por que importa: a primeira versão do prompt perguntava "contém ALGUMA afirmação não
sustentada?" e reprovava paráfrase fiel. Num RAG quase toda resposta é reformulação, e
a taxa medida no corpus real saiu em 79,5% — quase toda ela falso positivo. Sem este
passo, aquele número teria ido para o README como se fosse medição.

Rode isto sempre que trocar o modelo do juiz ou mexer no prompt.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from grifo.config import settings  # noqa: E402
from run_eval import JUDGE_PROMPT, _llm_do_eval  # noqa: E402

CALIBRACAO = Path(__file__).resolve().parent / "judge_calibration.jsonl"


def carregar() -> list[dict]:
    return [
        json.loads(linha)
        for linha in CALIBRACAO.read_text(encoding="utf-8").splitlines()
        if linha.strip()
    ]


def main() -> int:
    casos = carregar()
    llm = _llm_do_eval()
    print(f"juiz: {settings.llm_model} @ {settings.openai_base_url or 'openai'}")
    print(f"casos: {len(casos)} rotulados à mão\n")

    acertos = falso_pos = falso_neg = 0
    for c in casos:
        prompt = JUDGE_PROMPT.format(c=c["contexto"], q=c["question"], a=c["answer"])
        veredito = llm.invoke(prompt).content.strip().upper()
        julgou_alucinacao = veredito.startswith("SIM")
        ok = julgou_alucinacao == c["alucina"]
        acertos += ok
        if not ok and julgou_alucinacao:
            falso_pos += 1  # acusou invenção onde havia só paráfrase
        elif not ok:
            falso_neg += 1  # deixou passar invenção
        marca = "ok  " if ok else "ERRO"
        print(f"  {marca} {c['id']}  juiz={'SIM' if julgou_alucinacao else 'NÃO'}  {c['nota']}")

    print(f"\nacurácia: {acertos}/{len(casos)}")
    print(f"  falso positivo (acusa paráfrase de invenção): {falso_pos}  -> infla a taxa")
    print(f"  falso negativo (deixa passar invenção)      : {falso_neg}  -> esconde o problema")
    if falso_neg:
        print("\nATENÇÃO: falso negativo é o erro perigoso — a taxa sai boa por omissão.")
    return 0 if acertos == len(casos) else 1


if __name__ == "__main__":
    sys.exit(main())
