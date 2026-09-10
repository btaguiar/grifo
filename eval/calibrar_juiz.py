"""Calibra o juiz de alucinação contra o conjunto de rótulos de referência.

    python eval/calibrar_juiz.py

Roda o `JUDGE_PROMPT` do run_eval contra `judge_calibration.jsonl` e reporta a matriz
de confusão completa, precisão, recall, taxa de falso positivo e o Kappa de Cohen —
que corrige a acurácia pelo acerto ao acaso, e é o número que diz se o juiz serve de
algo.

**O kappa sai separado por procedência do rótulo**, e ler os dois é obrigatório.
`humano` são casos que alguém leu e decidiu; `construcao` são casos cujo rótulo decorre
de como foram construídos e foi verificado por código (ver `confirmar_rotulos.py`).
Concordar com uma regra mecânica não é a mesma coisa que concordar com uma pessoa, e o
kappa global mistura as duas se a maioria for de um tipo só — daí a separação.

Por que kappa e não só acurácia: com 70% de casos "não alucinou" na calibração, um juiz
que respondesse NÃO incondicionalmente acertaria 70% — e não pegaria alucinação nenhuma.
A acurácia esconde isso; o kappa não, porque desconta o acordo esperado pelo acaso. Um
kappa de 0.70 é o piso que o plano de execução fixa para liberar a taxa de alucinação
sem revisão manual ("substancial" na escala de Landis & Koch, 1977 — a faixa
0.61-0.80). Abaixo disso a taxa sai publicada, mas acompanhada da ressalva.

Por que importa: a primeira versão do prompt perguntava "contém ALGUMA afirmação não
sustentada?" e reprovava paráfrase fiel. Num RAG quase toda resposta é reformulação, e
a taxa medida no corpus real saiu em 79,5% — quase toda ela falso positivo. Sem este
passo, aquele número teria ido para o README como se fosse medição.

Casos com `"rascunho": true` no JSONL não têm rótulo confirmado: são contados à parte e
NÃO entram nas métricas. O fluxo é gerar rascunhos, passar o `confirmar_rotulos.py`
(que promove só o que ele consegue verificar) e revisar à mão o que sobrar.

Rode isto sempre que trocar o modelo do juiz ou mexer no prompt — o resultado fica em
`eval/results/calibracao_juiz.json` e acompanha cada rodada no bloco `config` dos
`metricas_*.json`.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from grifo.config import settings  # noqa: E402
from run_eval import JUDGE_PROMPT, _llm_do_eval  # noqa: E402

CALIBRACAO = Path(__file__).resolve().parent / "judge_calibration.jsonl"
RESULTADO = Path(__file__).resolve().parent / "results" / "calibracao_juiz.json"

#: Piso para considerar o juiz liberado sem revisão manual. 0.70 vem da escala de
#: Landis & Koch (1977), faixa "substancial" 0.61-0.80: o plano de execução fixou o
#: ponto dentro da faixa onde o erro do juiz deixa de ser da mesma ordem do sinal.
KAPPA_PISO_PRODUCAO = 0.70

#: Procedencia do rotulo (ver eval/confirmar_rotulos.py).
HUMANO = "humano"


def prompt_sha256(prompt: str) -> str:
    """SHA-256 do prompt — identifica qual juiz produziu aquele kappa."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def carregar() -> list[dict]:
    return [
        json.loads(linha)
        for linha in CALIBRACAO.read_text(encoding="utf-8").splitlines()
        if linha.strip()
    ]


def matriz_de_confusao(rotulos: list[bool], vereditos: list[bool]) -> dict[str, int]:
    """Matriz completa tomando SIM (alucinou) como classe positiva.

    TP = juiz acusa e o rótulo confirma; FP = acusa paráfrase fiel de invenção
    (infla a taxa publicada); FN = deixa passar invenção (o erro perigoso);
    TN = aprova resposta fiel.
    """
    tp = sum(1 for r, v in zip(rotulos, vereditos, strict=True) if r and v)
    fp = sum(1 for r, v in zip(rotulos, vereditos, strict=True) if not r and v)
    fn = sum(1 for r, v in zip(rotulos, vereditos, strict=True) if r and not v)
    tn = sum(1 for r, v in zip(rotulos, vereditos, strict=True) if not r and not v)
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn}


def _razao(num: int, den: int) -> float | None:
    return num / den if den else None


def taxas_de_erro(m: dict[str, int]) -> dict[str, float | None]:
    """Precisão, recall e taxa de falso positivo a partir da matriz.

    None quando o denominador é zero — com zero casos positivos rotulados, recall e
    kappa são indefinidos, e publicar 0.0 no lugar seria inventar certeza.
    """
    return {
        "precisao": _razao(m["tp"], m["tp"] + m["fp"]),
        "recall": _razao(m["tp"], m["tp"] + m["fn"]),
        "taxa_falso_positivo": _razao(m["fp"], m["fp"] + m["tn"]),
        "acuracia": _razao(m["tp"] + m["tn"], m["tp"] + m["fp"] + m["fn"] + m["tn"]),
    }


def kappa_de_cohen(rotulos: list[bool], vereditos: list[bool]) -> float | None:
    """κ = (po - pe) / (1 - pe), com pe = acordo esperado pelo acaso.

    None quando pe = 1 — acontece se rótulo e veredito são constantes e concordantes
    (ex.: só casos negativos e juiz sempre NÃO). É o kappa indefinido, não 0 nem 1:
    o conjunto de calibração precisa das duas classes em quantidade.
    """
    n = len(rotulos)
    if n == 0:
        return None
    po = sum(1 for r, v in zip(rotulos, vereditos, strict=True) if r == v) / n
    p_rot_sim = sum(rotulos) / n
    p_ver_sim = sum(vereditos) / n
    pe = p_rot_sim * p_ver_sim + (1 - p_rot_sim) * (1 - p_ver_sim)
    if pe >= 1.0:
        return None
    return (po - pe) / (1 - pe)


def faixa_kappa(kappa: float) -> str:
    """Bandas de Landis & Koch (1977), só para rotular o número — não para julgá-lo."""
    if kappa < 0:
        return "pior que o acaso"
    if kappa <= 0.20:
        return "insignificante"
    if kappa <= 0.40:
        return "discreto"
    if kappa <= 0.60:
        return "moderado"
    if kappa <= 0.80:
        return "substancial"
    return "quase perfeito"


def _commit_hash() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=REPO_ROOT,
        ).stdout.strip()
    except Exception:
        return "sem-git"


def _fmt_taxa(v: float | None) -> str:
    return f"{v:.3f}" if v is not None else "indefinida"


def main() -> int:
    if not settings.openai_api_key:
        print("erro: OPENAI_API_KEY ausente — a calibração julga com LLM de verdade")
        return 2

    casos = carregar()
    confirmados = [c for c in casos if not c.get("rascunho")]
    rascunhos = [c for c in casos if c.get("rascunho")]
    juiz_modelo = settings.eval_llm_model or settings.llm_model
    llm = _llm_do_eval()
    print(f"juiz: {juiz_modelo} @ {settings.openai_base_url or 'openai'}")
    print(
        f"casos: {len(confirmados)} com rótulo confirmado"
        + (f" (+{len(rascunhos)} em rascunho, fora da conta)" if rascunhos else "")
        + "\n"
    )

    rotulos: list[bool] = []
    vereditos: list[bool] = []
    for c in confirmados:
        prompt = JUDGE_PROMPT.format(c=c["contexto"], q=c["question"], a=c["answer"])
        veredito = llm.invoke(prompt).content.strip().upper()
        julgou = veredito.startswith("SIM")
        rotulos.append(c["alucina"])
        vereditos.append(julgou)
        ok = julgou == c["alucina"]
        marca = "ok  " if ok else "ERRO"
        print(f"  {marca} {c['id']}  juiz={'SIM' if julgou else 'NÃO'}  {c['nota']}")

    m = matriz_de_confusao(rotulos, vereditos)
    taxas = taxas_de_erro(m)
    kappa = kappa_de_cohen(rotulos, vereditos)

    # Kappa por PROCEDÊNCIA do rótulo. Um kappa alto sobre rótulos derivados por
    # construção diz que o juiz concorda com uma regra mecânica — não que ele
    # concorda com uma pessoa. As duas coisas são diferentes e o relatório não pode
    # deixar quem lê confundir uma com a outra (ver eval/confirmar_rotulos.py).
    por_procedencia: dict[str, dict] = {}
    for origem in sorted({c.get("procedencia", "humano") for c in confirmados}):
        idx = [i for i, c in enumerate(confirmados) if c.get("procedencia", "humano") == origem]
        sub_rot = [rotulos[i] for i in idx]
        sub_ver = [vereditos[i] for i in idx]
        sub_m = matriz_de_confusao(sub_rot, sub_ver)
        sub_k = kappa_de_cohen(sub_rot, sub_ver)
        por_procedencia[origem] = {
            "n": len(idx),
            "kappa": round(sub_k, 4) if sub_k is not None else None,
            "matriz": sub_m,
            **{k: round(v, 4) if v is not None else None for k, v in taxas_de_erro(sub_m).items()},
        }

    print("\nmatriz de confusão (positivo = alucinou):")
    print(f"  TP {m['tp']}   FP {m['fp']}   FN {m['fn']}   TN {m['tn']}")
    print(
        f"precisão {_fmt_taxa(taxas['precisao'])}   "
        f"recall {_fmt_taxa(taxas['recall'])}   "
        f"taxa de falso positivo {_fmt_taxa(taxas['taxa_falso_positivo'])}   "
        f"acurácia {_fmt_taxa(taxas['acuracia'])}"
    )
    if kappa is None:
        print(
            "kappa: indefinido — rótulo e veredito constantes; faltam casos positivos ou negativos"
        )
    else:
        print(f"kappa de Cohen: {kappa:.3f} ({faixa_kappa(kappa)})")
        if kappa < KAPPA_PISO_PRODUCAO:
            print(
                f"  abaixo do piso de {KAPPA_PISO_PRODUCAO}: a taxa de alucinação NÃO está\n"
                "  liberada para produção sem revisão manual — publique com esta ressalva"
            )
    print("\npor procedência do rótulo:")
    for origem, bloco in por_procedencia.items():
        k = f"{bloco['kappa']:.3f}" if bloco["kappa"] is not None else "indefinido"
        print(f"  {origem:11} n={bloco['n']:3}  kappa={k}")
    n_humano = por_procedencia.get("humano", {}).get("n", 0)
    if n_humano < len(confirmados) / 2:
        print(
            f"  ATENÇÃO: só {n_humano} de {len(confirmados)} rótulos vieram de revisão\n"
            "  humana. O kappa global mede sobretudo o acordo do juiz com uma regra\n"
            "  mecânica de construção, não com uma pessoa — publique a procedência junto."
        )

    if m["fn"]:
        print("\nATENÇÃO: falso negativo é o erro perigoso — a taxa sai boa por omissão.")

    bloco = {
        "timestamp": datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"),
        "commit": _commit_hash(),
        "juiz": {
            "modelo": juiz_modelo,
            "prompt_sha256": prompt_sha256(JUDGE_PROMPT),
            "n_casos": len(confirmados),
            "kappa": round(kappa, 4) if kappa is not None else None,
            "matriz": m,
            **{k: round(v, 4) if v is not None else None for k, v in taxas.items()},
            #: De onde vieram os rótulos contra os quais este kappa foi medido.
            #: Sem isto o número viaja para o `metricas_*.json` sem dizer se o juiz
            #: concordou com uma pessoa ou com uma regra de construção.
            "por_procedencia": por_procedencia,
        },
        "rascunhos_pendentes": len(rascunhos),
        #: Veredito por caso. A matriz agregada diz QUANTO o juiz erra; só o detalhe
        #: diz ONDE — e sem ele a análise do padrão de falha exige rodar tudo de novo.
        #: Não carrega texto do curso: só id, rótulo, veredito e procedência.
        "vereditos": [
            {
                "id": c["id"],
                "rotulo": r,
                "juiz": v,
                "procedencia": c.get("procedencia", HUMANO),
                "nota": c["nota"],
            }
            for c, r, v in zip(confirmados, rotulos, vereditos, strict=True)
        ],
    }
    RESULTADO.parent.mkdir(exist_ok=True)
    RESULTADO.write_text(json.dumps(bloco, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\ncalibração de registro salva em {RESULTADO}")
    return 0 if m["tp"] + m["tn"] == len(confirmados) else 1


if __name__ == "__main__":
    sys.exit(main())
