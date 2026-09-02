"""FR-31/32/35: o prompt carrega a regra de citação; format_context expõe módulo/aula."""

from grifo.config import REFUSAL_MESSAGE
from grifo.generation.prompts import ANSWER_SYSTEM_PROMPT, format_context

CHUNKS = [
    {
        "id": "a:chunk0",
        "text": "O CAC é o custo total dividido pelos clientes.",
        "score": 0.8,
        "metadata": {
            "modulo": "2 - Metricas",
            "aula": "4 - CAC e LTV",
            "timestamp_inicio": "00:22:14",
            "pagina": None,
        },
    },
    {
        "id": "b:chunk0",
        "text": "Preço por valor.",
        "score": 0.7,
        "metadata": {
            "modulo": "3 - Estrategia",
            "aula": "7 - Precificacao",
            "timestamp_inicio": None,
            "pagina": 3,
        },
    },
]


def test_prompt_contem_recusa_exata_e_regra_de_citacao():
    assert REFUSAL_MESSAGE in ANSWER_SYSTEM_PROMPT
    assert "[Módulo X, Aula Y]" in ANSWER_SYSTEM_PROMPT
    assert "{max_words}" in ANSWER_SYSTEM_PROMPT
    assert "{context}" in ANSWER_SYSTEM_PROMPT and "{question}" in ANSWER_SYSTEM_PROMPT


def test_format_context_expoe_localizadores_legiveis():
    ctx = format_context(CHUNKS)
    assert "[1]" in ctx and "[2]" in ctx
    assert "Módulo: 2 - Metricas" in ctx
    assert "Aula: 4 - CAC e LTV" in ctx
    assert "Timestamp: 00:22:14" in ctx  # FR-33: timestamp visível ao modelo
    assert "Página: 3" in ctx
    assert "custo total" in ctx


def test_format_context_omite_localizador_ausente():
    ctx = format_context([CHUNKS[0]])
    assert "Página" not in ctx
