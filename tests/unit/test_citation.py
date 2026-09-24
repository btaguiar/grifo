"""FR-33/FR-62: a citação vira link para o minuto da aula."""

import pytest

from grifo.citation import (
    CITACAO_RE,
    formatar_citacao,
    link_com_timestamp,
    timestamp_para_segundos,
)


@pytest.mark.parametrize(
    ("stamp", "segundos"), [("00:22:14", 1334), ("05:30", 330), ("01:00:00", 3600), ("0:00", 0)]
)
def test_timestamp_vira_segundos(stamp, segundos):
    assert timestamp_para_segundos(stamp) == segundos


def test_url_curta_recebe_query_nova():
    assert link_com_timestamp("https://youtu.be/AbC", "00:22:14") == "https://youtu.be/AbC?t=1334"


def test_url_que_ja_tem_query_recebe_parametro_extra():
    """`watch?v=...` já traz query: um segundo `?` produziria link quebrado."""
    assert (
        link_com_timestamp("https://www.youtube.com/watch?v=AbC", "05:30")
        == "https://www.youtube.com/watch?v=AbC&t=330"
    )


def test_sem_timestamp_devolve_a_url_da_aula():
    """PDF e markdown citam por página: a aula ainda abre, só não no minuto."""
    assert link_com_timestamp("https://youtu.be/AbC", None) == "https://youtu.be/AbC"


def test_sem_url_nao_ha_link():
    assert link_com_timestamp(None, "00:22:14") is None
    assert link_com_timestamp("", "00:22:14") is None


# ── formato da citação: quem escreve e quem reconhece são o mesmo módulo ────────


def test_citacao_com_autor():
    assert formatar_citacao("1 - Vendas", "1 - Como Vender", "Alfredo Soares") == (
        "[Módulo 1 - Vendas, Aula 1 - Como Vender — Alfredo Soares]"
    )


def test_citacao_sem_autor_mantem_o_formato_antigo():
    """Corpus sem autor declarado continua citando como sempre citou."""
    assert formatar_citacao("2", "4") == "[Módulo 2, Aula 4]"
    assert formatar_citacao("2", "4", None) == "[Módulo 2, Aula 4]"


def test_regex_reconhece_as_duas_formas():
    assert CITACAO_RE.search("o CAC é isso [Módulo 2, Aula 4].")
    assert CITACAO_RE.search("venda é isso [Módulo 1 - Vendas, Aula 1 — Alfredo Soares].")


def test_regex_nao_confunde_colchete_qualquer():
    """`citacao_em_respondidas` conta com isto: texto entre colchetes não é citação."""
    assert not CITACAO_RE.search("segundo o material [ver adiante] o CAC sobe")
    assert not CITACAO_RE.search("sem colchete nenhum")
