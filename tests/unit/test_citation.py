"""FR-33/FR-62: a citação vira link para o minuto da aula."""

import pytest

from grifo.citation import link_com_timestamp, timestamp_para_segundos


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
