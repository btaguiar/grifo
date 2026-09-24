"""Contrato de saída do LLM (plano de execução, Fase 2): Pydantic + instructor.

Até aqui a saída do modelo era prosa livre tratada por regex, e o `_ensure_citation`
consertava a citação à força em 9 de 44 respostas da rodada de 2026-08-24
(EVALUATION.md 5.5) — o que tornava a métrica de citação artificial e fazia qualquer
mudança de prompt mover números sem rastro. O contrato inverte a direção: o modelo
devolve structured output validado por Pydantic; se violou, o instructor devolve o
erro ao modelo (max_retries=2) em vez de o código consertar a saída por fora.

`SourceRef` valida o par módulo/aula contra os chunks recuperados DA query via
`ContextVar`: validador Pydantic não recebe contexto na assinatura, e o conjunto
permitido muda a cada pergunta. Fora do contexto de uma query (construção direta em
teste), a checagem de existência não se aplica — os demais validadores sempre valem.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from pydantic import BaseModel, model_validator

from grifo.config import REFUSAL_MESSAGE


def _numero(valor: str) -> str:
    """Prefixo numérico de módulo/aula: "2 - Metricas" casa "2".

    A mesma regra do `fonte_bate` do run_eval: o material usa rótulos longos
    ("2 - Metricas") e a citação do modelo pode vir só com o número.
    """
    m = re.match(r"\s*(\d+)", valor or "")
    return m.group(1) if m else (valor or "").strip()


_PARES_RECUPERADOS: ContextVar[frozenset[tuple[str, str]] | None] = ContextVar(
    "grifo_pares_recuperados", default=None
)


@contextmanager
def pares_recuperados(chunks: list[dict]) -> Iterator[None]:
    """Registra os pares módulo/aula válidos para ESTA query.

    O validador de `SourceRef` lê deste contexto: citação de módulo/aula que não
    está entre os trechos recuperados é atribuir fonte não consultada — e é
    exatamente o erro que o retry instruído precisa devolver ao modelo.
    """
    token = _PARES_RECUPERADOS.set(
        frozenset(
            (_numero(c["metadata"]["modulo"]), _numero(c["metadata"]["aula"])) for c in chunks
        )
    )
    try:
        yield
    finally:
        _PARES_RECUPERADOS.reset(token)


class SourceRef(BaseModel):
    """Fonte citada pela resposta: o par módulo/aula precisa existir no recuperado."""

    modulo: str
    aula: str
    #: Timestamp do vídeo ou página do PDF — "" quando o trecho não tem localizador.
    localizador: str = ""

    @model_validator(mode="after")
    def par_existe_no_recuperado(self) -> SourceRef:
        permitidos = _PARES_RECUPERADOS.get()
        if permitidos is None or (_numero(self.modulo), _numero(self.aula)) in permitidos:
            return self
        raise ValueError(
            f"par módulo/aula ({self.modulo!r}, {self.aula!r}) não está entre os "
            "trechos recuperados — cite módulo e aula exatamente como aparecem nos "
            "trechos fornecidos"
        )


class GrifoAnswer(BaseModel):
    """Contrato DC-2 na borda do LLM: found/citations coerentes entre si.

    A recusa é string exata (FR-32): `found=False` só é válido com a recusa literal
    e sem citações. `found=True` sem citações é resposta sem fundação — o caso que
    antes o `_ensure_citation` maquiava.
    """

    found: bool
    answer: str
    citations: list[SourceRef] = []

    @model_validator(mode="after")
    def coerencia_found_citacoes(self) -> GrifoAnswer:
        if self.found:
            if not self.citations:
                raise ValueError("found=True exige ao menos uma citação em citations")
        else:
            if self.answer.strip() != REFUSAL_MESSAGE:
                raise ValueError(
                    f"found=False exige answer exatamente '{REFUSAL_MESSAGE}' "
                    f"(recebido: {self.answer.strip()!r})"
                )
            if self.citations:
                raise ValueError("found=False não pode carregar citações")
        return self
