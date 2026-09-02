"""FR-21 (BM25), FR-22 (RRF com pesos configuráveis), FR-24 (threshold de recusa)."""

from types import SimpleNamespace

from grifo.retrieval import hybrid
from grifo.retrieval.hybrid import BM25Index, reciprocal_rank_fusion, retrieve


def test_rrf_ordem_depende_dos_pesos():
    """FR-22: HYBRID_WEIGHTS altera a ordem final de forma observável."""
    a_sobe = reciprocal_rank_fusion([["a", "b"], ["b", "a"]], (0.6, 0.4))
    b_sobe = reciprocal_rank_fusion([["a", "b"], ["b", "a"]], (0.4, 0.6))
    assert a_sobe[0][0] == "a"
    assert b_sobe[0][0] == "b"


def test_rrf_funde_a_uniao_dos_rankings():
    fused = dict(reciprocal_rank_fusion([["a"], ["b"]], (0.5, 0.5)))
    assert set(fused) == {"a", "b"}


def test_rrf_premia_topo_das_duas_listas():
    fused = reciprocal_rank_fusion([["a", "x", "y"], ["x", "a", "z"]], (0.5, 0.5))
    top2 = {k for k, _ in fused[:2]}
    assert top2 == {"a", "x"}


def test_bm25_recupera_sigla_citada_uma_vez():
    """FR-21: a busca exata que o embedding dilui e o BM25 pega."""
    docs = [
        {"id": "x", "text": "refinamento geral do processo comercial da empresa"},
        {"id": "y", "text": "planejamento de metas trimestrais do time de vendas"},
        {"id": "z", "text": "rituais de acompanhamento semanal dos indicadores"},
        {"id": "s", "text": "use a sigla RFM para segmentar a base de clientes"},
    ]
    top = BM25Index(docs).top("o que é RFM?", 4)
    assert top[0][0] == "s"


def test_bm25_normaliza_acentos_e_ignora_stopwords():
    docs = [
        {"id": "a", "text": "Precificação por valor captura a disposição a pagar"},
        {"id": "b", "text": "outro assunto qualquer sobre gestão de equipe"},
        {"id": "c", "text": "mais um texto distrator sobre reuniões e agenda"},
    ]
    top = BM25Index(docs).top("o que é precificacao?", 3)
    assert top[0][0] == "a"


def _fake_vector_store(hits, resgatados=()):
    return SimpleNamespace(
        _embedder=lambda: SimpleNamespace(embed_query=lambda q: [0.0, 1.0]),
        search=lambda v, k, filters=None: hits,
        score_by_ids=lambda v, ids, collection=None: list(resgatados),
    )


def test_threshold_descarta_scores_baixos(monkeypatch):
    """FR-24: query fora do domínio → 0 chunks acima do threshold."""
    monkeypatch.setattr(
        hybrid,
        "vector_store",
        _fake_vector_store([{"id": "a", "text": "t", "metadata": {}, "score": 0.10}]),
    )
    monkeypatch.setattr(hybrid, "_get_bm25", lambda filters: BM25Index([]))
    assert retrieve("qual a receita do bolo de cenoura?", 5) == []


def test_retrieve_devolve_somente_acima_do_threshold(monkeypatch):
    hits = [
        {"id": "a", "text": "cac", "metadata": {}, "score": 0.80},
        {"id": "b", "text": "ltv", "metadata": {}, "score": 0.20},
    ]
    monkeypatch.setattr(hybrid, "vector_store", _fake_vector_store(hits))
    monkeypatch.setattr(hybrid, "_get_bm25", lambda filters: BM25Index([]))
    out = retrieve("como calcular o cac", 5)
    assert [h["id"] for h in out] == ["a"]


def test_bm25_pode_promover_a_ordem_sem_violar_threshold(monkeypatch):
    """FR-22 no contexto do retrieve: o BM25 reordena, o cosseno continua decidindo quem entra."""
    hits = [
        {"id": "a", "text": "custo de aquisição", "metadata": {}, "score": 0.70},
        {"id": "b", "text": "use a sigla RFM para segmentar", "metadata": {}, "score": 0.65},
    ]
    monkeypatch.setattr(hybrid, "vector_store", _fake_vector_store(hits))
    monkeypatch.setattr(
        hybrid,
        "_get_bm25",
        lambda filters: BM25Index(
            [{"id": "b", "text": "RFM"}, {"id": "a", "text": "x"}, {"id": "c", "text": "y"}]
        ),
    )
    out = retrieve("o que é RFM?", 5)
    assert [h["id"] for h in out] == ["b", "a"]


def _corpus_com_termo_ensinado():
    """Um termo concentrado numa aula (ensinado) e um espalhado (metafora)."""
    docs = []
    for i in range(4):  # 'pulse' concentrado: 4 chunks, todos na Aula 2
        docs.append(
            {
                "id": f"a2:c{i}",
                "text": f"o pulse organiza o ritmo da companhia {i}",
                "metadata": {"aula": "2 - Metodo", "modulo": "1 - FLG"},
            }
        )
    for i, aula in enumerate(["3 - Marca", "4 - CX", "5 - IA", "6 - Growth"]):
        docs.append(
            {
                "id": f"outro:{i}",
                "text": f"e igual receita de bolo, mistura tudo {i}",
                "metadata": {"aula": aula, "modulo": "9 - Varios"},
            }
        )
    return docs


def _sem_gate_de_raridade(monkeypatch):
    """Neutraliza o criterio de IDF para isolar o de concentracao.

    Num corpus de 9 docs a IDF de um termo presente em metade deles e 0.0, entao o
    gate de raridade nao e satisfazivel aqui — e nao e ele que esta sob teste.
    """
    monkeypatch.setattr(hybrid.settings, "bm25_rescue_min_idf", 0.0)


def test_termo_ensinado_e_resgatavel_mas_metafora_nao(monkeypatch):
    _sem_gate_de_raridade(monkeypatch)
    """IDF mede raridade, nao dominio: `pulse` e `bolo` sao igualmente raros.

    O que separa e a concentracao — o termo que uma aula ensina fica numa aula so.
    """
    from grifo.retrieval.hybrid import BM25Index

    idx = BM25Index(_corpus_com_termo_ensinado())
    assert "pulse" in idx.termos_resgataveis("o que e o pulse?")
    assert "bolo" not in idx.termos_resgataveis("qual a receita do bolo de cenoura?")


def test_termo_de_aparicao_unica_nao_e_resgatavel(monkeypatch):
    _sem_gate_de_raridade(monkeypatch)
    """Aparicao unica e incidental, nao conceito: fica abaixo do piso de chunks."""
    from grifo.retrieval.hybrid import BM25Index

    docs = _corpus_com_termo_ensinado()
    docs.append(
        {
            "id": "solo:0",
            "text": "escrevi um poema qualquer aqui",
            "metadata": {"aula": "7 - Outra", "modulo": "9 - Varios"},
        }
    )
    idx = BM25Index(docs)
    assert "poema" not in idx.termos_resgataveis("escreve um poema sobre o mar")


def test_contem_algum_localiza_o_chunk_do_termo():
    from grifo.retrieval.hybrid import BM25Index

    idx = BM25Index(_corpus_com_termo_ensinado())
    assert idx.contem_algum("a2:c0", {"pulse"}) is True
    assert idx.contem_algum("outro:0", {"pulse"}) is False


def test_ensure_collection_recusa_dimensao_divergente(monkeypatch):
    """Trocar de modelo de embedding sem reindexar tem de falhar cedo e claro.

    Sem esta checagem o erro so aparece no /ask, como um 400 cru do Qdrant
    ("expected dim: 256, got 384") longe da causa real.
    """
    import pytest

    from grifo.retrieval import vector_store

    cfg = SimpleNamespace(
        config=SimpleNamespace(params=SimpleNamespace(vectors=SimpleNamespace(size=256)))
    )
    monkeypatch.setattr(
        vector_store,
        "_client",
        lambda: SimpleNamespace(collection_exists=lambda n: True, get_collection=lambda n: cfg),
    )
    with pytest.raises(ValueError, match="256"):
        vector_store.ensure_collection("grifo", 384)


def test_ensure_collection_aceita_dimensao_igual(monkeypatch):
    from grifo.retrieval import vector_store

    cfg = SimpleNamespace(
        config=SimpleNamespace(params=SimpleNamespace(vectors=SimpleNamespace(size=384)))
    )
    monkeypatch.setattr(
        vector_store,
        "_client",
        lambda: SimpleNamespace(collection_exists=lambda n: True, get_collection=lambda n: cfg),
    )
    vector_store.ensure_collection("grifo", 384)  # nao levanta


def test_point_id_nao_depende_do_nome_da_colecao():
    """Regressao: o id do ponto amarrado a colecao quebra alias e rename.

    Quando o nome entrava no id, criar um alias mudava o id calculado, `score_by_ids`
    nao achava mais o ponto, e o resgate lexico do BM25 parava EM SILENCIO -- a busca
    seguia respondendo, so que sem os chunks resgatados.
    """
    from grifo.retrieval.vector_store import _point_id

    cid = "aula-02-metodo:chunk79"
    assert _point_id(cid, "colecao_antiga") == _point_id(cid, "colecao_nova")
    assert _point_id(cid) == _point_id(cid, "qualquer")
    assert _point_id("outro:chunk1") != _point_id(cid)


def _corpus_fake(monkeypatch, docs):
    """Substitui o scroll do Qdrant e devolve o contador de chamadas."""
    chamadas: list[dict | None] = []
    monkeypatch.setattr(
        hybrid.vector_store,
        "fetch_all",
        lambda filters=None: (chamadas.append(filters), docs)[1],
    )
    return chamadas


def test_warmup_constroi_o_indice_e_a_query_seguinte_reusa(monkeypatch):
    """O aquecimento tira o build do caminho da primeira pergunta."""
    hybrid.invalidate_cache()
    docs = [{"id": "a", "text": "conteudo da aula", "metadata": {"aula": "1"}}]
    chamadas = _corpus_fake(monkeypatch, docs)

    assert hybrid.warmup(filters={"curso": "C"}) == 1
    hybrid._get_bm25({"curso": "C"})  # a query do aluno, logo depois

    assert chamadas == [{"curso": "C"}], "o indice foi reconstruido em vez de reusado"


def test_warmup_com_filtro_errado_nao_aquece_a_query_real(monkeypatch):
    """Regressao: o cache e chaveado por filtro, e a chain sempre passa `curso`.

    Aquecer com `None` constroi um indice que nenhuma pergunta consulta -- o custo de
    build acaba pago duas vezes, e a segunda no meio do /ask.
    """
    hybrid.invalidate_cache()
    docs = [{"id": "a", "text": "conteudo da aula", "metadata": {"aula": "1"}}]
    chamadas = _corpus_fake(monkeypatch, docs)

    hybrid.warmup()  # sem filtro
    hybrid._get_bm25({"curso": "C"})

    assert chamadas == [None, {"curso": "C"}]


def test_invalidate_cache_forca_releitura_do_corpus(monkeypatch):
    """O bug que isso corrige: apos /ingest o BM25 seguia servindo o corpus velho.

    A busca vetorial enxergava o material recem-indexado e o lexico nao, entao o resgate
    do ADR 001 ficava cego justamente para o conteudo mais novo -- sem erro nenhum.
    """
    hybrid.invalidate_cache()
    corpus = [{"id": "a", "text": "aula sobre precificacao", "metadata": {"aula": "1"}}]
    chamadas: list[dict | None] = []
    monkeypatch.setattr(
        hybrid.vector_store,
        "fetch_all",
        lambda filters=None: (chamadas.append(filters), list(corpus))[1],
    )
    assert hybrid.warmup(filters={"curso": "C"}) == 1

    corpus.append({"id": "b", "text": "aula nova sobre o pulse", "metadata": {"aula": "2"}})
    assert len(hybrid._get_bm25({"curso": "C"}).ids) == 1, "cache quente ve o corpus velho"

    hybrid.invalidate_cache()
    assert len(hybrid._get_bm25({"curso": "C"}).ids) == 2
    assert len(chamadas) == 2
