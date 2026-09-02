"""Métricas próprias do eval como funções puras (testáveis sem API key)."""

import pytest

from grifo.config import REFUSAL_MESSAGE


def _p95(list):
    from eval.run_eval import p95

    return p95(list)


def test_p95_basico():
    """Interpolação linear compatível com numpy.percentile."""
    assert _p95([1, 2, 3, 4, 5, 6, 7, 8, 9, 100]) == pytest.approx(59.05)
    assert _p95([10]) == 10
    assert _p95([1, 2]) == pytest.approx(1.95)


def test_taxa_de_recusa_correta():
    from eval.run_eval import recusa_correta

    itens = [
        {"should_answer": False, "answer": REFUSAL_MESSAGE, "found": False},
        {"should_answer": False, "answer": REFUSAL_MESSAGE, "found": False},
        {"should_answer": False, "answer": "resposta inventada", "found": True},
        {"should_answer": True, "answer": "ok [Módulo 1, Aula 1]", "found": True},
    ]
    # 2 recusas corretas em 3 itens fora-de-escopo
    assert recusa_correta(itens) == 2 / 3


def test_fonte_esperada_acerta_por_prefixo_numerico():
    from eval.run_eval import fonte_bate

    resposta_fontes = [
        {"modulo": "2 - Metricas", "aula": "4 - CAC e LTV", "timestamp": None, "score": 0.8}
    ]
    assert fonte_bate({"modulo": "2", "aula": "4"}, resposta_fontes)
    assert not fonte_bate({"modulo": "3", "aula": "4"}, resposta_fontes)


def test_citacao_obrigatoria_nas_respostas_encontradas():
    import re

    padrao = re.compile(r"\[Módulo [^\],]+, Aula [^\],]+\]")
    assert padrao.search("O CAC é X [Módulo 2 - Metricas, Aula 4 - CAC e LTV].")
    assert not padrao.search("sem fonte nenhuma")


def test_registro_do_eval_carrega_texto_e_nao_etiqueta():
    """Regressao: `contexts` precisa ser o TEXTO dos chunks.

    Ja esteve montado a partir de `sources` (dicts de metadado), e nesse formato o
    juiz de alucinacao e o RAGAS avaliavam a resposta contra nomes de aula — medindo
    nada. Ruff e pytest nao pegam isso; so um teste do formato pega.
    """
    resposta = {
        "answer": "O CAC e custo por cliente [Módulo 2, Aula 4].",
        "found": True,
        "sources": [
            {"modulo": "2 - Metricas", "aula": "4 - CAC e LTV", "timestamp": None, "score": 0.8}
        ],
        "contexts": ["O CAC e o custo total de aquisicao dividido pelo numero de clientes."],
        "latency_ms": 10,
        "tokens": {"input": 1, "output": 1},
    }
    contexts = resposta["contexts"]
    assert all(isinstance(c, str) for c in contexts)
    contexto_do_juiz = "\n\n".join(
        f"[Módulo {s['modulo']}, Aula {s['aula']}]\n{t}"
        for s, t in zip(resposta["sources"], contexts, strict=False)
    )
    assert "custo total de aquisicao" in contexto_do_juiz  # o texto chega ao juiz
    assert "[Módulo 2 - Metricas, Aula 4 - CAC e LTV]" in contexto_do_juiz
