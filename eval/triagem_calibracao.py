"""Triagem do conjunto de calibração do juiz — sem LLM, sem custo, determinística.

    python eval/triagem_calibracao.py

O `calibrar_juiz.py` mede o juiz contra os rótulos. Este script mede **os rótulos**:
um conjunto de calibração fabricado pode produzir um kappa alto por motivo errado, e
nenhuma métrica do relatório denuncia isso. Rode antes de publicar qualquer kappa.

O que ele checa, e por que cada coisa importa:

  assinatura de superfície  A classe positiva se separa da negativa SEM ler o
        contexto? Medido em 2026-09-06 no conjunto de 93 rascunhos: 67% dos casos
        `alucina=true` terminam numa frase que abre com fórmula de atribuição ("O
        material recomenda...", "A aula sugere..."), contra 2% dos negativos — e os
        positivos são sistematicamente mais curtos (223 contra 347 chars de média).
        Duas pistas de forma que um juiz pode aprender no lugar da substância. É a
        única checagem que REPROVA: um conjunto assim mede a forma da fabricação.

  n efetivo   Kappa assume itens independentes. Os rascunhos reaproveitam o mesmo
        contexto em até três famílias (fiel / paráfrase / injetado): são 99 casos
        sobre ~33 contextos, e itens que compartilham contexto erram juntos. O número
        de contextos distintos é o que deve ser publicado ao lado do kappa.

  fato novo em paráfrase   Paráfrase é rotulada `alucina=false`. Se a reescrita à mão
        injetou um número ou nome que não está no contexto, o rótulo virou falso
        negativo no GABARITO — o erro perigoso, porque ensina o kappa a premiar a
        omissão. Esta checagem over-reporta de propósito: é triagem, e o custo de um
        falso alarme é ler uma linha.

  positivo tardio   Fato novo pendurado na última frase é positivo fácil demais.
        Alucinação real vem tecida no meio da resposta.

Não substitui a revisão humana dos rascunhos: ordena o que revisar primeiro.
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CALIBRACAO = REPO_ROOT / "eval" / "judge_calibration.jsonl"
RESULTADOS = REPO_ROOT / "eval" / "results"

#: Aberturas que atribuem a afirmação ao material. Injetar fato novo quase sempre pede
#: uma delas ("segundo a aula, X"), então algum excesso na classe positiva é natural —
#: o que não é natural é o excesso virar pista suficiente.
FORMULAS_DE_ATRIBUICAO = ("o material", "a aula", "segundo a aula", "na pratica", "o curso")

#: Diferença tolerada entre as taxas de fórmula das duas classes. 0.25 deixa passar a
#: assimetria intrínseca acima e reprova a medida de 2026-09-06 (65pp), que é o estado
#: que motivou este script. Recalibrar exige remedir as duas taxas, não afrouxar aqui.
GAP_MAXIMO_FORMULA = 0.25

#: Faixa tolerada para (tamanho mediano dos positivos ÷ dos negativos). Fora dela, o
#: comprimento sozinho separa as classes. Medido em 2026-09-06: 0.64.
RAZAO_TAMANHO_MINIMA = 0.75
RAZAO_TAMANHO_MAXIMA = 1.33

#: Prefixo usado para casar palavra flexionada com a do contexto ("Corrige" com
#: "Corrigir"). Mesmo tamanho do stem do `analytics.question_log`, pelo mesmo motivo:
#: é grosseiro e suficiente para separar morfologia de fato novo.
STEM = 5

#: Número ou palavra Capitalizada: é onde fato novo se esconde (data, percentual,
#: nome de empresa, autor). Verbo em início de frase também casa — daí o over-report.
_TOKEN_DURO = re.compile(r"\d+(?:[.,]\d+)?%?|\b[A-ZÀ-Þ][A-Za-zÀ-ÿ]{2,}\b")
_FIM_DE_FRASE = re.compile(r"(?<=[.!?])\s+")
_ORIGEM = re.compile(r"(gs-\d+)")
#: `[Módulo 2, Aula 4]` — etiqueta, não afirmação. O `judge.txt` também a ignora.
_CITACAO = re.compile(r"\[[^\]]*\]")


def normalizar(texto: str) -> str:
    """Casefold sem acento — a mesma regra da cobertura de conteúdo do `run_eval`."""
    decomposto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in decomposto if unicodedata.category(c) != "Mn").casefold()


def carregar(caminho: Path = CALIBRACAO) -> list[dict]:
    return [
        json.loads(linha)
        for linha in caminho.read_text(encoding="utf-8").splitlines()
        if linha.strip()
    ]


def familia(nota: str) -> str:
    """Família do caso, lida da `nota` que o gerador escreveu.

    O gerador não grava o campo, e derivar da nota é frágil de propósito: se a nota
    mudar de formato, o caso cai em "outro" e aparece no relatório em vez de ser
    contado errado em silêncio.
    """
    n = normalizar(nota)
    if n.startswith("resposta real"):
        return "fiel"
    if n.startswith("parafrase"):
        return "parafrase"
    if n.startswith("fato novo"):
        return "injetado"
    return "outro"


def item_de_origem(nota: str) -> str | None:
    """Id do golden set que deu origem ao caso, quando a nota o registra."""
    m = _ORIGEM.search(nota)
    return m.group(1) if m else None


def frases(texto: str) -> list[str]:
    return [f.strip() for f in _FIM_DE_FRASE.split(texto) if f.strip()]


def tokens_ausentes(resposta: str, contexto: str) -> list[str]:
    """Números e nomes próprios da resposta que não aparecem no contexto.

    Três filtros, cada um por um motivo:

    * marcação de citação (`[Módulo 2, Aula 4]`) sai antes de tudo — o próprio
      `judge.txt` manda ignorá-la, e sem isso o "2" e o "4" da etiqueta viram
      "número ausente do contexto" em toda resposta bem formada;
    * palavra capitalizada em INÍCIO de frase é ignorada: o português capitaliza por
      posição, não por ser nome próprio, e era daí que vinha quase todo falso alarme
      ("Somar", "Cortar", "Porque"). Nome próprio injetado aparece no meio da frase
      ("cita a Netflix", "por Fred Reichheld") e continua sendo pego;
    * flexão casa por prefixo de `STEM` caracteres ("Corrige" contra "Corrigir").

    Número conta em qualquer posição. Ainda assim a checagem over-reporta: é triagem,
    e o custo de um falso alarme é ler uma linha.
    """
    ctx = normalizar(contexto)
    ctx_stems = {p[:STEM] for p in re.findall(r"[a-z0-9]+", ctx)}
    fora = set()
    for frase in frases(_CITACAO.sub(" ", resposta)):
        for posicao, palavra in enumerate(frase.split()):
            for token in _TOKEN_DURO.findall(palavra):
                if posicao == 0 and not token[0].isdigit():
                    continue
                alvo = normalizar(token)
                if alvo in ctx or alvo[:STEM] in ctx_stems:
                    continue
                fora.add(token)
    return sorted(fora)


def abre_com_atribuicao(frase: str) -> bool:
    return normalizar(frase).lstrip().startswith(FORMULAS_DE_ATRIBUICAO)


def assinatura_de_superficie(casos: list[dict]) -> dict:
    """As duas pistas de forma, por classe. Chaves `_ok` dizem se passam do limite."""
    pos = [c for c in casos if c["alucina"]]
    neg = [c for c in casos if not c["alucina"]]
    if not pos or not neg:
        return {"medivel": False}

    def taxa(grupo: list[dict]) -> float:
        return sum(1 for c in grupo if abre_com_atribuicao(frases(c["answer"])[-1])) / len(grupo)

    def mediana_chars(grupo: list[dict]) -> float:
        tamanhos = sorted(len(c["answer"]) for c in grupo)
        meio = len(tamanhos) // 2
        if len(tamanhos) % 2:
            return float(tamanhos[meio])
        return (tamanhos[meio - 1] + tamanhos[meio]) / 2

    taxa_pos, taxa_neg = taxa(pos), taxa(neg)
    med_pos, med_neg = mediana_chars(pos), mediana_chars(neg)
    razao = med_pos / med_neg if med_neg else 0.0
    return {
        "medivel": True,
        "n_positivos": len(pos),
        "n_negativos": len(neg),
        "taxa_formula_positivos": round(taxa_pos, 4),
        "taxa_formula_negativos": round(taxa_neg, 4),
        "gap_formula": round(abs(taxa_pos - taxa_neg), 4),
        "gap_ok": abs(taxa_pos - taxa_neg) <= GAP_MAXIMO_FORMULA,
        "mediana_chars_positivos": med_pos,
        "mediana_chars_negativos": med_neg,
        "razao_tamanho": round(razao, 4),
        "tamanho_ok": RAZAO_TAMANHO_MINIMA <= razao <= RAZAO_TAMANHO_MAXIMA,
    }


def n_efetivo(casos: list[dict]) -> dict:
    """Casos contra contextos distintos — o denominador honesto do kappa."""
    contextos = {normalizar(c["contexto"]) for c in casos}
    return {
        "casos": len(casos),
        "contextos_distintos": len(contextos),
        "casos_por_contexto": round(len(casos) / len(contextos), 2) if contextos else 0.0,
    }


def _faithfulness_por_item() -> dict[str, float]:
    """`ragas_faithfulness` por item da rodada mais recente que o gravou.

    Os `eval_*.json` completos são locais (carregam o texto dos chunks). Sem eles a
    checagem simplesmente não aparece no relatório — não é erro.
    """
    for caminho in sorted(RESULTADOS.glob("eval_*.json"), reverse=True):
        try:
            dados = json.loads(caminho.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        valores = {
            i["id"]: i["ragas_faithfulness"]
            for i in dados.get("itens", [])
            if i.get("ragas_faithfulness") is not None
        }
        if valores:
            return valores
    return {}


def _secao(titulo: str) -> None:
    print(f"\n{titulo}\n{'-' * len(titulo)}")


def main() -> int:
    casos = carregar()
    rascunhos = [c for c in casos if c.get("rascunho")]
    confirmados = [c for c in casos if not c.get("rascunho")]
    print(f"{len(casos)} casos em {CALIBRACAO.name}: ", end="")
    print(f"{len(confirmados)} confirmados, {len(rascunhos)} em rascunho")

    _secao("composição")
    for fam, n in Counter(familia(c["nota"]) for c in casos).most_common():
        positivos = sum(1 for c in casos if familia(c["nota"]) == fam and c["alucina"])
        print(f"  {fam:10} {n:3}  ({positivos} positivos)")

    ef = n_efetivo(casos)
    _secao("n efetivo")
    print(f"  {ef['casos']} casos sobre {ef['contextos_distintos']} contextos distintos")
    print(f"  {ef['casos_por_contexto']} casos por contexto")
    if ef["casos_por_contexto"] > 1.5:
        print("  publique o kappa como 'n casos sobre C contextos': itens que")
        print("  compartilham contexto não são independentes e o kappa assume que são")

    sa = assinatura_de_superficie(casos)
    _secao("assinatura de superfície")
    if not sa["medivel"]:
        print("  indefinida — falta uma das classes")
    else:
        print(
            f"  fórmula de atribuição na última frase: "
            f"{sa['taxa_formula_positivos']:.0%} dos positivos contra "
            f"{sa['taxa_formula_negativos']:.0%} dos negativos "
            f"(gap {sa['gap_formula']:.0%}, teto {GAP_MAXIMO_FORMULA:.0%})"
        )
        print(
            f"  tamanho mediano: {sa['mediana_chars_positivos']:.0f} contra "
            f"{sa['mediana_chars_negativos']:.0f} chars "
            f"(razão {sa['razao_tamanho']:.2f}, faixa "
            f"{RAZAO_TAMANHO_MINIMA:.2f} a {RAZAO_TAMANHO_MAXIMA:.2f})"
        )

    _secao("fato novo em paráfrase (rótulo 'não alucina' sob suspeita)")
    suspeitas = 0
    for c in casos:
        if familia(c["nota"]) != "parafrase":
            continue
        fora = tokens_ausentes(c["answer"], c["contexto"])
        if fora:
            suspeitas += 1
            print(f"  {c['id']}  ausentes do contexto: {fora}")
    print(f"  {suspeitas} para conferir (a checagem over-reporta: ver docstring)")

    _secao("positivo tardio (fato novo na última frase)")
    tardios = [
        c["id"]
        for c in casos
        if c["alucina"]
        and (fr := frases(c["answer"]))
        and len(fr) > 1
        and tokens_ausentes(fr[-1], c["contexto"])
    ]
    print(f"  {len(tardios)} de {sum(1 for c in casos if c['alucina'])} positivos")
    if tardios:
        print(f"  {', '.join(tardios)}")

    faith = _faithfulness_por_item()
    if faith:
        _secao("fiéis com faithfulness baixo (rótulo merece desconfiança)")
        achou = False
        for c in sorted(casos, key=lambda x: x["id"]):
            if familia(c["nota"]) != "fiel" or c["alucina"]:
                continue
            gs = item_de_origem(c["nota"])
            valor = faith.get(gs or "")
            if valor is not None and valor < 0.80:
                achou = True
                print(f"  {c['id']}  {gs}  faithfulness={valor:.2f}")
        if not achou:
            print("  nenhum")

    _secao("veredito")
    if not sa["medivel"]:
        print("  INDEFINIDO — conjunto sem uma das classes")
        return 1
    problemas = []
    if not sa["gap_ok"]:
        problemas.append(f"gap de fórmula {sa['gap_formula']:.0%} > {GAP_MAXIMO_FORMULA:.0%}")
    if not sa["tamanho_ok"]:
        problemas.append(f"razão de tamanho {sa['razao_tamanho']:.2f} fora da faixa")
    if problemas:
        print("  REPROVADO — a classe positiva é separável sem ler o contexto:")
        for p in problemas:
            print(f"    - {p}")
        print("  o kappa medido assim mede a forma da fabricação, não o juiz")
        return 1
    print("  APROVADO — nenhuma pista de forma separa as classes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
