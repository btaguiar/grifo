"""API FastAPI (FR-40 a FR-44).

Endpoints:
    POST /ask                        DC-2
    POST /ingest                     protegido por INGEST_TOKEN (FR-42)
    GET  /health                     503 se o Qdrant estiver fora (FR-41)
    GET  /analytics/top-questions    FR-43

O Swagger em /docs e peca de portfolio: descreva os endpoints com capricho.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from grifo.analytics.question_log import log_question, top_questions
from grifo.api.schemas import (
    AskRequest,
    AskResponse,
    HealthResponse,
    IngestRequest,
    IngestResponse,
    TopQuestion,
    TopQuestionsResponse,
)
from grifo.config import settings
from grifo.generation import chain
from grifo.ingest import pipeline
from grifo.retrieval import hybrid, vector_store

log = logging.getLogger(__name__)


def _warmup(curso: str) -> None:
    """Paga o custo de inicializacao fora do caminho do aluno (EVALUATION.md 4.5).

    Sem isso a primeira pergunta de cada processo custa ~10s: carga do modelo de
    embedding mais o scroll completo do Qdrant para montar o indice BM25. Quem pagava
    era o primeiro aluno depois de cada deploy.

    O `curso` importa: o cache do BM25 e chaveado por filtro e a chain sempre consulta
    com `{"curso": ...}` (ver `chain._retrieve_state`). Aquecer sem filtro construiria
    um indice que nenhuma pergunta usa.

    Falhar aqui nao derruba o boot nem a ingestao: quem reporta o Qdrant fora e o
    /health, e a construcao volta a ser preguicosa na primeira pergunta.
    """
    try:
        vector_store.warmup()
        chunks = hybrid.warmup(filters={"curso": curso})
        log.info("warmup: indice BM25 pronto, %d chunks (curso=%s)", chunks, curso)
    except Exception:
        log.warning("warmup falhou; a primeira pergunta paga a construcao", exc_info=True)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """FR-41: a API so aceita trafego depois de aquecer embedder e indice lexico."""
    _warmup(settings.curso_nome)
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Grifo",
    description=(
        "Assistente que responde dúvidas de alunos usando exclusivamente o material do "
        "curso, sempre citando módulo e aula — e recusando explicitamente quando a "
        "resposta não está no material (ADR 002)."
    ),
    version="0.1.0",
)


@app.exception_handler(RequestValidationError)
async def payload_invalido_400(_request, exc):
    """DC-2: payload inválido responde 400, não o 422 padrão do FastAPI."""
    return JSONResponse(status_code=400, content={"detail": exc.errors()})


@app.post(
    "/ask",
    response_model=AskResponse,
    summary="Responde uma dúvida do aluno",
    description=(
        "Fluxo completo: retrieval híbrido → reranking → geração com citação. "
        "`found: false` significa recusa: `answer` é a string de recusa exata e "
        "`sources` vem vazio (DC-2)."
    ),
    responses={500: {"description": "Falha do provedor LLM (body traz `request_id`)"}},
)
def ask(payload: AskRequest) -> AskResponse:
    try:
        resposta = chain.answer(payload.question, payload.curso, payload.session_id)
    except Exception as exc:
        request_id = uuid.uuid4().hex
        raise HTTPException(
            status_code=500,
            detail={"request_id": request_id, "error": "falha do provedor LLM"},
        ) from exc
    log_question(
        payload.question,
        {**resposta, "session_id": payload.session_id, "curso": payload.curso},
    )
    return AskResponse(**resposta)


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Status do serviço e do Qdrant",
    responses={503: {"description": "Qdrant indisponível"}},
)
def health() -> HealthResponse:
    """FR-41: o serviço responde, mas se declara degradado sem o índice."""
    motivo = vector_store.healthcheck()
    if motivo:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "degraded",
                "qdrant": motivo,
                "collection": settings.qdrant_collection,
            },
        )
    return HealthResponse(
        status="ok",
        qdrant="up",
        collection=settings.qdrant_collection,
        version=app.version,
    )


@app.post(
    "/ingest",
    response_model=IngestResponse,
    summary="Dispara a ingestão de um diretório",
    description="Protegido por token (FR-42). O path deve existir e ficar sob o diretório da API.",
    responses={
        401: {"description": "Token ausente ou inválido"},
        400: {"description": "Path inválido"},
    },
)
def ingest(
    payload: IngestRequest, x_ingest_token: str = Header(default="", alias="X-Ingest-Token")
) -> IngestResponse:
    if not settings.ingest_token or x_ingest_token != settings.ingest_token:
        raise HTTPException(status_code=401, detail="token ausente ou inválido")
    raiz = Path.cwd().resolve()
    alvo = Path(payload.path).resolve()
    try:
        alvo.relative_to(raiz)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="path fora do diretório permitido") from exc
    if not alvo.is_dir():
        raise HTTPException(status_code=400, detail="path não é um diretório")
    contagens = pipeline.ingest(str(alvo), payload.curso)
    # `pipeline.ingest` descartou o indice BM25 velho; reconstruir agora e o que impede
    # o proximo aluno de pagar o rebuild no meio do /ask.
    _warmup(payload.curso)
    return IngestResponse(**contagens)


@app.get(
    "/analytics/top-questions",
    response_model=TopQuestionsResponse,
    summary="Dúvidas mais frequentes (FR-43)",
    description="Perguntas agrupadas por proximidade, ordenadas por frequência.",
)
def analytics_top_questions(
    days: int = Query(default=7, ge=1, le=90, description="janela em dias"),
) -> TopQuestionsResponse:
    grupos = top_questions(days=days)
    return TopQuestionsResponse(
        days=days,
        total=len(grupos),
        questions=[
            TopQuestion(question=g["question"], count=g["count"], found_rate=g["found_rate"])
            for g in grupos
        ],
    )
