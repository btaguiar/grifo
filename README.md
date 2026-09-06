# Grifo

**Assistente de dÃºvidas para cursos online. Responde sÃ³ com o material oficial, cita mÃ³dulo, aula e o minuto do vÃ­deo â€” e recusa quando a resposta nÃ£o estÃ¡ lÃ¡.**

[![CI](https://github.com/btaguiar/grifo/actions/workflows/ci.yml/badge.svg)](https://github.com/btaguiar/grifo/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11-blue)
![Testes](https://img.shields.io/badge/testes-159-green)

> **Status:** pipeline completo com avaliaÃ§Ã£o de ponta a ponta, contrato de saÃ­da
> validado por Pydantic e sÃ©rie temporal de mÃ©tricas. Aberto e datado: latÃªncia acima
> da meta com o contrato (3,5s vs 3s) e juiz com calibraÃ§Ã£o ampliada pendente de
> revisÃ£o humana. Nenhum nÃºmero aqui Ã© estimativa: ou foi medido, ou estÃ¡ vazio.

---

## 1. O problema

Aluno de curso online trava Ã s 23h. A resposta existe â€” estÃ¡ num vÃ­deo de 40 minutos,
mÃ³dulo 3, aula 7, minuto 22 â€” e o suporte responde as mesmas 20 perguntas toda semana.
O problema nÃ£o Ã© falta de conteÃºdo, Ã© **recuperaÃ§Ã£o** de conteÃºdo â€” e a resposta
errada dada com confianÃ§a Ã© pior que nenhuma resposta.

Grifar Ã© marcar o trecho certo no material. Ã‰ o que o projeto faz: responde **sÃ³** com
o material oficial, cita onde estÃ¡, e recusa quando nÃ£o estÃ¡.

## 2. MÃ©tricas

Dois corpora, dois setups, denominadores explÃ­citos e o comando que gera cada nÃºmero
ao lado. Metodologia, calibraÃ§Ã£o e anÃ¡lise de erro em [EVALUATION.md](EVALUATION.md).

| MÃ©trica | Denominador | Meta | Corpus real, LLM local | Corpus de exemplo, LLM remoto | Reproduzir |
|---|---|---|---|---|---|
| **Taxa de recusa correta** | 11 fora do escopo | > 0.95 | **1.00** (11/11) | **1.00** (11/11) | `python eval/run_eval.py` |
| **Taxa de alucinaÃ§Ã£o** | respondidas | < 2% | **0.00** (0/44)Â¹ | **0.00** (0/33)Â¹ | `python eval/run_eval.py` |
| **fonte@5** â€” retrieval puro | 53 em escopo | â€” | **0.79** | â€” | `python eval/calibrar_retrieval.py --ablacao` |
| **Fonte correta nas respondidas** | respondidas | â€” | **0.82** (36/44) | **0.97** (32/33) | `python eval/run_eval.py` |
| **CitaÃ§Ã£o espontÃ¢nea** | respondidas | â€” | **0.80** (35/44)Â² | **1.00** (33/33, contrato)Â³ | `python eval/run_eval.py` |
| **Cobertura de conteÃºdo** | respondidas com gabarito | â‰¥ 0.90 | â€” | **0.95** / 0.94 (n=33) | `python eval/run_eval.py` |
| Faithfulness (RAGAS) | respondidas | > 0.90 | â€” | 0.87 â€” **nÃ£o atinge** | `python eval/run_eval.py` |
| Context Precision (RAGAS) | respondidas | > 0.75 | â€” | **0.96** | `python eval/run_eval.py` |
| Answer Relevance (RAGAS) | respondidas | > 0.80 | â€” | **0.84** | `python eval/run_eval.py` |
| Retry de validaÃ§Ã£o do contrato | todas as perguntas | â€” | â€” | **0.000** (55/55 de primeira) | `python eval/run_eval.py` |
| **LatÃªncia p95** | todas as perguntas | < 3s | 19,9s â€” nÃ£o atinge | 3,53s â€” nÃ£o atingeÂ³ | `python eval/run_eval.py` |
| **Custo por query** | 55 perguntas | â€” | US$ 0 (local) | **~US$ 0.0001** | `python eval/run_eval.py` â†’ `custo_usd` |

As colunas **nÃ£o sÃ£o comparÃ¡veis entre si**: corpora de tamanhos muito diferentes.
A sÃ©rie temporal (3 rodadas na configuraÃ§Ã£o canÃ´nica congelada) estÃ¡ no
[EVALUATION.md Â§3.5](EVALUATION.md), com grÃ¡fico derivado dos `metricas_*.json`.

Â¹ Verificada Ã  mÃ£o: o juiz sinalizou 2 casos, ambos falso positivo (EVALUATION.md 5.4).
Regra de publicaÃ§Ã£o: a taxa de alucinaÃ§Ã£o sÃ³ aparece ao lado do **Kappa de Cohen** do
juiz â€” `python eval/calibrar_juiz.py` gera matriz de confusÃ£o, precisÃ£o, recall e
kappa. Kappa < 0.70 = taxa nÃ£o liberada para produÃ§Ã£o sem revisÃ£o manual. O conjunto
de calibraÃ§Ã£o tem 99 casos (33 positivos); a revisÃ£o humana dos rascunhos estÃ¡ pendente.
Â² MediÃ§Ã£o da rodada de 2026-08-24, antes do `_ensure_citation` (EVALUATION.md 5.5) â€”
prompt antigo, `qwen2.5-7b` local. A citaÃ§Ã£o **final** daquela rodada foi 1.00
(44/44) **pÃ³s-processada**: 9 respostas (20%) foram consertadas Ã  forÃ§a pela chain.
Â³ Rodada do contrato de saÃ­da Pydantic (2026-09-06, EVALUATION.md 3.4): citaÃ§Ã£o validada
por Pydantic/instructor com retry instruÃ­do â€” 1.00 espontÃ¢nea, zero re-validaÃ§Ãµes. O
custo do contrato Ã© publicado: p95 2,58s â†’ 3,53s, tokens de entrada 361 â†’ 561 por
pergunta. Custo por query derivado dos tokens medidos Ã— preÃ§o pÃºblico datado em
`config.py` (`custo_usd` no `metricas_*.json`).

**TrÃªs leituras que valem mais que os nÃºmeros** (detalhes no EVALUATION.md):

- 9 perguntas dentro do escopo foram recusadas indevidamente (17% no corpus real) â€” Ã©
  o custo declarado da regra de recusa, invisÃ­vel na taxa de recusa correta.
- As duas mÃ©tricas de fidelidade discordam de forma informativa: o juiz prÃ³prio sÃ³
  acusa fato novo; o faithfulness do RAGAS pega elaboraÃ§Ã£o. 5 itens com faithfulness
  < 0.70 foram aprovados pelo juiz â€” a divergÃªncia item a item estÃ¡ no 5.8.
- A latÃªncia que nÃ£o atinge Ã© do contrato, nÃ£o do retrieval: a busca custa 30ms; o
  tool calling do structured output Ã© o que pesa.

## 3. Arquitetura

```mermaid
flowchart LR
    subgraph offline [IngestÃ£o offline]
        A[Loaders: PDF, VTT/SRT, MD] --> B[AnonimizaÃ§Ã£o de PII]
        B --> C[Chunking estrutural 900/150<br/>fronteira por aula/tÃ³pico]
        C --> D[Embeddings] --> E[(Qdrant)]
        C --> F[(Ãndice BM25)]
    end
    Q[DÃºvida do aluno] --> G[Busca hÃ­brida<br/>vetorial + BM25]
    G --> H[FusÃ£o RRF]
    H --> I[Resgate lÃ©xico<br/>IDF â‰¥ 6, â‰¥ 3 chunks, â‰¥ 70% concentrado]
    I --> J{score â‰¥ 0.45?}
    J -- nÃ£o --> R[Recusa exata<br/>found=false, sem LLM]
    J -- sim --> K[Chain LCEL<br/>prompt versionado .txt]
    K --> L[Contrato Pydantic<br/>GrifoAnswer via instructor<br/>retry instruÃ­do Ã—2]
    L --> M[Envelope HTTP<br/>AskResponse DC-2]
```

Dois gates de recusa em sÃ©rie (ADR 002): o threshold do retrieval (barra o
desalinhado) e o prÃ³prio modelo via contrato (`found=false` com a string exata).
A citaÃ§Ã£o sai do modelo validada â€” o par mÃ³dulo/aula citado precisa existir entre os
trechos recuperados, senÃ£o o contrato reprova e o erro volta ao modelo.

Diagrama completo e os trÃªs ADRs em [ARCHITECTURE.md](ARCHITECTURE.md). Requisitos
com critÃ©rio de aceite em [SPEC.md](SPEC.md).

**Stack:** Python 3.11 Â· LangChain (LCEL) Â· Qdrant Â· FastAPI Â· Pydantic + instructor Â·
Streamlit Â· Docker Compose Â· GitHub Actions. O LLM e os embeddings entram por qualquer
API compatÃ­vel com OpenAI, escolhida sÃ³ por variÃ¡vel de ambiente â€” nenhum cÃ³digo muda
entre elas. TrÃªs setups em [.env.example](.env.example): **OpenRouter** (uma chave
para os dois, Ã© o default), **OpenAI direto**, e **100% local** via LM Studio ou
Ollama.

**Privacidade.** O material do curso nunca entra no repositÃ³rio: o `.gitignore` foi o
primeiro commit e cobre tambÃ©m os resultados brutos da avaliaÃ§Ã£o (carregam o texto dos
trechos). Dois corpora, um cÃ³digo: o real fica local, o sanitizado em `samples/` Ã©
commitado e Ã© o que a demo e o CI usam. A ingestÃ£o anonimiza e-mail, telefone e CPF
antes de indexar. Com o setup local, embeddings **e** LLM rodam na mÃ¡quina â€” nenhum
trecho do material sai dela.

## 4. DecisÃµes medidas

A seÃ§Ã£o que diferencia este repositÃ³rio: cada decisÃ£o de projeto tem o nÃºmero que a
justificou e o link para a mediÃ§Ã£o. Nenhuma veio de opiniÃ£o.

| DecisÃ£o | O que a mediÃ§Ã£o mostrou | Onde |
|---|---|---|
| **Reranker desligado** | cross-encoder `ms-marco-MiniLM` (inglÃªs) reordenando portuguÃªs: fonte 77% â†’ 74% **e** +613ms por pergunta | [4.4](EVALUATION.md) |
| **Resgate lÃ©xico com os 3 critÃ©rios** (IDF â‰¥ 6 + â‰¥ 3 chunks + 70% concentraÃ§Ã£o) | sÃ³-IDF comprava 7pp de recall e **destruÃ­a a recusa** (82% â†’ 27%); com os trÃªs, +6pp de recall sem custo nenhum | [4.4](EVALUATION.md) |
| **Threshold em 0.45** (partida 0.35) | recusa do gate 9% â†’ 55% com a mesma cobertura e o mesmo acerto de fonte â€” ganho nos dois eixos, nÃ£o trade-off | [4.1](EVALUATION.md) |
| **Juiz binÃ¡rio** (SIM/NÃƒO, nÃ£o Likert) | a versÃ£o "contÃ©m ALGUMA afirmaÃ§Ã£o nÃ£o sustentada?" reprovava parÃ¡frase fiel e inflava a alucinaÃ§Ã£o para 79,5% â€” quase todo falso positivo | [3.2](EVALUATION.md) |
| **BM25 mantido** (o plano de partida mandava cortÃ¡-lo) | sozinho vale +9pp de acerto de fonte; com o resgate, cobertura 100% | [4.4](EVALUATION.md) |
| **Contrato Pydantic em vez de regex** sobre a saÃ­da | citaÃ§Ã£o 1.00 espontÃ¢nea com 0 re-validaÃ§Ãµes; custo publicado: p95 2,58s â†’ 3,53s, +55% tokens de entrada | [3.4](EVALUATION.md) |
| **PÃ³s-processamento de citaÃ§Ã£o desligado** | o `_ensure_citation` anexava 20% das citaÃ§Ãµes Ã  forÃ§a â€” atribuir fonte a afirmaÃ§Ã£o nÃ£o fundamentada; ficou como flag `FORCE_CITATION=false` | [5.5](EVALUATION.md) |

![CalibraÃ§Ã£o do threshold: cobertura e acerto de fonte estÃ¡veis atÃ© 0.45, enquanto a recusa correta salta de 9% para 55%](docs/calibracao-threshold.png)

**O que eu faria diferente.** Mediria antes de decidir, e mais cedo: os trÃªs
parÃ¢metros de partida do planejamento (threshold, reranker, BM25) estavam errados, e
nenhuma das descobertas exigia cÃ³digo novo â€” sÃ³ a mediÃ§Ã£o que eu podia ter feito na
primeira semana. E desconfiaria de componente que "funciona": os dois piores bugs
foram silenciosos (BM25 que reordenava sem resgatar; cache lÃ©xico servindo corpus
congelado pÃ³s-ingestÃ£o). Num RAG a falha silenciosa Ã© o modo de falha padrÃ£o â€” o teste
que a pega tem de afirmar o que o componente *recupera*, nÃ£o que ele rodou.

## 5. LimitaÃ§Ãµes conhecidas

Declaradas para nÃ£o serem lidas como promessas; detalhes no [EVALUATION.md Â§7](EVALUATION.md).

- **Sem tracing nem observabilidade de produÃ§Ã£o.** As mediÃ§Ãµes sÃ£o de avaliaÃ§Ã£o
  offline; nÃ£o existe traÃ§ado de requisiÃ§Ã£o real (depende de trÃ¡fego que nÃ£o hÃ¡).
- **O `question_log` nÃ£o tem trÃ¡fego real.** 7 linhas de smoke test, sem resposta nem
  chunks gravados â€” nÃ£o Ã© base para golden set.
- **Gabarito parcial.** `expected_answer_contains` Ã© consumido (cobertura de
  conteÃºdo); um campo `reference` que destravaria o context recall do RAGAS foi
  decidido **nÃ£o** fazer â€” razÃµes documentadas.
- **O juiz precisa de kappa.** 99 casos de calibraÃ§Ã£o (33 positivos) aguardam revisÃ£o
  humana; atÃ© o kappa sair â‰¥ 0.70, a taxa de alucinaÃ§Ã£o nÃ£o estÃ¡ liberada para
  produÃ§Ã£o sem revisÃ£o manual.
- **p95 acima da meta com o contrato** (3,5s vs 3s) â€” custo do structured output,
  publicado. O job de eval no CI estÃ¡ pronto atrÃ¡s de `ENABLE_EVAL` e ligÃ¡-lo hoje
  reprova no p95: estado registrado, nÃ£o silenciado.
- **Escopo v1:** um curso por Ã­ndice (sem multi-tenant), sem autenticaÃ§Ã£o de aluno,
  sem memÃ³ria de conversa longa, sem streaming.
- As duas rodadas antigas (corpus real com 7B local; corpus pÃºblico prÃ©-contrato) nÃ£o
  formam sÃ©rie entre si â€” a sÃ©rie canÃ´nica comeÃ§ou em 2026-09-06.

**PrÃ³ximos passos, em ordem de impacto:** revisar os 99 rascunhos da calibraÃ§Ã£o e
publicar o kappa do juiz; resolver a latÃªncia do contrato (streaming ou prompt mais
magro) e ligar o eval no CI; re-medir o corpus real com o contrato; um reranker
multilÃ­ngue se o reranking voltar Ã  pauta.

## 6. Rodar

```bash
cp .env.example .env               # preencha sÃ³ OPENAI_API_KEY
docker compose up -d               # sobe Qdrant + API + UI
docker compose run --rm ingest     # indexa o corpus de exemplo
```

- API e Swagger: http://127.0.0.1:8000/docs
- UI de chat: http://127.0.0.1:8501

Pergunte *"Como calcular o CAC?"* e vocÃª recebe a resposta com a aula citada. Pergunte
*"Qual a receita do bolo de cenoura?"* e recebe a recusa â€” que Ã© o comportamento
correto. As duas respostas estÃ£o certas, e Ã© a segunda que quase ninguÃ©m mede.

A primeira build baixa PyTorch e leva alguns minutos. A ingestÃ£o roda dentro do
container: vocÃª nÃ£o precisa de Python na mÃ¡quina. Custo de rodar a avaliaÃ§Ã£o sobre o
corpus de exemplo: **US$ 0,007 por rodada** (tokens medidos Ã— preÃ§o pÃºblico â€” ver
`custo_usd` no resultado). Para custo zero e nada saindo da mÃ¡quina, use o setup
local do `.env.example`.

Desenvolvimento:

```bash
python -m venv .venv && .venv\Scripts\activate
pip install -e ".[dev]"
pytest                                # 159 testes, sem serviÃ§os externos
pytest -m integration                 # 4 testes, exigem Qdrant no ar
python eval/calibrar_retrieval.py     # varreduras de calibraÃ§Ã£o (sem LLM)
python eval/run_eval.py               # suite completa de avaliaÃ§Ã£o
python eval/calibrar_juiz.py          # kappa + matriz de confusÃ£o do juiz
python eval/gate_regressao.py         # gate contra a Ãºltima rodada da sÃ©rie
python eval/serie_temporal.py         # grÃ¡fico da sÃ©rie (docs/serie-temporal.png)
pip-audit                             # vulnerabilidades conhecidas nas dependÃªncias
```

---

DocumentaÃ§Ã£o: [SPEC.md](SPEC.md) Â· [ARCHITECTURE.md](ARCHITECTURE.md) Â· [EVALUATION.md](EVALUATION.md) Â· [CHANGELOG.md](CHANGELOG.md) Â· [Plano de execuÃ§Ã£o](docs/plano-execucao.md)
