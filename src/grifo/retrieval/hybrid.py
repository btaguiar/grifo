"""Retriever hibrido: vetorial + BM25 fundidos por RRF (ADR 001).

Requisitos: FR-21 (BM25), FR-22 (RRF com pesos configuraveis), FR-24 (threshold).

Por que hibrido: material de curso e cheio de jargao, sigla e nome de ferramenta. Busca
puramente semantica erra quando o aluno pergunta pelo nome exato de algo citado uma vez;
o embedding dilui o termo raro no significado geral do trecho. BM25 pega isso.

Papel de cada componente:
    * o cosseno do Qdrant DECIDE quem entra pela via semantica: abaixo de
      SCORE_THRESHOLD fica fora (FR-24);
    * o BM25 PROMOVE a ordem via RRF, subindo o chunk do termo exato que o embedding
      deixou la embaixo;
    * o BM25 tambem RESGATA: um chunk fora do top-k vetorial entra se casar um termo
      que alguma aula do corpus ensina (ver `termos_resgataveis`).

O resgate existe porque a versao anterior anulava o proprio ADR 001. Medido no corpus
real: "O que e o Pulse?" devolvia ZERO chunks embora o termo apareca 8x numa aula -- o
cosseno daquele chunk contra a pergunta e 0.026, ruido, porque um nome proprio citado
num trecho de 900 chars nao move o embedding. Nenhum threshold o admitiria. Quem admite
tem de ser a evidencia lexica.

Medido no golden set do corpus real (53 itens dentro do escopo, 11 fora), threshold 0.53:

    resgate desligado                 fonte@5 68%   fonte@20 77%   recusa 82%
    so IDF (sem concentracao)         fonte@5 75%   fonte@20 87%   recusa 27%  <- quebra
    IDF + concentracao (atual)        fonte@5 74%   fonte@20 83%   recusa 82%

FR-24 e o gatilho da recusa: se nada passa dos dois gates, o retriever devolve lista
vazia e a chain responde REFUSAL_MESSAGE.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict

from rank_bm25 import BM25Okapi

from grifo.config import settings
from grifo.retrieval import vector_store

#: Constante clássica do Reciprocal Rank Fusion.
RRF_K = 60

_STOPWORDS = frozenset(
    (
        "a",
        "o",
        "as",
        "os",
        "um",
        "uma",
        "uns",
        "umas",
        "de",
        "do",
        "da",
        "dos",
        "das",
        "em",
        "no",
        "na",
        "nos",
        "nas",
        "para",
        "por",
        "com",
        "sem",
        "que",
        "qual",
        "quais",
        "como",
        "onde",
        "quando",
        "quem",
        "porque",
        "me",
        "meu",
        "minha",
        "você",
        "vocês",
        "é",
        "são",
        "e",
        "ou",
        "se",
        "ao",
        "aos",
        "à",
        "às",
        "isso",
        "este",
        "esta",
        "esse",
        "essa",
        "dele",
        "dela",
    )
)


def _tokenize(text: str) -> list[str]:
    norm = unicodedata.normalize("NFKD", text.lower())
    norm = "".join(c for c in norm if not unicodedata.combining(c))
    return [t for t in re.findall(r"[a-z0-9]+", norm) if t not in _STOPWORDS and len(t) > 1]


def _termos_ensinados(docs: list[dict], tokens: list[list[str]]) -> frozenset[str]:
    """Tokens que alguma aula ensina: recorrentes e concentrados numa aula só.

    Sem metadado de aula (testes de índice puro) o critério cai para só a contagem.
    """
    por_termo: dict[str, Counter] = defaultdict(Counter)
    for doc, toks in zip(docs, tokens, strict=False):
        aula = (doc.get("metadata") or {}).get("aula", "?")
        for t in set(toks):
            por_termo[t][aula] += 1
    ensinados = set()
    for termo, aulas in por_termo.items():
        total = sum(aulas.values())
        if total < settings.bm25_rescue_min_chunks:
            continue
        if aulas.most_common(1)[0][1] / total >= settings.bm25_rescue_min_concentracao:
            ensinados.add(termo)
    return frozenset(ensinados)


class BM25Index:
    """Índice léxico puro sobre [{"id", "text"}] — unit-testável sem Qdrant."""

    def __init__(self, docs: list[dict]):
        self.ids: list[str] = [d["id"] for d in docs]
        tokens = [_tokenize(d["text"]) for d in docs]
        self._por_id: dict[str, set[str]] = {
            cid: set(t) for cid, t in zip(self.ids, tokens, strict=False)
        }
        self._bm25 = BM25Okapi(tokens) if any(tokens) else None
        self._ensinados = _termos_ensinados(docs, tokens)

    def top(self, question: str, k: int) -> list[tuple[str, float]]:
        """[(id, score)] ordenado por relevância, só com score > 0."""
        if not self._bm25:
            return []
        scores = self._bm25.get_scores(_tokenize(question))
        ordem = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        return [(self.ids[i], float(scores[i])) for i in ordem[:k] if scores[i] > 0]

    def termos_resgataveis(self, question: str) -> set[str]:
        """Tokens da pergunta que uma aula do corpus efetivamente ENSINA.

        IDF sozinho não serve: mede raridade, não pertencimento ao domínio. Medido neste
        corpus, `pulse` (IDF 7.3) e `bolo` (IDF 7.1) são igualmente raros — mas o
        primeiro é um conceito de uma aula e o segundo é metáfora de cozinha.

        O que separa é a forma da ocorrência. Termo ensinado aparece várias vezes e
        concentrado numa aula (`pulse`: 4 chunks, 1 aula, 100%; `apqc`: 4, 1, 100%).
        Termo incidental se espalha (`bolo`: 5 chunks, 4 aulas, 40%) ou é aparição
        única (`poema`: 1 chunk). Daí os três critérios combinados.
        """
        if not self._bm25:
            return set()
        return {
            t
            for t in _tokenize(question)
            if self._bm25.idf.get(t, 0.0) >= settings.bm25_rescue_min_idf and t in self._ensinados
        }

    def contem_algum(self, chunk_id: str, termos: set[str]) -> bool:
        return bool(self._por_id.get(chunk_id, frozenset()) & termos)


_bm25_cache: dict[tuple, BM25Index] = {}


def _get_bm25(filters: dict | None) -> BM25Index:
    """Índice BM25 sobre o mesmo corpus do Qdrant (filtrado), cacheado por processo.

    O corpus de um curso é pequeno (ordem de centenas de chunks): reconstruir na
    primeira query do processo é mais simples e menos bugável que serializar.
    """
    chave = tuple(sorted((filters or {}).items()))
    if chave not in _bm25_cache:
        _bm25_cache[chave] = BM25Index(vector_store.fetch_all(filters=filters))
    return _bm25_cache[chave]


def invalidate_cache() -> None:
    """Descarta o índice BM25 em memória. Obrigatório após qualquer escrita no Qdrant.

    O cache é um snapshot do corpus tirado na primeira query do processo. Sem invalidar,
    o material recém-ingerido fica visível para a busca vetorial e invisível para o
    BM25: o resgate do ADR 001 — o nome exato citado uma vez no material — deixa de
    achar justamente o conteúdo mais novo. E falha calada, porque a API continua
    respondendo, só que pior.
    """
    _bm25_cache.clear()


def warmup(filters: dict | None = None) -> int:
    """Constrói o índice BM25 fora do caminho do usuário. Devolve o nº de chunks.

    O `filters` tem de ser o MESMO que a consulta vai usar: o cache é chaveado por
    filtro (ver `_get_bm25`) e a chain sempre passa `{"curso": ...}`. Aquecer com `None`
    constrói um índice que nenhuma pergunta usa — o custo é pago duas vezes.
    """
    return len(_get_bm25(filters).ids)


def reciprocal_rank_fusion(
    rankings: list[list], weights: tuple[float, float]
) -> list[tuple[object, float]]:
    """Funde rankings de ids pela fórmula RRF: soma de w / (K + rank).

    Retorna [(id, score)] em ordem decrescente. Os ids precisam ser hashable.
    """
    scores: dict[object, float] = {}
    for ranking, peso in zip(rankings, weights, strict=False):
        for rank, chave in enumerate(ranking, start=1):
            scores[chave] = scores.get(chave, 0.0) + peso / (RRF_K + rank)
    return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)


def retrieve(question: str, k: int, filters: dict | None = None) -> list[dict]:
    """Busca hibrida com fusao RRF, ja aplicando o SCORE_THRESHOLD (FR-24).

    O chunk que so o BM25 encontrou tambem entra: buscamos o vetor dele e calculamos o
    cosseno, entao o gate de recusa continua valendo sobre TODOS os candidatos. Sem esse
    resgate o BM25 so reordena o que o vetorial ja trouxe, e o caso que justifica o
    ADR 001 -- o nome exato citado uma vez no material -- nunca e recuperado.
    """
    vetor = vector_store._embedder().embed_query(question)
    hits_vetorial = vector_store.search(vetor, k, filters=filters)

    bm25 = _get_bm25(filters)
    ranking_vetorial = [h["id"] for h in hits_vetorial]
    ranking_bm25 = [cid for cid, _score in bm25.top(question, k)]

    por_id = {h["id"]: h for h in hits_vetorial}

    # Resgate lexico: o chunk que so o BM25 achou entra se casar um termo RARO da
    # pergunta. O cosseno dele nao serve de criterio -- medido em 0.026 no caso "Pulse",
    # ruido puro -- porque um nome proprio citado 8x num chunk de 900 chars nao move o
    # embedding. Quem admite e a evidencia lexica; o cosseno vai junto so para exibicao.
    raros = bm25.termos_resgataveis(question)
    resgatados = {
        cid for cid in ranking_bm25 if cid not in por_id and bm25.contem_algum(cid, raros)
    }
    for hit in vector_store.score_by_ids(vetor, sorted(resgatados)):
        por_id[hit["id"]] = hit | {"via": "bm25"}

    fused = reciprocal_rank_fusion([ranking_vetorial, ranking_bm25], settings.hybrid_weights)

    resultado = []
    for cid, _rrf in fused:
        candidato = por_id.get(cid)
        if candidato is None:  # id do BM25 que sumiu do indice entre o cache e a consulta
            continue
        # FR-24: o gate de cosseno vale para o que veio do vetorial. O resgatado ja
        # passou por um gate proprio (termo raro), entao nao e barrado pelo cosseno.
        if cid not in resgatados and candidato["score"] < settings.score_threshold:
            continue
        resultado.append(candidato)
    return resultado[:k]
