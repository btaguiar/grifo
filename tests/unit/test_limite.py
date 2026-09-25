"""Travas de custo da demo pública (src/grifo/api/limite.py).

Cada pergunta gasta token da chave do dono. O que se testa aqui é o que protege esse
bolso: quantas passam, quando param, e que pergunta barrada não consome cota.
"""

from datetime import UTC, datetime, timedelta

from grifo.api.limite import Limitador

INICIO = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)


def test_sem_limite_configurado_tudo_passa():
    """Padrão de quem roda local: o custo é do próprio dono, não há visitante anônimo."""
    limitador = Limitador(por_minuto=0, diario=0)
    assert all(limitador.checar("1.2.3.4", INICIO) is None for _ in range(50))


def test_limite_por_minuto_barra_o_excesso():
    limitador = Limitador(por_minuto=3, diario=0)
    for _ in range(3):
        assert limitador.checar("1.2.3.4", INICIO) is None
    assert "Muitas perguntas" in (limitador.checar("1.2.3.4", INICIO) or "")


def test_a_janela_anda_e_libera_de_novo():
    limitador = Limitador(por_minuto=2, diario=0)
    limitador.checar("1.2.3.4", INICIO)
    limitador.checar("1.2.3.4", INICIO)
    assert limitador.checar("1.2.3.4", INICIO) is not None
    assert limitador.checar("1.2.3.4", INICIO + timedelta(seconds=61)) is None


def test_um_ip_nao_derruba_o_outro():
    """O limite por minuto é por visitante: quem chega depois não paga pelo anterior."""
    limitador = Limitador(por_minuto=1, diario=0)
    assert limitador.checar("1.1.1.1", INICIO) is None
    assert limitador.checar("2.2.2.2", INICIO) is None


def test_teto_diario_vale_para_todos_juntos():
    limitador = Limitador(por_minuto=0, diario=3)
    for i in range(3):
        assert limitador.checar(f"9.9.9.{i}", INICIO) is None
    barrado = limitador.checar("outro.ip", INICIO)
    assert barrado and "limite de perguntas de hoje" in barrado


def test_pergunta_barrada_nao_consome_cota_do_dia():
    """Senão um robô insistente empurraria o teto diário sozinho, e quem chegasse
    depois pegaria a demo fechada sem ninguém ter sido atendido."""
    limitador = Limitador(por_minuto=1, diario=10)
    limitador.checar("1.2.3.4", INICIO)
    for _ in range(5):
        limitador.checar("1.2.3.4", INICIO)  # todas barradas pelo limite por minuto
    assert limitador.usadas_hoje == 1


def test_o_dia_vira_e_o_teto_reseta():
    limitador = Limitador(por_minuto=0, diario=2)
    limitador.checar("1.2.3.4", INICIO)
    limitador.checar("1.2.3.4", INICIO)
    assert limitador.checar("1.2.3.4", INICIO) is not None
    assert limitador.checar("1.2.3.4", INICIO + timedelta(days=1)) is None
