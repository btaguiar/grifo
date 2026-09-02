# SPEC — Grifo v1

**Chatbot RAG educacional com citação obrigatória**
Versão 1.0 · 2026-08-23 · Autor: Bruno
Arquitetura e ADRs: [ARCHITECTURE.md](ARCHITECTURE.md) · Métricas: [EVALUATION.md](EVALUATION.md)

Este documento é o contrato de implementação. O documento de planejamento original explica *por que*; este spec define *o que* e *como se verifica*. Todo requisito tem ID, prioridade e critério de aceite testável. Se algo não está aqui, não está na v1.

---

## 1. Objetivo

Responder dúvidas de alunos de curso online usando exclusivamente o conteúdo oficial do curso, sempre citando módulo/aula da fonte, e recusando explicitamente quando a resposta não existe no material.

**Métrica de sucesso do produto:** um aluno pergunta em linguagem natural e recebe, em menos de 3s, uma resposta correta com link para o ponto exato do material — ou uma recusa honesta.

**Métrica de sucesso do portfolio:** um estranho clona o repo, roda `docker compose up`, pergunta ao corpus de exemplo e recebe resposta com fonte, sem ajuda.

---

## 2. Escopo

### 2.1 Dentro da v1

Ingestão multi-formato · metadados ricos de citação · busca híbrida com reranking · geração com citação obrigatória · recusa por threshold · API FastAPI · UI Streamlit · suite de avaliação com golden set · log de perguntas e relatório de dúvidas frequentes.

### 2.2 Fora da v1 (não negociável)

| Fora | Por quê |
|---|---|
| Multi-tenant / isolamento por permissão | v1 serve um curso por índice |
| Autenticação de aluno / integração com a plataforma do curso | Projeto de portfolio, não produto interno |
| Memória de conversa longa | Contexto de sessão curto basta para Q&A pontual |
| Fine-tuning | RAG resolve; fine-tuning é custo sem ganho aqui |
| Geração de conteúdo novo | O bot responde do material, não inventa aula |
| Streaming de resposta token a token | Nice-to-have; entra na v1.1 se sobrar tempo |

Reler esta tabela toda semana. É a defesa contra o risco "escopo cresce".

---

## 3. Personas e casos de uso

| ID | Persona | Caso de uso | Requisitos |
|---|---|---|---|
| UC-1 | Aluno | Pergunta algo coberto pelo material e recebe resposta com citação clicável | FR-30, FR-31, FR-33 |
| UC-2 | Aluno | Pergunta algo fora do material e recebe recusa explícita | FR-32 |
| UC-3 | Aluno | Pergunta mal formulada / ambígua e recebe o caso mais provável + desdobramento | FR-34 |
| UC-4 | Suporte/CS | Consulta as dúvidas mais frequentes dos últimos N dias | FR-50, FR-51 |
| UC-5 | Operador | Indexa um diretório novo de material via CLI | FR-14 |

---

## 4. Requisitos funcionais

Prioridade: **P0** = bloqueia a v1 · **P1** = importante, cortável sob pressão · **P2** = se sobrar tempo.
Ordem de corte sob pressão (SPEC seção 11): corte reranking e BM25 **antes** de cortar avaliação.

### 4.1 Ingestão

| ID | Req | Pri | Aceite |
|---|---|---|---|
| FR-10 | `DocumentLoader` recebe um **path de diretório** e não sabe se o corpus é real ou sanitizado | P0 | O mesmo comando indexa `data/raw/` e `samples/` sem alteração de código |
| FR-11 | Loaders para PDF, VTT, SRT e Markdown | P0 | Teste por formato: arquivo fixture → lista de `Document` com texto não vazio |
| FR-12 | Anonimização de PII antes da indexação: e-mail, telefone, CPF no mínimo | P0 | Teste com texto contendo os 3 tipos → nenhum resiste ao passo; substituição por placeholder tipado (`[EMAIL]`, `[TELEFONE]`, `[CPF]`) |
| FR-13 | Chunking estrutural: divide por seção/aula primeiro, por tamanho depois | P0 | Nenhum chunk cruza fronteira de aula; todo chunk carrega o schema completo de DC-1 |
| FR-14 | CLI `python -m grifo.ingest <dir>` executa o pipeline fim a fim | P0 | Comando indexa e imprime contagem de documentos, chunks e tokens |
| FR-15 | Ingestão é idempotente: reindexar o mesmo diretório não duplica chunks | P1 | Rodar 2x → mesma contagem na coleção |
| FR-16 | Limpeza de ruído de transcrição (marcas de tempo soltas, repetições, hesitações) | P1 | Fixture de VTT ruidoso → texto legível |

### 4.2 Retrieval

| ID | Req | Pri | Aceite |
|---|---|---|---|
| FR-20 | Busca vetorial no Qdrant com filtro por metadado (`curso`, `modulo`) | P0 | Query filtrada por módulo só devolve chunks daquele módulo |
| FR-21 | Busca BM25 sobre o mesmo corpus | P1 | Query com sigla exata citada 1x no material recupera o chunk |
| FR-22 | Fusão RRF dos dois rankings, pesos configuráveis | P1 | `HYBRID_WEIGHTS` altera a ordem final de forma observável |
| FR-23 | Reranking cross-encoder de `RETRIEVE_K` → `FINAL_K` | P1 | Context precision melhora vs. baseline sem reranker, medido no golden set |
| FR-24 | Threshold de score: abaixo de `SCORE_THRESHOLD`, retorna vazio | P0 | Query fora do domínio → 0 chunks acima do threshold |

### 4.3 Geração

| ID | Req | Pri | Aceite |
|---|---|---|---|
| FR-30 | Chain LCEL: pergunta → retrieval → prompt → LLM → resposta + fontes | P0 | `/ask` responde fim a fim |
| FR-31 | **Toda** afirmação cita a fonte no formato `[Módulo X, Aula Y]` | P0 | Teste automatizado: resposta com `found: true` contém ao menos uma citação bem formada |
| FR-32 | Recusa exata `"Não encontrei isso no material do curso."` quando não há contexto suficiente | P0 | Teste automatizado com pergunta fora do escopo → string exata + `found: false` |
| FR-33 | Quando o chunk tem `timestamp_inicio`, a fonte expõe o timestamp para virar link | P0 | Resposta sobre transcrição traz `timestamp` não nulo |
| FR-34 | Pergunta ambígua: responde o caso mais provável e oferece desdobramento | P2 | Avaliação qualitativa no golden set |
| FR-35 | Resposta em PT-BR, no máximo 200 palavras | P0 | Teste de contagem de palavras sobre amostra do golden set |
| FR-36 | Contagem de tokens de entrada e saída registrada em toda chamada | P0 | Campo `tokens` presente e não nulo em 100% das respostas |

### 4.4 API

| ID | Req | Pri | Aceite |
|---|---|---|---|
| FR-40 | `POST /ask` conforme contrato DC-2 | P0 | Teste de contrato contra o schema Pydantic |
| FR-41 | `GET /health` retorna status do serviço e conectividade com o Qdrant | P0 | Qdrant fora do ar → 503 |
| FR-42 | `POST /ingest` protegido por token, dispara a ingestão | P1 | Sem token → 401 |
| FR-43 | `GET /analytics/top-questions?days=7` | P1 | Retorna lista ordenada por frequência |
| FR-44 | Swagger automático em `/docs` | P0 | Página abre com os 4 endpoints documentados |

### 4.5 Analytics

| ID | Req | Pri | Aceite |
|---|---|---|---|
| FR-50 | Toda pergunta é logada: texto, timestamp, `found`, latência, tokens, fontes | P0 | Uma linha por pergunta no store de log |
| FR-51 | Agrupamento de perguntas semanticamente próximas para o relatório | P1 | Duas formulações da mesma dúvida caem no mesmo grupo |
| FR-52 | Log não persiste PII do aluno | P0 | Anonimização aplicada também à pergunta antes de gravar |

### 4.6 UI

| ID | Req | Pri | Aceite |
|---|---|---|---|
| FR-60 | Chat Streamlit com histórico de sessão | P0 | Conversa de 5 turnos mantém histórico na tela |
| FR-61 | Fontes exibidas abaixo da resposta, com módulo, aula e score | P0 | Visível na demo |
| FR-62 | Timestamp vira link clicável para o minuto do vídeo | P1 | Link abre no ponto certo (ou copia a referência quando não há URL) |
| FR-63 | Estado de recusa visualmente distinto da resposta normal | P1 | Momento mais forte do vídeo de 2 min |

---

## 5. Requisitos não funcionais

| ID | Req | Alvo | Verificação |
|---|---|---|---|
| NFR-1 | Latência p95 de `/ask` | < 3s | Medida sobre o golden set, registrada em EVALUATION.md |
| NFR-2 | Custo de API rastreável | Contador de tokens desde o dia 1 | Campo `tokens` no log + limite de gasto na conta OpenAI |
| NFR-3 | Subida completa em um comando | `docker compose up` | Qdrant + API + UI no ar |
| NFR-4 | Nenhum arquivo de material no histórico do git | Zero | `.gitignore` no primeiro commit; auditoria antes de publicar o repo |
| NFR-5 | CI verde: lint + testes + eval | Badge no README | GitHub Actions em todo push |
| NFR-6 | Cobertura de testes em ingestão e geração | > 70% | Relatório no CI |
| NFR-7 | Config por variável de ambiente, sem segredo em código | 100% | `.env.example` completo; nenhum literal de chave no repo |
| NFR-8 | Reprodutibilidade da avaliação | Determinística onde possível | `temperature=0`, seed fixa, resultados versionados |

---

## 6. Contratos de dados

### DC-1 — Chunk indexado

```python
{
    "id": "modulo3_aula7:chunk12",
    "text": "...",
    "metadata": {
        "curso": "Gestão 4.0",
        "modulo": "3 - Estratégia",
        "aula": "7 - Precificação",
        "fonte_tipo": "transcricao",    # transcricao | pdf | slide | markdown
        "arquivo": "m3_a7.vtt",
        "timestamp_inicio": "00:22:14", # null quando não for vídeo
        "pagina": None,                 # preenchido para pdf/slide
        "chunk_index": 12,
        "ingested_at": "2026-08-25T10:00:00Z",
    }
}
```

**Invariantes:** `curso`, `modulo`, `aula`, `fonte_tipo`, `arquivo`, `chunk_index` e `ingested_at` são obrigatórios. Ao menos um entre `timestamp_inicio` e `pagina` deve estar preenchido — sem isso a citação não é acionável. A validação de schema roda na ingestão e falha alto.

### DC-2 — API `POST /ask`

```jsonc
// request
{"question": "string", "session_id": "string | null", "curso": "string"}

// 200
{
  "answer": "string",
  "sources": [
    {"modulo": "string", "aula": "string", "timestamp": "string | null", "score": 0.0}
  ],
  "found": true,
  "latency_ms": 0,
  "tokens": {"input": 0, "output": 0}
}
```

`found: false` implica `answer` exatamente igual à string de recusa e `sources` vazio.

Erros: `400` payload inválido · `401` `/ingest` sem token · `503` Qdrant indisponível · `500` falha do provedor LLM (com `request_id` no corpo).

### DC-3 — Golden set (`eval/golden_set.jsonl`)

```jsonc
{"id": "gs-001", "question": "...", "expected_source": {"modulo": "2", "aula": "4"}, "expected_answer_contains": ["...", "..."], "should_answer": true, "categoria": "conceitual"}
{"id": "gs-042", "question": "...", "expected_source": null, "should_answer": false, "categoria": "fora-de-escopo"}
```

Mínimo 50 itens. Composição alvo: 60% conceituais dentro do escopo, 20% factuais/específicas (siglas, nomes de ferramentas — testam o BM25), 20% fora do escopo (`should_answer: false`).

---

## 7. Parâmetros de configuração

Valores de **partida**, não finais. Calibrar contra o golden set e documentar a calibração em EVALUATION.md com gráfico de precisão vs. threshold.

```python
CHUNK_SIZE        = 900          # chars
CHUNK_OVERLAP     = 150
RETRIEVE_K        = 20           # candidatos antes do rerank
FINAL_K           = 5            # chunks no prompt
SCORE_THRESHOLD   = 0.35         # abaixo disso, "não encontrado"
HYBRID_WEIGHTS    = (0.6, 0.4)   # (vetorial, BM25)
LLM_TEMPERATURE   = 0.0
MAX_ANSWER_WORDS  = 200
```

Todos sobrescrevíveis por variável de ambiente — ver [.env.example](.env.example) e [src/grifo/config.py](src/grifo/config.py).

---

## 8. Metas de avaliação

| Métrica | Meta v1 | Origem |
|---|---|---|
| Context Precision | > 0.75 | RAGAS |
| Context Recall | > 0.70 | RAGAS |
| Faithfulness | > 0.90 | RAGAS |
| Answer Relevance | > 0.80 | RAGAS |
| **Taxa de recusa correta** | > 0.95 | métrica própria |
| **Taxa de alucinação** | < 2% | métrica própria |
| Latência p95 | < 3s | instrumentação |

As duas em negrito são o diferencial do projeto. `python eval/run_eval.py` roda no CI, resultados versionados em `eval/results/`.

---

## 9. Governança de dados (gate de bloqueio)

| ID | Requisito | Status |
|---|---|---|
| GOV-1 | Autorização por escrito da escola para (a) processar material em projeto pessoal, (b) enviar trechos para a API da OpenAI — serviço externo, o conteúdo sai da infra da empresa, (c) publicar o código e falar publicamente | pendente |
| GOV-2 | `.gitignore` commitado antes de qualquer arquivo em `data/` | feito |
| GOV-3 | Corpus real apenas em `data/raw/`, local; corpus aberto em `samples/`, commitado | feito |
| GOV-4 | Anonimização de PII na ingestão, documentada no README | feito |
| GOV-5 | Auditoria do histórico git antes de tornar o repo público | feito (2026-09-02) — ver abaixo |

**GOV-1 bloqueia o uso do corpus real, não o código.** Decidir na semana 1. Se a autorização não vier: trocar o corpus por material aberto (MIT OpenCourseWare, documentação técnica, curso fictício) e manter a narrativa em "o problema que eu via operando cursos online".

**Resultado da auditoria GOV-5 (2026-09-02).** Nenhum segredo em nenhum commit, e o
material do curso nunca entrou no índice — GOV-2 se sustenta. Foram encontrados e
corrigidos três vazamentos da *origem* do material, que é coisa diferente do material:

1. O documento de planejamento original, que nomeia a empresa, tinha sido removido da
   árvore mas continuava recuperável em todo commit anterior. Removido do histórico.
2. O rascunho do pedido de autorização nomeava a empresa no próprio nome do arquivo.
   Removido do histórico; a versão atual é `docs/autorizacao-material.md`.
3. Arquivos versionados citavam mentores reais dentro de `chunk_id`s do corpus, e o
   `.gitignore` nomeava a empresa no padrão da pasta de staging. As aulas passaram à
   notação `M<módulo>/A<aula>` e o padrão local mudou-se para `.git/info/exclude`.

O jargão técnico do corpus (`pulse`, `apqc`) fica: é o que sustenta o ADR 001 e a seção
4.4 do EVALUATION, e termo de domínio não é conteúdo do curso.

---

## 10. Marcos e Definition of Done

| Semana | Meta | DoD |
|---|---|---|
| 1 — Fundação e ingestão | Material entra, vira vetor, é buscável | `python -m grifo.ingest data/raw/` indexa o curso e uma busca por termo devolve chunks com módulo/aula corretos |
| 2 — Retrieval e geração | Perguntar e receber resposta com fonte | CLI responde 10 perguntas reais com fonte correta e recusa as 3 fora do escopo |
| 3 — Produto e avaliação | Vira software, não script | `docker compose up` sobe tudo; CI verde; EVALUATION.md com a tabela de métricas preenchida |
| 4 — Polimento e publicação | O portfolio existe fora da sua máquina | Um estranho clona, roda, pergunta ao corpus de exemplo e recebe resposta com fonte, sem você por perto |



---

## 11. Riscos e gatilhos de decisão

| Risco | Prob. | Mitigação | Gatilho |
|---|---|---|---|
| Autorização da escola não sai | Média | Corpus aberto no lugar, narrativa preservada | Decidir até o fim da semana 1 |
| Transcrições de baixa qualidade | Alta | Passo de limpeza na ingestão; se muito ruim, priorizar PDFs e slides | Avaliar após FR-16 |
| Chunking quebra o contexto | Alta | Investir tempo na semana 1; testar perguntas cuja resposta cruza dois chunks | Context recall < 0.70 |
| Escopo cresce | Alta | Tabela 2.2 relida toda semana | Qualquer item novo pedindo entrada |
| 4 semanas viram 10 | Alta | Cortar reranking (FR-23) e BM25 (FR-21/22) **antes** da avaliação | Fim da semana 2 sem o DoD |
| Custo de API surpreende | Baixa | Contador de tokens desde o dia 1, limite de gasto na conta OpenAI | Gasto acumulado acima do orçado |

---

## 12. Fora do código: entregáveis de portfolio

| Peça | Critério de pronto |
|---|---|
| README | Ordem: problema em 3 linhas → GIF da demo → **métricas** → arquitetura → como rodar → limitações. Métricas antes da arquitetura. |
| ARCHITECTURE.md | Diagrama + os 3 ADRs |
| EVALUATION.md | Metodologia, tabela de métricas, gráfico de calibração do threshold |
| Demo pública | Streamlit Cloud apontando para o corpus de `samples/` |
| Vídeo 2 min | 0:00 problema · 0:20 demo com citação clicável · 1:10 **a recusa** · 1:35 métricas e próximos passos |
| Post LinkedIn | Caso técnico: problema, decisão de arquitetura, número medido, o que deu errado. Sem travessão. |
