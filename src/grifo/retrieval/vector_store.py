"""Wrapper do Qdrant: criacao da colecao, upsert e busca vetorial filtrada (FR-20).

O filtro por metadado (`curso`, `modulo`) e nativo do Qdrant e e uma das razoes da
escolha -- ver Stack no DOSSIE.md.

IDs determinísticos: uuid5 do `chunk_id`. Reindexar sobrescreve o ponto em vez de
duplicar -- é assim que a ingestão é idempotente (FR-15) sem limpar coleção.

O nome da coleção NÃO entra no id, e isso é deliberado. Ele entrava, e o efeito só
apareceu ao renomear o projeto: um alias de coleção mudava o id calculado, o
`score_by_ids` não achava mais nada, e o resgate léxico do BM25 parava de funcionar
**em silêncio** -- a busca continuava respondendo, só que sem os chunks resgatados.
Ids no Qdrant já são escopados por coleção, então o prefixo não protegia de colisão
nenhuma; só acoplava o dado a um nome que pode mudar.
"""

from __future__ import annotations

import math
import uuid
from functools import lru_cache
from typing import Any

from qdrant_client import QdrantClient, models

from grifo.config import settings

_UPSERT_BATCH = 64


@lru_cache(maxsize=1)
def _client() -> QdrantClient:
    return QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
        timeout=settings.qdrant_timeout,
    )


class _LocalEmbedder:
    """Embeddings locais via sentence-transformers (sem API, determinístico).

    Usado quando o provedor de LLM não oferece embeddings (ex.: Z.ai/GLM) —
    ou quando se quer indexação sem custo de API. Mesma interface dos
    OpenAIEmbeddings: `embed_documents` e `embed_query`.
    """

    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)

    def _embed(self, texts: list[str]) -> list[list[float]]:
        vetores = self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [v.tolist() for v in vetores]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text])[0]


@lru_cache(maxsize=1)
def _embedder() -> Any:
    if settings.embedding_provider == "local":
        return _LocalEmbedder(settings.embedding_model)

    from langchain_openai import OpenAIEmbeddings

    kwargs: dict[str, Any] = {"api_key": settings.openai_api_key or None}
    if settings.openai_base_url:
        # Fora da OpenAI, o batching por tiktoken não se aplica (tokenizer do
        # provedor difere): manda o texto como está e deixa o limite com o provedor.
        kwargs |= {
            "base_url": settings.openai_base_url,
            "check_embedding_ctx_length": False,
        }
    return OpenAIEmbeddings(model=settings.embedding_model, **kwargs)


def _point_id(chunk_id: str, collection: str | None = None) -> str:
    """Id estável do ponto, derivado SÓ do chunk_id (ver docstring do módulo).

    `collection` continua na assinatura porque as chamadas a passam, mas é ignorada de
    propósito: incluí-la amarrava o id ao nome da coleção e quebrava alias e rename.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


def _qdrant_filter(filters: dict | None) -> models.Filter | None:
    if not filters:
        return None
    #: list[Any] porque o `must` do Qdrant aceita união de tipos de condição (invariância).
    must: list[Any] = [
        models.FieldCondition(key=f"metadata.{campo}", match=models.MatchValue(value=valor))
        for campo, valor in filters.items()
        if valor is not None
    ]
    return models.Filter(must=must) if must else None


def ensure_collection(name: str, dim: int) -> None:
    """Cria a colecao se nao existir; se existir, exige que a dimensao bata.

    Trocar de modelo de embedding sem reindexar deixa a colecao com vetores de outra
    dimensao. Sem esta checagem o erro so aparece na hora da consulta, como um 400 cru
    do Qdrant ("expected dim: 256, got 384") no meio do /ask -- longe da causa.
    """
    if not _client().collection_exists(name):
        _client().create_collection(
            collection_name=name,
            vectors_config=models.VectorParams(size=dim, distance=models.Distance.COSINE),
        )
        return
    atual = _client().get_collection(name).config.params.vectors
    atual_dim = getattr(atual, "size", None)
    if atual_dim is not None and atual_dim != dim:
        raise ValueError(
            f"colecao '{name}' foi indexada com vetores de {atual_dim} dimensoes, mas "
            f"{settings.embedding_model} produz {dim}. Reindexe a colecao (ou aponte "
            f"QDRANT_COLLECTION para outra) antes de continuar."
        )


def _vetor_simples(vetor: object) -> list[float] | None:
    """O vetor do ponto como lista de floats, ou None se vier noutra forma.

    O `vector` do Qdrant e uma uniao: vetor simples, multivetor, mapa de vetores
    nomeados ou None. Este projeto usa so o primeiro caso -- qualquer outra forma e
    tratada como ausencia de vetor, e nao como algo a adivinhar.
    """
    if isinstance(vetor, list) and all(isinstance(x, int | float) for x in vetor):
        return [float(x) for x in vetor]
    return None


class VetorZeradoError(RuntimeError):
    """O ponto foi gravado, mas sem vetor utilizavel."""


def assert_vetores_gravados(chunk_id: str, collection: str | None = None) -> None:
    """Le de volta um ponto recem-gravado e exige que o vetor tenha norma > 0.

    Existe por causa de uma falha silenciosa real (2026-09-02): com `qdrant-client`
    1.19 contra servidor 1.12.4 -- combinacao que o pyproject permitia --, o upsert
    retornava sucesso e gravava o vetor ZERADO. Nada falhava: a ingestao terminava
    limpa, o /ask respondia, e a busca vetorial estava morta. Todo score dava 0.0, o
    gate do FR-24 rejeitava tudo, e so os chunks resgatados pelo BM25 chegavam ao
    prompt -- resposta pior, sem um erro sequer.

    O pin de versao conserta a causa conhecida; isto pega a classe do problema. Uma
    ingestao que nao deixa o indice pesquisavel tem de falhar na hora, nao na primeira
    pergunta de um aluno.
    """
    colecao = collection or settings.qdrant_collection
    pontos = _client().retrieve(
        collection_name=colecao, ids=[_point_id(chunk_id)], with_vectors=True
    )
    if not pontos:
        raise VetorZeradoError(f"chunk '{chunk_id}' nao foi encontrado apos o upsert")
    vetor = _vetor_simples(pontos[0].vector)
    if vetor is None or math.sqrt(sum(x * x for x in vetor)) == 0.0:
        raise VetorZeradoError(
            f"o vetor de '{chunk_id}' foi gravado zerado na colecao '{colecao}': a busca "
            "vetorial ficaria morta em silencio. Causa conhecida: divergencia de versao "
            "entre qdrant-client e o servidor Qdrant -- confira os dois pins."
        )


def upsert_chunks(chunks: list[dict], collection: str | None = None) -> int:
    """Indexa os chunks (embeda o texto aqui). Devolve a quantidade escrita."""
    if not chunks:
        return 0
    colecao = collection or settings.qdrant_collection
    vectors = _embedder().embed_documents([c["text"] for c in chunks])
    ensure_collection(colecao, dim=len(vectors[0]))
    escritos = 0
    for i in range(0, len(chunks), _UPSERT_BATCH):
        lote = chunks[i : i + _UPSERT_BATCH]
        vetores = vectors[i : i + _UPSERT_BATCH]
        points = [
            models.PointStruct(
                id=_point_id(c["id"], colecao),
                vector=v,
                payload={"id": c["id"], "text": c["text"], "metadata": c["metadata"]},
            )
            for c, v in zip(lote, vetores, strict=False)
        ]
        _client().upsert(collection_name=colecao, points=points, wait=True)
        escritos += len(points)
    # Le de volta um ponto e exige vetor com norma: quem grava e quem confere.
    assert_vetores_gravados(chunks[0]["id"], colecao)
    return escritos


def search(
    query_vector: list[float],
    k: int,
    filters: dict | None = None,
    collection: str | None = None,
) -> list[dict]:
    """Busca vetorial com filtro opcional por metadado. Score = similaridade cosseno."""
    colecao = collection or settings.qdrant_collection
    resp = _client().query_points(
        collection_name=colecao,
        query=query_vector,
        limit=k,
        query_filter=_qdrant_filter(filters),
        with_payload=True,
    )
    return [
        {
            "id": (p.payload or {})["id"],
            "text": (p.payload or {})["text"],
            "metadata": (p.payload or {})["metadata"],
            "score": float(p.score),
        }
        for p in resp.points
    ]


def _cosine(a: list[float], b: list[float]) -> float:
    num = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return num / (na * nb) if na and nb else 0.0


def score_by_ids(
    query_vector: list[float], chunk_ids: list[str], collection: str | None = None
) -> list[dict]:
    """Recupera chunks por id e calcula o cosseno contra a pergunta.

    Existe para o resgate do BM25 (ADR 001): um chunk que só a busca léxica encontrou
    não tem score vindo do Qdrant, e sem similaridade absoluta ele não poderia passar
    pelo gate de recusa do FR-24. Aqui ele ganha o mesmo score que teria se a busca
    vetorial o tivesse trazido — o gate continua valendo para todos os candidatos.
    """
    if not chunk_ids:
        return []
    colecao = collection or settings.qdrant_collection
    pontos = _client().retrieve(
        collection_name=colecao,
        ids=[_point_id(c, colecao) for c in chunk_ids],
        with_payload=True,
        with_vectors=True,
    )
    hits = []
    for p in pontos:
        payload = p.payload or {}
        vetor = _vetor_simples(p.vector)
        if vetor is None:
            continue
        hits.append(
            {
                "id": payload["id"],
                "text": payload["text"],
                "metadata": payload["metadata"],
                "score": _cosine(query_vector, vetor),
            }
        )
    return hits


def fetch_all(filters: dict | None = None, collection: str | None = None) -> list[dict]:
    """Scroll completo da coleção filtrada — base para construir o índice BM25."""
    colecao = collection or settings.qdrant_collection
    resultados: list[dict] = []
    offset = None
    while True:
        pontos, offset = _client().scroll(
            collection_name=colecao,
            limit=256,
            offset=offset,
            scroll_filter=_qdrant_filter(filters),
            with_payload=True,
        )
        resultados.extend(
            {
                "id": (p.payload or {})["id"],
                "text": (p.payload or {})["text"],
                "metadata": (p.payload or {})["metadata"],
            }
            for p in pontos
        )
        if offset is None:
            break
    return resultados


def healthcheck() -> str | None:
    """FR-41: devolve o motivo da degradacao, ou None quando esta tudo de pe.

    Conectividade nao basta. Medido: com a colecao configurada ausente, o /health
    respondia `ok` -- porque o Qdrant estava no ar -- e TODO /ask devolvia 500 com o 404
    do Qdrant por baixo. O FR-41 pede o contrario: "o servico responde, mas se declara
    degradado sem o indice". Sem o indice ele nao responde nada, e precisa dizer isso
    antes de receber a pergunta de um aluno.
    """
    try:
        _client().get_collections()
    except Exception:
        return "down"
    if not _client().collection_exists(settings.qdrant_collection):
        # Estado normal entre `docker compose up` e `docker compose run ingest`.
        return "sem indice"
    return None


def warmup() -> None:
    """Instancia o embedder antes da primeira pergunta.

    Com `EMBEDDING_PROVIDER=local` isso importa o torch e carrega os pesos do
    SentenceTransformer do disco, que é a parte cara; com provedor remoto só constrói o
    cliente, sem tocar a rede. Em ambos os casos o custo sai do caminho do usuário.
    """
    _embedder()
