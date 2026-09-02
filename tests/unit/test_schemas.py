"""Contrato DC-2 da API (FR-40)."""

import pytest
from pydantic import ValidationError

from grifo.api.schemas import AskRequest, AskResponse


def test_ask_request_exige_pergunta_nao_vazia():
    with pytest.raises(ValidationError):
        AskRequest(question="", curso="Curso Exemplo")


def test_ask_response_de_recusa():
    """found=false implica sources vazio (DC-2)."""
    r = AskResponse(
        answer="Não encontrei isso no material do curso.",
        sources=[],
        found=False,
        latency_ms=120,
        tokens={"input": 320, "output": 12},
    )
    assert r.found is False
    assert r.sources == []


def test_ask_response_com_fonte_e_timestamp():
    """FR-33: quando a fonte e transcricao, o timestamp vira link para o minuto."""
    r = AskResponse(
        answer="O CAC é o custo total de aquisição dividido pelo número de clientes "
        "[Módulo 2, Aula 4].",
        sources=[
            {
                "modulo": "2 - Métricas",
                "aula": "4 - CAC e LTV",
                "timestamp": "00:22:14",
                "score": 0.81,
            }
        ],
        found=True,
        latency_ms=1840,
        tokens={"input": 2100, "output": 90},
    )
    assert r.sources[0].timestamp == "00:22:14"
