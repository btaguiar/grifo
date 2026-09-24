"""Montagem do corpus de vídeo: json3 -> cues -> VTT (scripts/baixar_aulas.py)."""

import pytest
import webvtt
from scripts.baixar_aulas import (
    agrupar_eventos,
    exigir_conteudo,
    hhmmss,
    id_do_video,
    montar_vtt,
)


@pytest.mark.parametrize(
    ("url", "esperado"),
    [
        ("https://www.youtube.com/watch?v=bhOSSMFs1gI", "bhOSSMFs1gI"),
        ("https://www.youtube.com/watch?v=exYVpYbERno&t=37s", "exYVpYbERno"),
        ("https://www.youtube.com/watch?v=k2zFLImP0kM&t=16s&pp=0gcJCS8M", "k2zFLImP0kM"),
        ("https://youtu.be/bhOSSMFs1gI", "bhOSSMFs1gI"),
        ("https://www.youtube.com/shorts/AbC123", "AbC123"),
    ],
)
def test_id_do_video(url, esperado):
    """`t=` e `pp=` acompanham link copiado do player e não podem virar parte do id."""
    assert id_do_video(url) == esperado


def test_url_sem_id_reprova():
    with pytest.raises(ValueError, match="id do vídeo"):
        id_do_video("https://www.youtube.com/feed/subscriptions")


@pytest.mark.parametrize(
    ("ms", "stamp"), [(0, "00:00:00.000"), (114_000, "00:01:54.000"), (3_661_000, "01:01:01.000")]
)
def test_hhmmss(ms, stamp):
    assert hhmmss(ms) == stamp


def _ev(ms: int, *palavras: str) -> dict:
    return {"tStartMs": ms, "segs": [{"utf8": p} for p in palavras]}


def test_agrupa_palavras_ate_o_limite_guardando_o_primeiro_inicio():
    """O início do grupo é o que vira `?t=`: apontar para o começo do trecho."""
    eventos = [_ev(i * 1000, "palavra ") for i in range(60)]
    cues = agrupar_eventos(eventos, max_chars=80)
    assert len(cues) > 1
    assert cues[0][0] == 0
    assert all(len(texto) <= 100 for _, texto in cues)


def test_evento_vazio_nao_vira_cue_nem_adianta_o_inicio():
    """O json3 traz eventos sem `segs` (marcadores): entram como cue em branco."""
    cues = agrupar_eventos([{"tStartMs": 500}, _ev(2000, "olá"), {"tStartMs": 3000, "segs": []}])
    assert cues == [(2000, "olá")]


def test_texto_do_cue_sai_normalizado():
    cues = agrupar_eventos([_ev(0, "  muito   ", "\n espaço  ")])
    assert cues == [(0, "muito espaço")]


def test_vtt_gerado_e_lido_de_volta_com_os_timestamps(tmp_path):
    """O loader de transcrição lê este arquivo: ele precisa ser VTT válido."""
    vtt = montar_vtt([(0, "primeiro trecho"), (114_000, "segundo trecho")])
    f = tmp_path / "aula.vtt"
    f.write_text(vtt, encoding="utf-8")
    caps = list(webvtt.read(str(f)))
    assert [c.text for c in caps] == ["primeiro trecho", "segundo trecho"]
    assert caps[0].start == "00:00:00.000"
    assert caps[1].start == "00:01:54.000"


def test_fim_de_um_cue_e_o_inicio_do_proximo():
    """Cue sem fim coerente faz o player pular texto; o último ganha uma cauda fixa."""
    vtt = montar_vtt([(0, "a"), (10_000, "b")])
    assert "00:00:00.000 --> 00:00:10.000" in vtt
    assert "00:00:10.000 --> 00:00:15.000" in vtt


def test_transcricao_vazia_e_erro_nao_arquivo_vazio():
    """A primeira versão gravava um VTT sem cue nenhum e seguia: a aula entrava no
    corpus como arquivo válido e vazio, que nenhuma métrica denunciaria."""
    with pytest.raises(RuntimeError, match="não produziu transcrição"):
        exigir_conteudo([], "whisper small")


def test_transcricao_com_conteudo_passa_adiante():
    cues = [(0, "olá")]
    assert exigir_conteudo(cues, "legenda automática") is cues
