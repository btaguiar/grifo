"""Contratos Pydantic da API — DC-2 da SPEC. Requisito FR-40."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    session_id: str | None = None
    curso: str


class Source(BaseModel):
    modulo: str
    aula: str
    timestamp: str | None = None
    score: float


class TokenUsage(BaseModel):
    input: int
    output: int


class AskResponse(BaseModel):
    answer: str
    sources: list[Source]
    #: False quando o sistema recusou (ADR 002). Implica answer == REFUSAL_MESSAGE
    #: e sources vazio.
    found: bool
    latency_ms: int
    tokens: TokenUsage


class HealthResponse(BaseModel):
    status: str
    qdrant: str
    collection: str
    version: str


class IngestRequest(BaseModel):
    path: str
    curso: str


class IngestResponse(BaseModel):
    documentos: int
    chunks: int
    tokens_embedding: int


class TopQuestion(BaseModel):
    question: str
    count: int
    found_rate: float


class TopQuestionsResponse(BaseModel):
    days: int
    total: int
    questions: list[TopQuestion]
