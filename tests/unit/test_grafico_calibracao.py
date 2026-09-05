"""O gráfico da SPEC 12 deriva da tabela 4.1 — ele não pode divergir do texto."""

import pytest


def _ler():
    from eval.grafico_calibracao import ler_tabela

    return ler_tabela()


def test_le_a_tabela_publicada_no_evaluation():
    dados = _ler()
    assert len(dados) >= 5, "a tabela 4.1 encolheu?"
    assert dados == sorted(dados, key=lambda d: d["threshold"])
    for linha in dados:
        assert 0 <= linha["fonte"] <= 100
        assert 0 <= linha["recusa"] <= 100
        assert 0 <= linha["cobertura"] <= 100


def test_os_dois_pontos_anotados_existem():
    """O argumento do gráfico são estes dois pontos; sem eles ele vira três curvas."""
    marcas = {d["marca"]: d for d in _ler() if d["marca"]}
    assert "partida" in marcas and "calibrado" in marcas
    partida, calibrado = marcas["partida"], marcas["calibrado"]
    # O que o gráfico afirma no título: ganho nos dois eixos, não trade-off.
    assert calibrado["recusa"] > partida["recusa"]
    assert calibrado["cobertura"] >= partida["cobertura"]
    assert calibrado["fonte"] >= partida["fonte"]


def test_formato_quebrado_falha_alto(tmp_path, monkeypatch):
    """Gráfico gerado de dado incerto é pior que gráfico nenhum."""
    from eval import grafico_calibracao as g

    falso = tmp_path / "EVALUATION.md"
    falso.write_text("### 4.1 titulo\n\nsem tabela nenhuma\n\n### 4.2 outra\n", encoding="utf-8")
    monkeypatch.setattr(g, "EVALUATION", falso)
    with pytest.raises(SystemExit, match="4.1"):
        g.ler_tabela()
