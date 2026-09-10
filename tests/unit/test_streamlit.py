"""FR-60 a FR-63: a UI — helpers puros e o script rodando no AppTest, sem browser."""

from pathlib import Path

import httpx
import pytest

app = pytest.importorskip("app.streamlit_app", reason="streamlit disponível no ambiente")

from app.streamlit_app import (  # noqa: E402
    agrupar_por_aula,
    linha_fonte,
    mensagem_de_falha,
    timestamp_to_seconds,
    video_link,
)
from streamlit.testing.v1 import AppTest  # noqa: E402

SCRIPT = str(Path(__file__).resolve().parents[2] / "app" / "streamlit_app.py")
RECUSA = "Não encontrei isso no material do curso."


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


# ── fontes: uma linha por aula, citadas primeiro ────────────────────────────────


def _fonte(aula: str, score: float, cited: bool, ts: str | None = None) -> dict:
    return {"modulo": "2 - Metricas", "aula": aula, "score": score, "cited": cited, "timestamp": ts}


def test_dois_trechos_da_mesma_aula_viram_uma_linha():
    """Era o que a tela mostrava: "Aula 4" duas vezes, idênticas."""
    aulas = agrupar_por_aula([_fonte("4 - CAC", 0.64, True), _fonte("4 - CAC", 0.50, True)])
    assert len(aulas) == 1
    assert aulas[0]["trechos"] == 2
    assert aulas[0]["score"] == 0.64


def test_aula_fica_com_o_melhor_score_e_o_timestamp_dele():
    aulas = agrupar_por_aula(
        [_fonte("4 - CAC", 0.50, False, "00:01:00"), _fonte("4 - CAC", 0.70, False, "00:09:00")]
    )
    assert aulas[0]["score"] == 0.70
    assert aulas[0]["timestamp"] == "00:09:00"


def test_aula_e_citada_se_qualquer_trecho_foi():
    aulas = agrupar_por_aula([_fonte("4 - CAC", 0.64, False), _fonte("4 - CAC", 0.50, True)])
    assert aulas[0]["cited"] is True


def test_citadas_vem_antes_mesmo_com_score_menor():
    aulas = agrupar_por_aula([_fonte("5 - Funil", 0.90, False), _fonte("4 - CAC", 0.50, True)])
    assert [a["aula"] for a in aulas] == ["4 - CAC", "5 - Funil"]


def test_fonte_sem_campo_cited_nao_quebra():
    """API anterior ao `cited`: nada citado, nada separado."""
    fonte = {"modulo": "2", "aula": "4", "score": 0.6}
    assert agrupar_por_aula([fonte])[0]["cited"] is False


def test_linha_so_menciona_trechos_quando_ha_mais_de_um():
    assert "trechos" not in linha_fonte({**_fonte("4", 0.6, True), "trechos": 1})
    assert "2 trechos" in linha_fonte({**_fonte("4", 0.6, True), "trechos": 2})


# ── falha: dizer o que falhou, sem culpar a peça errada ─────────────────────────


def test_timeout_nao_diz_que_a_api_caiu():
    msg = mensagem_de_falha(httpx.ReadTimeout("lento"))
    assert "API_TIMEOUT" in msg and "no ar" not in msg


def test_erro_500_aponta_o_log_e_nao_a_conexao():
    """O caso real: provedor LLM recusando a requisição, API perfeitamente no ar."""
    req = httpx.Request("POST", "http://api/ask")
    erro = httpx.HTTPStatusError("500", request=req, response=httpx.Response(500, request=req))
    msg = mensagem_de_falha(erro)
    assert "500" in msg and "no ar" not in msg


def test_sem_conexao_manda_conferir_a_api():
    assert "no ar" in mensagem_de_falha(httpx.ConnectError("recusada"))


# ── o script rodando: histórico redesenhado igual à mensagem nova ───────────────


class _Resposta:
    def __init__(self, corpo: dict) -> None:
        self._corpo = corpo

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._corpo


def _api_falsa(monkeypatch, respostas: list[dict]) -> None:
    fila = iter(respostas)
    monkeypatch.setattr(httpx, "post", lambda *_a, **_k: _Resposta(next(fila)))


def _perguntar(at: AppTest, texto: str) -> None:
    at.chat_input[0].set_value(texto).run()


def test_legenda_da_recusa_sobrevive_ao_redesenho(monkeypatch):
    """Eram dois blocos copiados: a legenda existia só na mensagem nova, e a recusa
    perdia a frase assim que a pergunta seguinte redesenhava a conversa."""
    _api_falsa(
        monkeypatch,
        [
            {"answer": RECUSA, "found": False, "sources": []},
            {"answer": RECUSA, "found": False, "sources": []},
        ],
    )
    at = AppTest.from_file(SCRIPT).run()
    _perguntar(at, "receita de bolo?")
    _perguntar(at, "teoria das cordas?")
    legendas = [c.value for c in at.caption if "Prefiro dizer" in c.value]
    assert len(legendas) == 2


def test_resposta_separa_citadas_das_so_consultadas(monkeypatch):
    _api_falsa(
        monkeypatch,
        [
            {
                "answer": "O CAC divide o custo pelos clientes [Módulo 2, Aula 4].",
                "found": True,
                "sources": [
                    _fonte("4 - CAC e LTV", 0.64, True),
                    _fonte("4 - CAC e LTV", 0.50, True),
                    _fonte("5 - Funil", 0.47, False),
                ],
            }
        ],
    )
    at = AppTest.from_file(SCRIPT).run()
    _perguntar(at, "Como calcular o CAC?")
    linhas = [m.value for m in at.markdown if "**Aula**" in m.value]
    assert len(linhas) == 2  # três trechos, duas aulas
    assert "2 trechos" in linhas[0] and "CAC e LTV" in linhas[0]
    assert linhas[1].startswith(":gray[") and "Funil" in linhas[1]
    assert "Citadas na resposta" in [c.value for c in at.caption]
