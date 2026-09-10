"""Triagem do conjunto de calibração (eval/triagem_calibracao.py) como funções puras.

O script existe para impedir que um kappa alto saia de um conjunto fabricado com
pista de forma. Estes testes travam as duas coisas que ele precisa acertar: detectar
fato novo de verdade e NÃO acusar o que é só maiúscula de início de frase — a segunda
importa tanto quanto a primeira, porque uma triagem que grita em tudo é ignorada.
"""

from eval.triagem_calibracao import (
    GAP_MAXIMO_FORMULA,
    abre_com_atribuicao,
    assinatura_de_superficie,
    familia,
    item_de_origem,
    n_efetivo,
    normalizar,
    tokens_ausentes,
)

CONTEXTO = (
    "O CAC é o custo total de aquisição dividido pelo número de clientes conquistados "
    "no mesmo período. Inclui mídia, salários do time comercial e ferramentas. Um erro "
    "comum é corrigir o número considerando apenas o gasto com anúncios."
)


def _caso(cid: str, answer: str, alucina: bool, contexto: str = CONTEXTO) -> dict:
    return {
        "id": cid,
        "contexto": contexto,
        "question": "Como calcular o CAC?",
        "answer": answer,
        "alucina": alucina,
        "nota": "caso de teste",
    }


# ── normalização e classificação ────────────────────────────────────────────────


def test_normalizar_tira_acento_e_caixa():
    assert normalizar("Aquisição") == normalizar("AQUISICAO") == "aquisicao"


def test_familia_reconhece_as_tres_e_cai_em_outro():
    assert familia("resposta real da rodada 2026-09-03 (gs-001), verbatim") == "fiel"
    assert familia("paráfrase fiel agressiva de gs-007: sinônimo") == "parafrase"
    assert familia("fato novo injetado em gs-011: benchmark ausente") == "injetado"
    # Nota fora do formato conhecido não pode ser contada como uma das famílias.
    assert familia("repeticao quase literal") == "outro"


def test_item_de_origem_le_o_id_do_golden_set():
    assert item_de_origem("fato novo injetado em gs-045: faixa ausente") == "gs-045"
    assert item_de_origem("repeticao quase literal") is None


# ── tokens ausentes: o coração da triagem ───────────────────────────────────────


def test_nome_proprio_no_meio_da_frase_e_pego():
    """O caso que a checagem existe para pegar: autoria inventada."""
    resposta = "Aquisição com retenção fraca é balde furado, metáfora de Philip Kotler."
    assert "Kotler" in tokens_ausentes(resposta, CONTEXTO)


def test_numero_ausente_e_pego_em_qualquer_posicao():
    resposta = "35% do CAC vem de salários. Um benchmark comum é 10% do LTV."
    fora = tokens_ausentes(resposta, CONTEXTO)
    assert "35%" in fora and "10%" in fora


def test_verbo_capitalizado_em_inicio_de_frase_nao_e_acusado():
    """O português capitaliza por posição. Era daqui que vinha quase todo falso alarme."""
    resposta = "Somar só anúncios dá um CAC baixo. Cortar dessa conta distorce o número."
    assert tokens_ausentes(resposta, CONTEXTO) == []


def test_etiqueta_de_citacao_nao_vira_numero_novo():
    """O próprio judge.txt manda ignorar a marcação entre colchetes."""
    resposta = "O CAC é o custo total dividido pelos clientes [Módulo 2, Aula 4]."
    assert tokens_ausentes(resposta, CONTEXTO) == []


def test_flexao_casa_com_o_contexto_por_prefixo():
    """ "Corrige" na resposta contra "corrigir" no contexto é morfologia, não fato."""
    resposta = "O método é assim: primeiro mede, depois Corrige o que saiu da faixa."
    assert tokens_ausentes(resposta, CONTEXTO) == []


def test_resposta_fiel_ao_contexto_nao_gera_suspeita():
    resposta = "O CAC divide o custo total de aquisição pelo número de clientes."
    assert tokens_ausentes(resposta, CONTEXTO) == []


# ── assinatura de superfície: a checagem que reprova ────────────────────────────


def test_abre_com_atribuicao_reconhece_as_formulas():
    assert abre_com_atribuicao("O material recomenda revisar a cada seis meses.")
    assert abre_com_atribuicao("A aula sugere dois trimestres.")
    assert not abre_com_atribuicao("O CAC é o custo total de aquisição.")


def test_assinatura_reprova_positivos_com_formula_e_negativos_sem():
    """O padrão medido em 2026-09-06: 61% contra 2%, separável sem ler o contexto."""
    casos = [
        _caso(f"p{i}", "O CAC é o custo total. O material recomenda revisar sempre.", True)
        for i in range(5)
    ] + [_caso(f"n{i}", "O CAC é o custo total dividido pelos clientes.", False) for i in range(5)]
    sa = assinatura_de_superficie(casos)
    assert sa["medivel"]
    assert sa["taxa_formula_positivos"] == 1.0
    assert sa["taxa_formula_negativos"] == 0.0
    assert sa["gap_formula"] > GAP_MAXIMO_FORMULA
    assert not sa["gap_ok"]


def test_assinatura_aprova_conjunto_sem_pista_de_forma():
    texto = "O CAC divide o custo total de aquisição pelo número de clientes do periodo."
    casos = [_caso(f"p{i}", texto, True) for i in range(5)]
    casos += [_caso(f"n{i}", texto, False) for i in range(5)]
    sa = assinatura_de_superficie(casos)
    assert sa["gap_ok"] and sa["tamanho_ok"]


def test_assinatura_indefinida_sem_uma_das_classes():
    """Kappa e assinatura precisam das duas classes; sem elas o veredito é indefinido."""
    casos = [_caso(f"n{i}", "O CAC é o custo total.", False) for i in range(3)]
    assert assinatura_de_superficie(casos) == {"medivel": False}


def test_razao_de_tamanho_denuncia_positivos_mais_curtos():
    curto = "Inventei um número: 42% dos clientes."
    longo = "O CAC é o custo total de aquisição dividido pelo número de clientes " * 3
    casos = [_caso(f"p{i}", curto, True) for i in range(3)]
    casos += [_caso(f"n{i}", longo, False) for i in range(3)]
    assert not assinatura_de_superficie(casos)["tamanho_ok"]


# ── n efetivo ───────────────────────────────────────────────────────────────────


def test_n_efetivo_conta_contexto_repetido_uma_vez():
    """Três famílias sobre o mesmo contexto não são três itens independentes."""
    casos = [
        _caso("a", "resposta 1", False),
        _caso("b", "resposta 2", False),
        _caso("c", "resposta 3", True),
        _caso("d", "resposta 4", False, contexto="Outro contexto completamente diferente."),
    ]
    ef = n_efetivo(casos)
    assert ef["casos"] == 4
    assert ef["contextos_distintos"] == 2
    assert ef["casos_por_contexto"] == 2.0
