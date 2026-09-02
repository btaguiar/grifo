"""FR-62: helpers puros da UI — link do timestamp testável sem browser."""

import pytest

app = pytest.importorskip("app.streamlit_app", reason="streamlit disponível no ambiente")

from app.streamlit_app import timestamp_to_seconds, video_link  # noqa: E402


def test_timestamp_para_segundos():
    assert timestamp_to_seconds("00:22:14") == 1334
    assert timestamp_to_seconds("05:30") == 330
    assert timestamp_to_seconds("01:00:00") == 3600


def test_link_so_existe_com_player_configurado(monkeypatch):
    monkeypatch.setattr(app, "VIDEO_BASE_URL", "https://player.exemplo.com/video/1")
    assert video_link("00:22:14") == "https://player.exemplo.com/video/1?t=1334"


def test_sem_player_devolve_none(monkeypatch):
    monkeypatch.setattr(app, "VIDEO_BASE_URL", "")
    assert video_link("00:22:14") is None
    assert video_link(None) is None
