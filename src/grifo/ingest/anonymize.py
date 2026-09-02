"""Remocao de PII antes da indexacao e antes do log (FR-12, FR-52).

Transcricoes de aula ao vivo contem nomes de alunos, e-mails e as vezes dados de negocio
de quem faz a pergunta. Este passo roda na ingestao E sobre a pergunta do aluno antes de
gravar no question_log.

Cobertura minima da v1: e-mail, telefone, CPF. Substituicao por placeholder tipado
(`[EMAIL]`, `[TELEFONE]`, `[CPF]`) para o texto continuar legivel ao LLM.
"""

from __future__ import annotations

import re

EMAIL_PLACEHOLDER = "[EMAIL]"
PHONE_PLACEHOLDER = "[TELEFONE]"
CPF_PLACEHOLDER = "[CPF]"

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
#: DDD com ou sem parenteses, nono digito opcional, com ou sem hifen, DDI +55 opcional.
_PHONE_RE = re.compile(r"(?:\+55\s?)?(?:\(\d{2}\)|\d{2})\s?9?\d{4}-?\d{4}")
#: CPF com ou sem pontuacao (11 digitos).
_CPF_RE = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")


def anonymize(text: str) -> str:
    """Aplica todas as regras de anonimizacao ao texto.

    Ordem importa: e-mail primeiro (nunca colide), telefone antes do CPF para nao
    mascarar um CPF formatado como se fosse telefone.
    """
    text = _EMAIL_RE.sub(EMAIL_PLACEHOLDER, text)
    text = _PHONE_RE.sub(PHONE_PLACEHOLDER, text)
    text = _CPF_RE.sub(CPF_PLACEHOLDER, text)
    return text
