"""Gate de regressão e série temporal (Fase 4) como funções puras."""

import json

from eval.gate_regressao import comparar

from grifo.config import custo_por_tokens


def _rodada(timestamp: str, **metricas) -> dict:
    padrao = {
        "recusa_correta": 1.0,
        "alucinacao": 0.0,
        "latency_p95_ms": 2500.0,
    }
    padrao.update(metricas)
    return {"timestamp": timestamp, "commit": "abc1234", "metricas": padrao}


def test_sem_regressao_aprova():
    nova = _rodada("20260906T150000Z", recusa_correta=0.97, alucinacao=0.01)
    antiga = _rodada("20260901T150000Z", recusa_correta=1.0, alucinacao=0.0)
    assert comparar(nova, antiga) == []


def test_queda_de_recusa_acima_da_tolerancia_reprova():
    nova = _rodada("t2", recusa_correta=0.90)
    antiga = _rodada("t1", recusa_correta=0.99)
    falhas = comparar(nova, antiga)
    assert len(falhas) == 1 and "recusa_correta" in falhas[0]


def test_queda_de_recusa_dentro_da_tolerancia_passa():
    """5pp é a tolerância: 0.96 vindo de 1.00 é queda real menor que o ruído aceito."""
    nova = _rodada("t2", recusa_correta=0.96)
    antiga = _rodada("t1", recusa_correta=1.0)
    assert [f for f in comparar(nova, antiga) if "recusa" in f] == []


def test_subida_de_alucinacao_acima_da_tolerancia_reprova():
    falhas = comparar(_rodada("t2", alucinacao=0.05), _rodada("t1", alucinacao=0.0))
    assert len(falhas) == 1 and "alucinacao" in falhas[0]


def test_p95_acima_do_teto_reprova_mesmo_sem_anterior():
    """O teto de 3000ms é absoluto (NFR-1): vale até na primeira rodada da série."""
    falhas = comparar(_rodada("t1", latency_p95_ms=3527.0), None)
    assert any("p95" in f for f in falhas)


def test_metrica_ausente_nao_gera_falso_alarme():
    """alucinacao None (juiz fora do ar) não pode virar 'subiu para zero'."""
    nova = _rodada("t2", alucinacao=None)
    antiga = _rodada("t1", alucinacao=0.0)
    assert [f for f in comparar(nova, antiga) if "alucinacao" in f] == []


def test_custo_por_tokens_gpt4o_mini():
    """Rodada 3.4-A: 30.850 entrada + 4.358 saída a 0,15/0,60 = US$ 0,007242."""
    assert custo_por_tokens("openai/gpt-4o-mini", 30850, 4358) == 0.007242


def test_custo_de_modelo_fora_da_tabela_e_none():
    """Preço não confirmado não vira número: custo None, não estimado."""
    assert custo_por_tokens("qwen2.5-7b-instruct-1m", 1000, 1000) is None


def test_rodada_da_serie_carrega_so_as_canonicas(tmp_path, monkeypatch):
    from eval import serie_temporal

    for nome, serie in (
        ("metricas_20260901T000000Z_aaaa.json", True),
        ("metricas_20260902T000000Z_bbbb.json", False),
        ("metricas_20260903T000000Z_cccc.json", True),
    ):
        (tmp_path / nome).write_text(
            json.dumps(
                {
                    "timestamp": nome[9:24],
                    "commit": nome[26:30],
                    "serie": serie,
                    "metricas": {"latency_p95_ms": 1000},
                }
            ),
            encoding="utf-8",
        )
    monkeypatch.setattr(serie_temporal, "RESULTADOS", tmp_path)
    rodadas = serie_temporal.carregar_serie()
    assert [r["commit"] for r in rodadas] == ["aaaa", "cccc"]  # fora da série não entra
