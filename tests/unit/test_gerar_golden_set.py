"""Rascunho de golden set (eval/gerar_golden_set.py).

O valor está nas verificações: o que o script RECUSA a gravar. Gabarito com termo
inventado e pergunta "fora do escopo" que na verdade está no material são os dois
jeitos de um golden set medir a si mesmo.
"""

from eval.gerar_golden_set import (
    aparece_no_corpus,
    numero_de,
    parecidas,
    tem_dado_duro,
    termos_ausentes,
)

TRECHO = (
    "A empresa saiu de 53 para 131 pessoas em um ano, e o que travou foi a falta de "
    "autonomia para decidir rápido. O fundador virou o gargalo."
)


def _chunk(texto: str) -> dict:
    return {"text": texto}


# ── gabarito: só o que está literalmente no trecho ──────────────────────────────


def test_termo_presente_no_trecho_passa():
    assert termos_ausentes(["53 para 131", "autonomia para decidir"], TRECHO) == []


def test_termo_inventado_e_apontado():
    """O caso real: o modelo resume com palavras próprias e o gabarito vira ficção."""
    assert termos_ausentes(["investimento em marketing"], TRECHO) == ["investimento em marketing"]


def test_acento_e_caixa_nao_contam_como_diferenca():
    assert termos_ausentes(["O FUNDADOR VIROU O GARGALO"], TRECHO) == []


def test_espaco_repetido_no_trecho_nao_atrapalha():
    assert termos_ausentes(["virou o gargalo"], "o fundador   virou\no gargalo") == []


# ── fora do escopo: o termo não pode existir no corpus ──────────────────────────


def test_termo_ausente_do_corpus_serve_como_fora_de_escopo():
    assert not aparece_no_corpus("bolo de cenoura", [_chunk(TRECHO)])


def test_termo_presente_no_corpus_reprova_a_pergunta_fora_de_escopo():
    """Pegou uma de verdade: a pergunta sobre cachorro, citado numa das aulas."""
    corpus = [_chunk("comprei um cachorro e aprendi sobre lealdade"), _chunk(TRECHO)]
    assert aparece_no_corpus("cachorro", corpus)


# ── perguntas quase iguais ──────────────────────────────────────────────────────


def test_pergunta_quase_igual_e_recusada():
    """Chunks vizinhos falam do mesmo assunto e rendem a mesma pergunta duas vezes."""
    aceitas = ["por que é importante dar autonomia para o time?"]
    assert parecidas("por que é importante dar autonomia para o time da empresa?", aceitas)


def test_pergunta_sobre_outro_assunto_passa():
    aceitas = ["por que é importante dar autonomia para o time?"]
    assert not parecidas("como a starbucks lidou com a crise de 2008?", aceitas)


def test_primeira_pergunta_nunca_e_duplicata():
    assert not parecidas("qualquer pergunta", [])


# ── auxiliares ──────────────────────────────────────────────────────────────────


def test_numero_do_modulo_sai_do_rotulo():
    assert numero_de("2 - Metricas") == "2"
    assert numero_de("4 - Inteligencia Artificial") == "4"


def test_rotulo_sem_numero_volta_inteiro():
    """Sem número não há o que extrair — inventar "0" criaria fonte errada."""
    assert numero_de("Bonus") == "Bonus"


def test_trecho_com_numero_e_candidato_a_factual():
    assert tem_dado_duro("crescemos 33% no semestre")
    assert tem_dado_duro("faturamos 150 milhões")
    assert tem_dado_duro("eram 130 pessoas")


def test_trecho_sem_dado_duro_nao_e_candidato():
    assert not tem_dado_duro("a alta performance é um desapego da própria reputação")
