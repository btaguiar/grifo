"""Configuração central, carregada de variáveis de ambiente (NFR-7).

Os valores default reproduzem os parâmetros de partida da SPEC seção 7. Eles NÃO são
finais: calibre contra o golden set e registre a calibração em EVALUATION.md.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Texto exato da recusa. Contrato do ADR 002 — não altere sem atualizar os testes.
REFUSAL_MESSAGE = "Não encontrei isso no material do curso."


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # OpenAI (ou qualquer API compatível — ex.: GLM da Zhipu — via OPENAI_BASE_URL)
    openai_api_key: str = ""
    openai_base_url: str = ""
    #: openai = API remota | local = sentence-transformers (provedores sem embedding,
    #: como a Z.ai, ou indexação sem custo de API)
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"
    llm_model: str = "gpt-4o-mini"
    #: Modelo do JUIZ da avaliacao (juiz de alucinacao e metricas RAGAS). Vazio = usa
    #: `llm_model`, que era o comportamento anterior -- e nele o mesmo modelo responde e
    #: julga a propria resposta. Aponte para um modelo mais forte antes de publicar
    #: qualquer numero: auto-julgamento infla faithfulness e mascara alucinacao.
    eval_llm_model: str = ""
    llm_temperature: float = 0.0

    # Qdrant
    #: 127.0.0.1, nao `localhost`: no Windows o nome resolve `::1` primeiro e cada
    #: requisicao ao Qdrant paga ~200ms, que o cliente amplifica para ~2s por busca
    #: (EVALUATION.md 4.5 -- 69x na query quente). O .env corrigiu; o default nao tinha.
    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_api_key: str = ""
    qdrant_collection: str = "grifo"
    #: Timeout HTTP do cliente, em segundos. 15 era hardcoded e estourava no upsert em
    #: lote de corpus grande com a maquina sob carga -- e o erro chega como
    #: `ResponseHandlingException: timed out` no meio da ingestao, deixando a colecao
    #: pela metade. Suba se indexar corpus grande.
    qdrant_timeout: int = 60

    # Curso
    curso_nome: str = "Curso Exemplo"
    video_base_url: str = ""

    # Chunking
    chunk_size: int = 900
    chunk_overlap: int = 150

    # Retrieval
    retrieve_k: int = 20
    final_k: int = 5
    #: CALIBRADO contra o golden set do corpus real (EVALUATION.md 4.1). O valor de
    #: partida do dossie era 0.35, que deixava passar 10 de 11 perguntas fora de escopo.
    score_threshold: float = 0.45
    hybrid_weight_vector: float = 0.6
    hybrid_weight_bm25: float = 0.4
    #: Resgate lexico do ADR 001: um chunk que so o BM25 achou entra se casar um termo
    #: da pergunta com IDF >= este valor. Num corpus de ~6.5k chunks, 7.0 ~ menos de 10
    #: chunks contem o termo. Valor alto (ex.: 99) desliga o resgate. CALIBRAR.
    bm25_rescue_min_idf: float = 6.0
    #: ...e que apareca em pelo menos N chunks, concentrados numa aula so. E o que
    #: separa conceito ensinado de metafora: `pulse` 4 chunks/1 aula vs `bolo` 5/4.
    bm25_rescue_min_chunks: int = 3
    bm25_rescue_min_concentracao: float = 0.7
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    #: DESLIGADO por medicao: a ablacao (EVALUATION.md 4.4) mostrou que o cross-encoder
    #: ms-marco (treinado em ingles) PIORA a ordem em portugues -- 77% -> 74% de acerto
    #: de fonte -- alem de custar ~613ms. Reative so com um reranker multilingue.
    rerank_enabled: bool = False

    # Geração
    max_answer_words: int = 200
    #: O `_ensure_citation` (FR-31 original) anexava a citação do top chunk quando o
    #: modelo omitia a própria. Medido na rodada de 2026-08-24 (EVALUATION.md 5.5):
    #: 9 de 44 respostas (20%) foram consertadas assim, e a citação 1.00 publicada
    #: era artificial. Com o contrato Pydantic (Fase 2) o modelo passou a devolver
    #: `citations` validadas; a flag fica DESLIGADA por padrão — ligar é rede de
    #: segurança explícita, nunca o mecanismo principal. Mesmo padrão do reranker.
    force_citation: bool = False

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    ingest_token: str = ""

    # Avaliação
    #: O golden set do corpus público é o default. O do corpus real
    #: (`eval/golden_set.local.jsonl`) é gitignored: codifica módulos e temas internos.
    golden_set: Path = Path("eval/golden_set.jsonl")
    #: false = run_eval calcula as métricas sem reprovar o build abaixo das metas.
    eval_strict: bool = True
    #: Requisições concorrentes do RAGAS ao LLM. O default dele é 16, que derruba um
    #: servidor local servindo um modelo só: medido, até 2 concorrentes já fazem o
    #: `faithfulness` sair como NaN em TODOS os itens (timeout), e o relatório grava a
    #: métrica como se fosse resultado. Com 1, os mesmos itens calculam normalmente.
    #: Suba para provedor remoto, onde a concorrência é o que torna a rodada viável.
    ragas_max_workers: int = 1
    #: Segundos por job do RAGAS. O default dele é 180, apertado para LLM local.
    ragas_timeout: int = 600
    #: false = pula as métricas RAGAS (as próprias continuam). Rodada de comparação
    #: A/B (Fase 2) não precisa pagar RAGAS duas vezes — e RAGAS é o bloco mais
    #: caro e lento da rodada.
    ragas_enabled: bool = True

    # Analytics
    question_log_path: Path = Path("data/processed/question_log.jsonl")

    # Corpus
    corpus_dir: Path = Field(default=Path("samples/"))

    @property
    def hybrid_weights(self) -> tuple[float, float]:
        """(peso vetorial, peso BM25) — ADR 001."""
        return (self.hybrid_weight_vector, self.hybrid_weight_bm25)


settings = Settings()
