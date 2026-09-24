"""Confirmação de rótulo por verificação (eval/confirmar_rotulos.py).

O valor do script está no que ele RECUSA. Confirmar rótulo que não se sustenta
transformaria o kappa em medida de si mesmo, então cada família tem um invariante e
quem não passa fica em rascunho esperando um humano.
"""

from eval.confirmar_rotulos import CONSTRUCAO, HUMANO, verificar

CONTEXTO = (
    "O CAC é o custo total de aquisição dividido pelo número de clientes conquistados "
    "no mesmo período. Inclui mídia, salários do time comercial e ferramentas."
)


def _caso(nota: str, answer: str, alucina: bool) -> dict:
    return {
        "id": "jc-000",
        "contexto": CONTEXTO,
        "question": "Como calcular o CAC?",
        "answer": answer,
        "alucina": alucina,
        "nota": nota,
    }


# ── injetado: o marcador manda ──────────────────────────────────────────────────

# gs-001 tem marcador "10% do LTV" no INJETADOS do gerador.
NOTA_INJ = "fato novo injetado em gs-001: benchmark numérico ausente do contexto"


def test_injetado_com_marcador_na_resposta_e_fora_do_contexto_confirma():
    caso = _caso(NOTA_INJ, "O CAC divide custo por clientes; mantenha abaixo de 10% do LTV.", True)
    ok, motivo = verificar(caso)
    assert ok and motivo == ""


def test_injetado_sem_o_marcador_na_resposta_nao_confirma():
    """Se o fato não está no texto, o rótulo `true` não decorre de nada."""
    caso = _caso(NOTA_INJ, "O CAC divide o custo total pelo número de clientes.", True)
    ok, motivo = verificar(caso)
    assert not ok and "não está na resposta" in motivo


def test_injetado_com_marcador_JA_no_contexto_nao_confirma():
    """Fato que o contexto já traz não é fato novo — seria rótulo errado."""
    caso = _caso(NOTA_INJ, "Mantenha abaixo de 10% do LTV.", True)
    caso["contexto"] = CONTEXTO + " A referência é manter o CAC abaixo de 10% do LTV."
    ok, motivo = verificar(caso)
    assert not ok and "EXISTE no contexto" in motivo


def test_injetado_rotulado_negativo_nao_confirma():
    caso = _caso(NOTA_INJ, "Mantenha abaixo de 10% do LTV.", False)
    ok, motivo = verificar(caso)
    assert not ok and "rótulo NÃO" in motivo


def test_injetado_de_item_sem_marcador_registrado_nao_confirma():
    caso = _caso("fato novo injetado em gs-999: inventado", "qualquer coisa", True)
    ok, motivo = verificar(caso)
    assert not ok and "sem marcador" in motivo


# ── fiel e paráfrase: nenhum fato novo detectável ───────────────────────────────

NOTA_PAR = "paráfrase fiel agressiva de gs-001: sinônimo e reordenação"
NOTA_FIEL = "resposta real da rodada 2026-09-03 (gs-001), verbatim"


def test_parafrase_sem_token_novo_confirma():
    caso = _caso(NOTA_PAR, "Divida o custo total de aquisição pelos clientes do período.", False)
    ok, motivo = verificar(caso)
    assert ok and motivo == ""


def test_fiel_sem_token_novo_confirma():
    caso = _caso(NOTA_FIEL, "O CAC inclui mídia, salários e ferramentas.", False)
    assert verificar(caso)[0]


def test_negativo_com_numero_fora_do_contexto_nao_confirma():
    """O caso perigoso: rótulo `false` num texto que traz fato novo é falso negativo
    no GABARITO — ensina o kappa a premiar a omissão."""
    caso = _caso(NOTA_PAR, "O CAC representa 35% do custo comercial.", False)
    ok, motivo = verificar(caso)
    assert not ok and "35%" in motivo


def test_negativo_rotulado_positivo_nao_confirma():
    caso = _caso(NOTA_PAR, "Divida o custo total pelos clientes.", True)
    ok, motivo = verificar(caso)
    assert not ok and "rótulo SIM" in motivo


def test_familia_desconhecida_nunca_confirma():
    """Nota fora do formato não tem invariante — não dá para verificar nada."""
    caso = _caso("repeticao quase literal", "O CAC inclui mídia.", False)
    ok, motivo = verificar(caso)
    assert not ok and "não tem invariante" in motivo


def test_as_duas_procedencias_sao_distintas():
    """O rótulo carrega de onde veio, e as duas etiquetas não podem colidir."""
    assert HUMANO != CONSTRUCAO
