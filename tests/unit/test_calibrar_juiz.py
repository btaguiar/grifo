"""Calibração do juiz como funções puras (testáveis sem API key).

Kappa de Cohen, matriz de confusão e as taxas de erro — o que a Fase 1 do plano de
execução adicionou ao `calibrar_juiz.py`. Os valores de referência dos testes de kappa
foram calculados à mão a partir da fórmula κ = (po - pe) / (1 - pe).
"""

import pytest
from eval.calibrar_juiz import (
    KAPPA_PISO_PRODUCAO,
    faixa_kappa,
    kappa_de_cohen,
    matriz_de_confusao,
    taxas_de_erro,
)


def test_matriz_de_confusao_completa():
    rotulos = [True, True, False, False, True, False]
    vereditos = [True, False, True, False, True, False]
    m = matriz_de_confusao(rotulos, vereditos)
    # TP: 2 (acusa os 1º e 5º) | FN: 1 (2º é invenção não vista)
    # FP: 1 (3º é fiel acusado) | TN: 2
    assert m == {"tp": 2, "fp": 1, "fn": 1, "tn": 2}


def test_kappa_acordo_perfeito_e_um():
    rotulos = [True, False, True, True, False]
    assert kappa_de_cohen(rotulos, list(rotulos)) == pytest.approx(1.0)


def test_kappa_acordo_de_puro_acaso_e_zero():
    # po = 0.5 e marginais equilibradas → pe = 0.5 → κ = 0
    rotulos = [True, True, False, False]
    vereditos = [True, False, True, False]
    assert kappa_de_cohen(rotulos, vereditos) == pytest.approx(0.0)


def test_kappa_discordancia_total_e_menos_um():
    rotulos = [True, True, False, False]
    vereditos = [not r for r in rotulos]
    assert kappa_de_cohen(rotulos, vereditos) == pytest.approx(-1.0)


def test_kappa_valor_de_referencia_calculado_a_mao():
    # po = 4/6; marginais 3/6 sim em ambos → pe = 0.5; κ = (0.667 - 0.5)/0.5 ≈ 0.333
    rotulos = [True, True, True, False, False, False]
    vereditos = [True, True, False, True, False, False]
    assert kappa_de_cohen(rotulos, vereditos) == pytest.approx(1 / 3, abs=1e-3)


def test_kappa_indefinido_sem_classe_positiva():
    """Só casos negativos com juiz sempre NÃO: pe = 1, kappa indefinido — não 1.0.

    É a armadilha que o plano chama: sem casos positivos suficientes o kappa é
    indefinido; publicar 1.0 aqui seria o mesmo que declarar o juiz perfeito por
    nunca ter tido a chance de errar.
    """
    rotulos = [False] * 10
    vereditos = [False] * 10
    assert kappa_de_cohen(rotulos, vereditos) is None
    assert kappa_de_cohen([], []) is None


def test_kappa_corrige_acuracia_inflada_por_classe_dominante():
    """98% de acurácia com juiz que nunca acusa: kappa tem que cair a zero.

    98 casos fiéis + 2 injetados; juiz responde NÃO sempre → po = 0.98, mas pe
    também é 0.98 (o acaso acertaria o mesmo copiando a maioria). κ = 0: acordo
    nulo — o juiz não adiciona informação nenhuma, e a acurácia de 0.98 não pode
    ser publicada como confiabilidade.
    """
    rotulos = [False] * 98 + [True] * 2
    vereditos = [False] * 100
    taxas = taxas_de_erro(matriz_de_confusao(rotulos, vereditos))
    assert taxas["acuracia"] == pytest.approx(0.98)
    assert taxas["recall"] == 0.0
    kappa = kappa_de_cohen(rotulos, vereditos)
    assert kappa == pytest.approx(0.0)


def test_taxas_de_erro_divisao_por_zero_e_indefinida():
    # matriz sem positivo rotulado: recall indefinido, não 0.0
    taxas = taxas_de_erro({"tp": 0, "fp": 2, "fn": 0, "tn": 8})
    assert taxas["precisao"] == 0.0
    assert taxas["recall"] is None
    assert taxas["taxa_falso_positivo"] == pytest.approx(0.2)


def test_faixas_de_kappa_landis_koch():
    assert faixa_kappa(-0.1) == "pior que o acaso"
    assert faixa_kappa(0.1) == "insignificante"
    assert faixa_kappa(0.3) == "discreto"
    assert faixa_kappa(0.5) == "moderado"
    assert faixa_kappa(0.7) == "substancial"
    assert faixa_kappa(0.95) == "quase perfeito"


def test_piso_de_producao_e_zero_setenta():
    """O piso 0.70 está dentro de 'substancial' (0.61-0.80) na escala citada."""
    assert KAPPA_PISO_PRODUCAO == 0.70
    assert faixa_kappa(KAPPA_PISO_PRODUCAO) == "substancial"


def test_registro_do_eval_carrega_o_bloco_do_juiz(tmp_path, monkeypatch):
    """Fase 1: o `metricas_*.json` carrega a confiabilidade do juiz da rodada.

    Sem o bloco, um kappa medido num prompt antigo seria lido como se valesse para
    o atual — o número de alucinação perderia o lastro.
    """
    import json

    from eval import run_eval

    calibracao = {
        "juiz": {
            "modelo": "gpt-4o",
            "prompt_sha256": "abc",
            "n_casos": 96,
            "kappa": 0.85,
            "matriz": {"tp": 27, "fp": 2, "fn": 3, "tn": 64},
        }
    }
    (tmp_path / "calibracao_juiz.json").write_text(json.dumps(calibracao), encoding="utf-8")
    monkeypatch.setattr(run_eval, "RESULTADOS", tmp_path)
    monkeypatch.setattr(
        run_eval.settings, "golden_set", __import__("pathlib").Path("eval/golden_set.jsonl")
    )
    run_eval._salvar({"metricas": {"total_itens": 1}})

    resumo = json.loads(next(tmp_path.glob("metricas_*.json")).read_text(encoding="utf-8"))
    juiz = resumo["config"]["juiz"]
    assert juiz["kappa"] == 0.85
    # o hash do arquivo diverge do JUDGE_PROMPT real → flag de divergência
    assert juiz["prompt_divergente_do_calibrado"] is True
    assert juiz["prompt_sha256"] == "abc"
