"""Contrato de saída `GrifoAnswer`/`SourceRef` (Fase 2): validadores como funções puras.

É o contrato que o instructor devolve ao modelo quando violado (max_retries=2) —
cada validador aqui é uma regra que a saída do LLM precisa cumprir sozinha, sem
conserto por regex no caminho de produção.
"""

import pytest
from pydantic import ValidationError

from grifo.config import REFUSAL_MESSAGE
from grifo.generation.schemas import (
    GrifoAnswer,
    SourceRef,
    pares_recuperados,
)

CHUNKS = [
    {"metadata": {"modulo": "2 - Metricas", "aula": "4 - CAC e LTV"}},
    {"metadata": {"modulo": "1 - Fundamentos", "aula": "1 - O que é Gestão 4.0"}},
]


def test_par_modulo_aula_valido_aceito_com_prefixo_numerico():
    """A citação "2" casa com o chunk "2 - Metricas" — mesma regra do fonte_bate."""
    with pares_recuperados(CHUNKS):
        ref = SourceRef(modulo="2", aula="4", localizador="00:22:14")
    assert ref.localizador == "00:22:14"


def test_par_ausente_dos_chunks_reprova():
    with (
        pares_recuperados(CHUNKS),
        pytest.raises(ValidationError, match="não está entre os trechos"),
    ):
        SourceRef(modulo="3", aula="9")


def test_fora_de_query_a_checagem_de_existencia_nao_se_aplica():
    """Sem contexto de query (construção direta), só os validadores estruturais valem."""
    ref = SourceRef(modulo="3", aula="9")
    assert ref.modulo == "3"


def test_found_sem_citacoes_reprova():
    with pytest.raises(ValidationError, match="ao menos uma citação"):
        GrifoAnswer(found=True, answer="Resposta fundamentada.", citations=[])


def test_found_false_com_resposta_diferente_da_recusa_reprova():
    with pytest.raises(ValidationError, match="exatamente"):
        GrifoAnswer(found=False, answer="Não sei responder isso.")


def test_found_false_com_citacoes_reprova():
    with pytest.raises(ValidationError, match="não pode carregar citações"):
        GrifoAnswer(
            found=False,
            answer=REFUSAL_MESSAGE,
            citations=[SourceRef(modulo="2", aula="4")],
        )


def test_recusa_exata_tolerante_a_espacos_extremos():
    """O modelo raramente devolve a string byte a byte: strip(), não regex por fora."""
    recusa = GrifoAnswer(found=False, answer=f"  {REFUSAL_MESSAGE}\n")
    assert recusa.answer.strip() == REFUSAL_MESSAGE


def test_contrato_valido_completo():
    with pares_recuperados(CHUNKS):
        resp = GrifoAnswer(
            found=True,
            answer="O CAC é o custo total de aquisição dividido pelos clientes "
            "[Módulo 2 - Metricas, Aula 4 - CAC e LTV].",
            citations=[SourceRef(modulo="2 - Metricas", aula="4 - CAC e LTV")],
        )
    assert resp.found is True and len(resp.citations) == 1
