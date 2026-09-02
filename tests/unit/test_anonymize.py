"""FR-12: nenhum PII sobrevive à anonimização; substituição por placeholder tipado."""

import re

from grifo.ingest.anonymize import (
    CPF_PLACEHOLDER,
    EMAIL_PLACEHOLDER,
    PHONE_PLACEHOLDER,
    anonymize,
)


def test_email_telefone_cpf_sao_substituidos(texto_com_pii):
    out = anonymize(texto_com_pii)
    assert "contato@exemplo.com.br" not in out
    assert "(11) 98765-4321" not in out
    assert "123.456.789-09" not in out
    assert EMAIL_PLACEHOLDER in out
    assert PHONE_PLACEHOLDER in out
    assert CPF_PLACEHOLDER in out


def test_email_generico_e_telefone_com_ddi_tambem_somem():
    out = anonymize("mande para a.b_99+x@org.net ou ligue +55 21 3456-7890")
    assert not re.search(r"[\w.+-]+@[\w.-]+\.\w+", out)
    assert "+55" not in out
    assert "3456-7890" not in out


def test_texto_normal_permanece_intacto():
    texto = "O CAC e o LTV sao metricas de aquisicao e retencao."
    assert anonymize(texto) == texto
