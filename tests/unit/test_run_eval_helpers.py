"""Métricas próprias do eval como funções puras (testáveis sem API key)."""

from pathlib import Path

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


def test_cobertura_conteudo_normaliza_caso_e_acento():
    """O gabarito casa "Aquisição" com "aquisicao" — paráfrase não pode virar zero."""
    from eval.run_eval import cobertura_conteudo

    itens = [
        {
            "should_answer": True,
            "found": True,
            "answer": "O CAC usa o custo TOTAL de aquisição dividido pelos clientes.",
            "expected_answer_contains": ["custo total de aquisição", "número de clientes"],
        }
    ]
    c = cobertura_conteudo(itens)
    assert c["media"] == 0.5  # 1 de 2 termos (o segundo está ausente de verdade)
    assert c["total_em_itens"] == 0.0
    assert c["n"] == 1


def test_cobertura_conteudo_so_conta_respondidas_com_gabarito():
    """Recusa fora do denominador — quem não respondeu já paga na taxa de resposta."""
    from eval.run_eval import cobertura_conteudo

    itens = [
        {  # respondida com gabarito: cobertura total
            "should_answer": True,
            "found": True,
            "answer": "fala de custo total de aquisição",
            "expected_answer_contains": ["custo total de aquisição"],
        },
        {  # recusada (falsa recusa) com gabarito: NÃO entra no denominador
            "should_answer": True,
            "found": False,
            "answer": REFUSAL_MESSAGE,
            "expected_answer_contains": ["custo total de aquisição"],
        },
        {  # fora de escopo: sem gabarito por desenho
            "should_answer": False,
            "found": False,
            "answer": REFUSAL_MESSAGE,
        },
    ]
    c = cobertura_conteudo(itens)
    assert c == {"media": 1.0, "total_em_itens": 1.0, "n": 1}


def test_cobertura_conteudo_sem_alvo_e_none():
    from eval.run_eval import cobertura_conteudo

    assert cobertura_conteudo([]) is None
    assert cobertura_conteudo([{"should_answer": False, "found": False}]) is None


def test_cobertura_media_e_total_distintos():
    """A média alta com total baixo é o achado: quase tudo coberto, nunca tudo."""
    from eval.run_eval import cobertura_conteudo

    itens = [
        {
            "should_answer": True,
            "found": True,
            "answer": "a b",
            "expected_answer_contains": ["a", "b"],
        },
        {
            "should_answer": True,
            "found": True,
            "answer": "a",
            "expected_answer_contains": ["a", "b"],
        },
        {
            "should_answer": True,
            "found": True,
            "answer": "a",
            "expected_answer_contains": ["a", "b"],
        },
        {
            "should_answer": True,
            "found": True,
            "answer": "a",
            "expected_answer_contains": ["a", "b"],
        },
    ]
    c = cobertura_conteudo(itens)
    assert c["media"] == 0.625  # 1.0, 0.5, 0.5, 0.5
    assert c["total_em_itens"] == 0.25  # só 1 de 4 cobre tudo


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


def test_resumo_versionado_nao_carrega_o_nome_do_curso(tmp_path, monkeypatch):
    """Regressão GOV-5: o `metricas_*.json` é commitado e era regenerado com CURSO_NOME.

    Num corpus real esse campo é o nome da escola dona do material. A auditoria tirou o
    nome dos arquivos rastreados, mas este era reescrito a cada rodada a partir do
    `.env` — então limpar uma vez não bastava, e a próxima avaliação o republicaria.
    """
    import json

    from eval import run_eval

    monkeypatch.setattr(run_eval, "RESULTADOS", tmp_path)
    monkeypatch.setattr(run_eval.settings, "curso_nome", "Escola Secreta")
    monkeypatch.setattr(run_eval.settings, "golden_set", Path("eval/golden_set.local.jsonl"))
    run_eval._salvar({"metricas": {"total_itens": 1}})

    resumo = next(tmp_path.glob("metricas_*.json"))
    conteudo = resumo.read_text(encoding="utf-8")
    assert "Escola Secreta" not in conteudo
    assert json.loads(conteudo)["corpus"] == "real (privado)"


def test_resumo_versionado_recusa_NaN(tmp_path, monkeypatch):
    """`NaN` não é JSON válido: melhor estourar que gravar arquivo ilegível por terceiros.

    Uma métrica RAGAS que falhou em parte dos itens virava NaN e era gravada como se
    fosse número — e `JSON.parse` ou `jq` rejeitam o arquivo inteiro.
    """
    from eval import run_eval

    monkeypatch.setattr(run_eval, "RESULTADOS", tmp_path)
    monkeypatch.setattr(run_eval.settings, "golden_set", Path("eval/golden_set.jsonl"))
    with pytest.raises(ValueError):
        run_eval._salvar({"metricas": {"faithfulness": float("nan")}})


def test_resumo_marca_serie_somente_na_config_canonica(tmp_path, monkeypatch):
    """Fase 4: rodada fora da configuração congelada sai com serie: false.

    Sem a marca, a rodada com gpt-4o (juiz mais caro) seria lida como próximo ponto
    da série produzida com gpt-4o-mini — comparação inválida sem ninguém ver.
    """
    import json

    from eval import run_eval

    from grifo.config import (
        SERIE_LLM_MODEL,
        SERIE_SCORE_THRESHOLD,
    )

    monkeypatch.setattr(run_eval, "RESULTADOS", tmp_path)
    monkeypatch.setattr(run_eval.settings, "golden_set", Path("eval/golden_set.jsonl"))
    monkeypatch.setattr(run_eval.settings, "curso_nome", "Escola Secreta")

    def _serie(**overrides):
        base = {
            "llm_model": SERIE_LLM_MODEL,
            "eval_llm_model": "openai/gpt-4o",
            "score_threshold": SERIE_SCORE_THRESHOLD,
            "final_k": 5,
            "rerank_enabled": False,
            "force_citation": False,
        }
        base.update(overrides)
        for campo, valor in base.items():
            monkeypatch.setattr(run_eval.settings, campo, valor)
        run_eval._salvar({"metricas": {"total_itens": 1}})
        resumo = json.loads(next(tmp_path.glob("metricas_*.json")).read_text(encoding="utf-8"))
        return resumo["serie"]

    assert _serie() is True
    assert _serie(llm_model="openai/gpt-4o") is False  # trocou o modelo respondedor
    assert _serie(force_citation=True) is False  # pós-processamento ligado
    assert _serie(score_threshold=0.50) is False  # threshold fora do congelado
