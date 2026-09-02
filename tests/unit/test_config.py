"""Os parametros de partida da SPEC secao 7 estao no codigo como default.

Este teste nao valida que os numeros sejam bons -- eles nao sao, sao ponto de partida.
Valida que o codigo e a SPEC nao divergiram sem alguem perceber. Ao calibrar, atualize
os dois juntos: config.py, SPEC secao 7 e o registro em EVALUATION.md secao 4.
"""

from grifo.config import REFUSAL_MESSAGE, Settings


def test_parametros_de_partida_batem_com_a_spec():
    s = Settings(_env_file=None)
    assert s.chunk_size == 900
    assert s.chunk_overlap == 150
    assert s.retrieve_k == 20
    assert s.final_k == 5
    assert s.score_threshold == 0.45  # calibrado, ver EVALUATION.md 4.1
    assert s.hybrid_weights == (0.6, 0.4)
    assert s.max_answer_words == 200


def test_geracao_e_deterministica():
    """NFR-8: a avaliacao precisa ser reproduzivel."""
    assert Settings(_env_file=None).llm_temperature == 0.0


def test_mensagem_de_recusa_e_exata():
    """ADR 002 / FR-32: o texto e contrato. Mudou aqui, mudou a API e o prompt."""
    assert REFUSAL_MESSAGE == "Não encontrei isso no material do curso."


def test_golden_set_default_aponta_para_o_corpus_publico():
    """O golden set versionado e o de samples/. O do corpus real e gitignored."""
    s = Settings(_env_file=None)
    assert s.golden_set.as_posix() == "eval/golden_set.jsonl"
    assert s.eval_strict is True


def test_golden_set_e_configuravel_por_ambiente(monkeypatch):
    """Trocar de corpus nao pode exigir editar codigo (mesma regra do FR-10)."""
    monkeypatch.setenv("GOLDEN_SET", "eval/golden_set.local.jsonl")
    monkeypatch.setenv("EVAL_STRICT", "false")
    s = Settings(_env_file=None)
    assert s.golden_set.as_posix() == "eval/golden_set.local.jsonl"
    assert s.eval_strict is False
