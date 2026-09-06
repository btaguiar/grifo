# Avaliação — Grifo

> **Status: primeira linha de base medida em 2026-08-24**, sobre o corpus real (24 sessões, 6.551 chunks), com `qwen2.5-7b-instruct-1m` local via LM Studio e embeddings locais — pipeline 100% offline. Nenhuma linha com valor inventado: vazio é honesto, chutado não é.

Requisitos e metas: [SPEC.md](SPEC.md), seções 8 e 6 (DC-3).

---

## 1. Por que este capítulo existe

A maioria dos projetos RAG de portfolio não tem avaliação — mostram uma demo bonita e nenhum número. É exatamente onde este projeto ganha. Um recruiter técnico procura evidência de rigor, e ela precisa aparecer antes de o scroll morrer: por isso as métricas vêm antes da arquitetura também no README.

---

## 2. Metodologia

**Golden set.** 50+ perguntas em `eval/golden_set.jsonl`, no formato DC-3, montadas a partir das dúvidas que se repetiam de verdade na operação do curso. Composição alvo:

| Categoria | Fatia | O que testa |
|---|---|---|
| Conceitual, dentro do escopo | 60% | Retrieval semântico e fidelidade da resposta |
| Factual / sigla / nome de ferramenta | 20% | O componente BM25 do retriever híbrido |
| Fora do escopo (`should_answer: false`) | 20% | A regra de recusa (ADR 002) |

**Execução.** `python eval/run_eval.py` — roda o pipeline completo sobre o golden set, calcula as métricas RAGAS e as duas métricas próprias, e grava um JSON com timestamp e hash do commit em `eval/results/`.

**Reprodutibilidade.** `temperature=0`, seed fixa, versões pinadas no `pyproject.toml`. Resultados versionados no git para render o gráfico de evolução ao longo dos commits.

**Cadência.** O job está escrito em `.github/workflows/ci.yml`, atrás da variável de repositório `ENABLE_EVAL` — hoje **desligada**, então o eval não roda a cada push e a frase "reprova o build" é o alvo, não o estado atual. Ligar exige uma configuração canônica congelada para que as rodadas formem série (ver seção 7).

---

## 3. Resultados

### 3.1 Linha de base — 2026-08-24, corpus real

64 itens de `eval/golden_set.local.jsonl` (53 dentro do escopo, 11 fora), coleção
`grifo_curso_real`, `SCORE_THRESHOLD=0.35`, `FINAL_K=5`, rerank ligado.
Resultado bruto: `eval/results/eval_20260824T184248Z_bb43a87.json`.

| Métrica | Meta v1 | Baseline | Status |
|---|---|---|---|
| Context Precision | > 0.75 | não medida | RAGAS não instalado |
| Context Recall | > 0.70 | não medida | RAGAS não instalado |
| Faithfulness | > 0.90 | não medida | RAGAS não instalado |
| Answer Relevance | > 0.80 | não medida | RAGAS não instalado |
| **Taxa de recusa correta** | > 0.95 | **1.00** (11/11) | atinge |
| **Taxa de alucinação** | < 2% | **0.00** (0/44) | atinge — ver 5.4 |
| Latência p95 | < 3s | **19,9s** | **falha por 6x** |

Complementares, fora da tabela da SPEC mas necessárias para ler as de cima:

| Métrica | Denominador | Medido | Leitura |
|---|---|---|---|
| Taxa de resposta | 64 itens | 0.69 (44/64) | 20 recusas: 11 corretas + **9 falsas** (ver 5.3) |
| fonte@5 (retrieval) | 53 itens em escopo | **0.79** | só retrieval, sem LLM — ver 4.4, configuração recomendada |
| Fonte correta nas respondidas (end-to-end) | 44 respondidas | **0.82** (36/44) | o `expected_source` apareceu nas fontes da resposta final |
| Citação espontânea | 44 respondidas | **0.80** (35/44) | citação que veio do modelo, medida antes do `_ensure_citation` (ver 5.5) |
| Citação final | 44 respondidas | 1.00 (44/44) | **pós-processada** — `_ensure_citation` anexou as 9 que faltavam |
| Tokens totais | — | 85.500 entrada / 11.429 saída | 1.374 / 220 por resposta |

`fonte@5` e "fonte correta nas respondidas" são métricas **diferentes** com denominadores
diferentes: a primeira é retrieval puro sobre todo o escopo (53), a segunda é end-to-end
só sobre o que o sistema respondeu (44). Publicar as duas no mesmo rótulo — como o README
fazia — infla a leitura: a taxa de resposta de 0.69 faz o denominador end-to-end esconder
justamente as perguntas que o retrieval não alcançou.

**A recusa em 100% é o resultado central, e o mecanismo importa.** Com threshold em
0.35 o gate de retrieval sozinho barra apenas 1 das 11 perguntas fora de escopo
(medido na seção 4.1). Quem recusou as outras 10 foi o **LLM**, pelo caminho em que a
recusa do modelo vira `found: false`. São os dois gates em série do ADR 002 — nenhum
dos dois entrega isso sozinho.

As duas em negrito não vêm do RAGAS. São métricas próprias, definidas abaixo, e são as que importam num contexto educacional.

### 3.2 Definição das métricas próprias

**Taxa de recusa correta** = recusas corretas ÷ total de itens com `should_answer: false`.
Uma recusa é correta quando a resposta é exatamente a string de recusa e `found` é `false`. Recusar uma pergunta que o material respondia conta como falso negativo e entra na análise de erro, não nesta métrica.

**Taxa de alucinação** = respostas com ao menos uma afirmação não sustentada pelos chunks recuperados ÷ total de respostas com `found: true`.
Medida por LLM-as-judge sobre a resposta e os chunks recuperados (o **texto**, não a
etiqueta de citação). O juiz é calibrado contra `eval/judge_calibration.jsonl`, 6 casos
rotulados à mão; rode `python eval/calibrar_juiz.py` para reproduzir. Ver 5.4 — o juiz
ainda produz falso positivo em dado real, então o número exige inspeção manual.

**fonte@5 (retrieval)** = itens em escopo cujo `expected_source` apareceu no top-5 do retrieval ÷ total de itens em escopo.
Sem LLM no caminho — é a métrica que isola o retriever. Reproduzir:
`python eval/calibrar_retrieval.py --ablacao` (linha "+ resgate léxico", com os defaults
atuais thr=0.45 e reranker off).

**Fonte correta nas respondidas (end-to-end)** = respostas cujo `expected_source` apareceu entre as fontes retornadas ÷ itens com `found: true`.
É a métrica da experiência do aluno, mas o denominador exclui as recusas — ler sempre ao
lado da taxa de resposta. Reproduzir: `python eval/run_eval.py`.

---

### 3.3 Corpus público com provedor remoto — 2026-09-03

Primeira rodada em que as métricas RAGAS saíram. 55 itens de `eval/golden_set.jsonl`
sobre o corpus de `samples/` (22 chunks), `gpt-4o-mini` respondendo e **`gpt-4o`
julgando** — modelos diferentes, pelo motivo da 5.7.

| Métrica | Meta v1 | Medido | |
|---|---|---|---|
| Context Precision (sem referência) | > 0.75 | **0.96** | atinge |
| Context Recall | > 0.70 | — | não mensurável, ver 5.7 |
| Faithfulness | > 0.90 | **0.81** | **não atinge** |
| Answer Relevance | > 0.80 | **0.83** | atinge |
| Taxa de recusa correta | > 0.95 | **1.00** | atinge |
| Taxa de alucinação | < 2% | **0.00** | atinge |
| **Latência p95** | < 3s | **2,58s** | **atinge** |

Complementares: taxa de resposta 0.60 (33/55), fonte correta nas respondidas **0.97**
(32/33), citação final 1.00 (pós-`_ensure_citation` — a **espontânea não foi medida**
nesta rodada), 601 tokens de entrada por resposta. As três métricas RAGAS têm
`n=33` — todos os itens respondidos entraram, nenhum job falhou. `fonte@5` de retrieval
não foi medida neste corpus: com 22 chunks, o número diria pouco.

**A latência atinge a meta, e isso reposiciona o NFR-1.** O projeto vinha registrando
"falha por 6x" a partir de 19,9s medidos com um 7B local. Com provedor remoto o p95 cai
para 2,58s: o gargalo nunca foi a arquitetura, era o modelo. O retrieval já custava 30ms
(4.5) e a geração é que consumia o orçamento.

A ressalva que impede declarar o NFR-1 cumprido: este corpus tem 22 chunks contra 6.551
do real, e o prompt correspondente é 601 tokens contra 1.374. A medição remota anterior
sobre o corpus real deu 6,6s. Então o que está provado é que **a meta é alcançável com
provedor remoto**, não que ela seja cumprida no corpus real — para isso falta uma rodada
remota sobre ele, que hoje esbarra no GOV-1.

**Faithfulness em 0.81 é o número mais útil desta tabela**, justamente por não atingir a
meta. Ele mede o quanto a resposta se sustenta nos trechos recuperados, e é a primeira
medida independente disso — o juiz de alucinação próprio, que dá 0.00, é mais permissivo
por desenho: só acusa fato novo, e trata reformulação como fiel (ver o prompt em
`run_eval.py`). Dois números diferentes medindo coisas próximas, e o mais rigoroso é o
que reprova.

Estes números **não substituem** a linha de base da 3.1: corpus diferente, muito menor.
A comparação direta entre eles não é válida.

---

## 4. Calibração de parâmetros

O ponto de partida está em SPEC seção 7. Estes números **não** são para aceitar — são para medir e ajustar. Cada tabela abaixo se preenche com uma varredura sobre o golden set.

### 4.1 `SCORE_THRESHOLD`

Trade-off central: threshold alto aumenta a taxa de recusa correta e derruba a cobertura; threshold baixo faz o inverso. O gráfico de precisão vs. threshold é a evidência mais forte do projeto.

Reproduzir: `python eval/calibrar_retrieval.py --threshold`. Corpus real, 64 itens,
`FINAL_K=5`, reranker ligado (o valor da época). Só retrieval, sem LLM.

| Threshold | fonte@5 | Recusa correta (só retrieval) | Cobertura |
|---|---|---|---|
| 0.25 | 74% | 0% | 100% |
| 0.30 | 74% | 0% | 100% |
| 0.35 (partida) | 74% | 9% | 100% |
| 0.40 | 75% | 18% | 100% |
| **0.45 (calibrado)** | **75%** | **55%** | **100%** |
| 0.50 | 72% | 73% | 98% |
| 0.53 | 70% | 82% | 96% |
| 0.55 | 66% | 82% | 94% |
| 0.60 | 57% | 91% | 85% |

![Calibração do threshold: cobertura e acerto de fonte estáveis até 0.45, enquanto a recusa correta salta de 9% para 55%](docs/calibracao-threshold.png)

Reproduzir o gráfico: `python eval/grafico_calibracao.py`. Ele **lê a tabela acima** em
vez de repetir os números — gráfico e texto não podem divergir, e recalibrar significa
reescrever a tabela e regerar, nunca editar os dois à mão.

**0.45 domina 0.35**: mesma cobertura, acerto de fonte igual ou melhor, e a recusa no
gate de retrieval passa de 9% para 55%. Não é um trade-off — é ganho nos dois eixos, e
o valor de partida simplesmente estava errado. Acima de 0.50 o recall começa a cair;
em 0.60 já se perde 15% da cobertura para ganhar 9 pontos de recusa.

`fonte@5` é o proxy de context precision enquanto o RAGAS não está instalado: mede se a
aula esperada apareceu, não se o trecho é relevante. São coisas diferentes.

A sondagem de 10 perguntas registrada abaixo apontava ~0.53. Com o golden set inteiro o
ponto ótimo é mais baixo — mais uma razão para não calibrar em amostra pequena.

#### Sondagem preliminar (2026-08-23) — corpus real

**Não é a calibração.** São 10 perguntas ad hoc (5 dentro do escopo, 5 fora) contra o
corpus real (`grifo_curso_real`, 6.551 chunks, embeddings
`paraphrase-multilingual-MiniLM-L12-v2`). Serve para uma coisa só: mostrar que o valor
de partida está errado por uma margem grande.

| Grupo | Score máximo observado |
|---|---|
| Dentro do escopo (5 perguntas) | 0.565 – 0.767 |
| **Fora do escopo (5 perguntas)** | **0.402 – 0.503** |

Com `SCORE_THRESHOLD = 0.35`, **5 de 5 perguntas fora do escopo passam do gate.**
"Qual a receita do bolo de cenoura?" recupera 11 chunks, o melhor deles em 0.503 —
casando com a aula "Máquina de **Receita**". Homônimo, e o gate não vê diferença.

A separação nesta amostra cai na faixa (0.503, 0.565); o ponto médio é ~0.53. **Não
promova esse número a default** sem o golden set: a margem é de 0.06 em 10 perguntas,
e uma pergunta legítima de baixa similaridade fecha a janela. O que a sondagem prova é
que 0.35 não é defensável neste corpus, não que 0.53 seja o certo.

Vale registrar que a recusa não depende só do threshold: o segundo gate é o próprio LLM
(ADR 002), e a recusa dele agora vira `found: false` corretamente. Os dois em série é o
que sustenta a meta de 0.95.

### 4.2 `FINAL_K`

Reproduzir: `python eval/calibrar_retrieval.py --k`.

| FINAL_K | fonte@k | Tokens de contexto (média) | Cobertura |
|---|---|---|---|
| 3 | 62% | 644 | 100% |
| 5 (partida) | 74% | 1.121 | 100% |
| 8 | **81%** | 1.867 | 100% |

Trade-off direto entre recall e latência, e é aqui que a decisão sobre o NFR-1 se paga.
`FINAL_K=8` compra 7 pontos de acerto por 66% mais tokens de contexto — e tokens de
entrada são tempo de geração, que já é 95% da latência. `FINAL_K=3` faria o inverso:
economiza 43% dos tokens e custa 12 pontos.

**Mantido em 5 por ora.** Subir para 8 só depois de resolver a latência; descer para 3
é a alavanca a puxar se a decisão for perseguir os 3s a qualquer custo.

### 4.3 Chunking

| CHUNK_SIZE / OVERLAP | Context Recall | Observação |
|---|---|---|
| 600 / 100 | — | — |
| 900 / 150 (partida) | — | — |
| 1200 / 200 | — | — |

Incluir no teste perguntas cuja resposta **cruza dois chunks** — é o caso que mais degrada o recall e o que o overlap existe para resolver.

### 4.4 Contribuição de cada componente

Ablação: quanto cada peça do retriever realmente entrega. Justifica manter ou cortar (SPEC seção 11).

Reproduzir: `python eval/calibrar_retrieval.py --ablacao`. `SCORE_THRESHOLD=0.35`.

| Configuração | fonte@5 | Delta | Cobertura |
|---|---|---|---|
| Só vetorial | 66% | baseline | 98% |
| + BM25 (RRF) | 75% | **+9 pp** | 98% |
| + resgate léxico | 77% | +2 pp | **100%** |
| + reranker cross-encoder | 74% | **−3 pp** | 100% |

Duas conclusões, e a segunda é o resultado mais acionável da calibração.

**O BM25 se paga.** Sozinho ele vale 9 pontos, e o resgate léxico soma 2 e ainda leva a
cobertura a 100% — nenhuma pergunta do escopo fica sem chunk. Isso responde à SPEC 11,
que mandava cortar o BM25 primeiro sob pressão de prazo: seria o corte errado.

**O reranker PIORA e ainda custa caro.** Tira 3 pontos de acerto de fonte e adiciona
~613ms por pergunta. A causa provável é o modelo: `ms-marco-MiniLM-L-6-v2` é treinado
em inglês, e reordenar português com ele é pior que a ordem que o RRF já tinha
produzido. Desligado por padrão — não por prazo, por medição. Reativar exige antes
trocar por um reranker multilíngue e refazer esta tabela.

#### Configuração recomendada

| Configuração | fonte@5 | Recusa | Cobertura |
|---|---|---|---|
| Anterior: thr=0.35, reranker ON | 74% | 9% | 100% |
| thr=0.45, reranker ON | 75% | 55% | 100% |
| thr=0.35, reranker OFF | 77% | 9% | 100% |
| **thr=0.45, reranker OFF** | **79%** | **55%** | **100%** |
| thr=0.50, reranker OFF | 74% | 73% | 98% |

A recomendada é melhor que a anterior em todos os eixos medidos, e ainda 613ms mais
rápida. Aplicada como default em `config.py` e `.env.example`.

#### Resgate léxico — medido no corpus real (2026-08-23)

64 itens do golden set do corpus real (53 dentro do escopo, 11 fora), `SCORE_THRESHOLD = 0.53`,
só retrieval, sem LLM.

| Configuração do resgate | fonte@5 | fonte@20 | Recusa correta |
|---|---|---|---|
| Desligado (comportamento anterior) | 68% | 77% | 82% |
| Só IDF ≥ 6 | **75%** | **87%** | **27%** |
| IDF ≥ 6 + ≥3 chunks + 70% concentração | 74% | 83% | 82% |

O resgate só por IDF compra 7 pontos de recall e **destrói a recusa** (82% → 27%).
A razão é conceitual: IDF mede raridade, não pertencimento ao domínio. Neste corpus
`pulse` tem IDF 7,3 e `bolo` tem 7,1 — igualmente raros, e nenhum corte de IDF os separa.
Também não separa por frequência: `pulse` aparece em 4 chunks, `bolo` em 5.

O que separa é a **forma** da ocorrência. Um termo que uma aula ensina é recorrente e
concentrado; um termo incidental se espalha ou aparece uma vez só:

| Termo | Chunks | Aulas | Concentração | Resgatável |
|---|---|---|---|---|
| `pulse` | 4 | 1 | 100% | sim |
| `apqc` | 4 | 1 | 100% | sim |
| `empacotamento` | 18 | 3 | 89% | sim |
| `bolo` | 5 | 4 | 40% | não |
| `cachorro` | 4 | 3 | 50% | não |
| `poema` | 1 | 1 | — | não (abaixo do piso) |

Com os três critérios combinados o recall sobe 6 pontos **sem custo nenhum de recusa**.
O resultado é insensível aos valores exatos — 70% e 80% de concentração, IDF 5 e 6 dão
a mesma linha — o que sugere robustez em vez de ajuste fino. Ainda assim são 64 itens:
reconfirmar quando o golden set for revisado.

### 4.5 Latência do retrieval (medido, 2026-08-23)

Corpus real, 6.551 chunks, antes de qualquer chamada de LLM. Orçamento NFR-1: 3s p95.

| Etapa | `localhost` | `127.0.0.1` |
|---|---|---|
| `fetch_all` — 26 round-trips, build do BM25 | 53,6s | 0,76s |
| Busca vetorial (média de 3) | 2,061s | **0,016s** |
| Query híbrida completa, quente | ~2,07s | **~0,03s** |

No Windows, `localhost` resolve `::1` antes de `127.0.0.1` e cada requisição ao Qdrant
paga ~200ms. O cliente Python amplifica isso para ~2s por busca. Uma letra no
`QDRANT_URL` devolveu 69x na query quente e tirou o retrieval do caminho crítico do
NFR-1 — o orçamento de 3s fica inteiro para o LLM.

**Resolvido (2026-09-02), e agora medido.** A primeira query de cada processo custava
~10s, e quem pagava era o primeiro aluno depois de cada deploy. A API agora aquece
embedder e índice no `lifespan`, antes de aceitar tráfego.

Medido no mesmo corpus real, Qdrant em container, processo novo a cada linha:

| | Tempo |
|---|---|
| 1ª query, processo frio, sem warmup | **10,275s** |
| 2ª query, mesmo processo | **0,031s** |
| **Removido do caminho do primeiro aluno** | **10,24s** |

E a decomposição do que o warmup paga, isolando cada parte:

| Etapa | Tempo | Escala com |
|---|---|---|
| Carga do modelo de embedding | **12,58s** | nada — custo fixo |
| `fetch_all` + build do BM25 (6.551 chunks) | 1,89s | tamanho do corpus |

O que importa não é o total, é a divisão. O texto anterior tratava "carga do modelo +
build do BM25" como duas parcelas comparáveis; medidas, o embedder é **87%** do custo e
não depende do corpus, enquanto o BM25 — a parte que a intuição culpa, por causa dos 26
round-trips — custa 1,9s. Ou seja: otimizar o scroll do Qdrant renderia no máximo 13% do
problema, e num corpus 10x maior essa proporção pioraria pouco. Quem quiser o warmup
instantâneo troca o provedor de embedding por uma API remota, ao custo de mandar cada
pergunta para fora da máquina.

(A soma isolada dá 14,5s contra os 10,3s da query fria porque a primeira medição pegou
os pesos do modelo fora do cache de disco do SO. Os 10,3s são o número realista para um
processo que reinicia num servidor quente; 14,5s é o pior caso, numa máquina fria.)

O aquecimento usa o filtro `{"curso": ...}`, o mesmo que a chain consulta: o cache do
BM25 é chaveado por filtro, e aquecer sem ele construiria um índice que nenhuma pergunta
usa.

**E o cache não invalidava após `/ingest`** — este era bug de correção, não de latência.
O índice léxico é um snapshot do corpus tirado na primeira query. Sem descartá-lo, o
material recém-ingerido ficava visível para a busca vetorial e invisível para o BM25: o
resgate do ADR 001 — o nome exato citado uma vez no material — deixava de alcançar
justamente o conteúdo mais novo. E calado, porque a API seguia respondendo, só que pior.
É o mesmo padrão da regressão do `_point_id` (docstring do `vector_store`): o resgate
parando sem ninguém notar. `pipeline.ingest` agora descarta o índice, e o endpoint o
reconstrói em seguida para o próximo aluno também não pagar o rebuild.

**Limite conhecido:** o cache vive no processo. Com `uvicorn --workers N` seriam N
índices independentes, e um `/ingest` que chega num worker não invalida os outros. Hoje
o compose roda single-worker, então a invalidação vale; escalar horizontalmente exige
mover a invalidação para fora do processo.

---

## 5. Análise de erro

Os casos concretos que falharam, com a causa raiz de cada um. As aulas do corpus real
aparecem pela notação `M<módulo>/A<aula>`: o conteúdo do curso não é público, mas o
diagnóstico não depende dele.

### 5.1 Primeira passada de retrieval — corpus real (2026-08-23)

64 itens do golden set do corpus real, avaliando só o retrieval (sem LLM). Dos 53 itens
dentro do escopo, a fonte esperada apareceu no top-5 em **40 (75%)**, no top-20 em mais
10, e ficou de fora em 3.

Os 3 rótulos foram conferidos por grep no material: **estão corretos**. Não são erro do
golden set, são falha do sistema — e as três têm a mesma causa raiz.

| ID | Pergunta | Esperado | Retrieval trouxe |
|---|---|---|---|
| gs-051 | "O que é o Pulse?" | M1/A2 (o termo aparece 8x, só lá) | **nada** — 0 chunks |
| gs-012 | "Quais são os três tipos de público?" | M1/A7 (título da aula) | M3/A2 |
| gs-010 | "O que é empacotamento de conteúdo?" | M1/A6 (o termo aparece 33x lá) | M1/A1 |

### 5.2 Causa raiz: o BM25 não resgata, só reordena

Nos três casos o BM25 sozinho encontrou o chunk **certo**, com score alto, e o pipeline
o descartou:

| Pergunta | Melhor chunk do BM25 | Score BM25 | Achados só pelo BM25, descartados | `retrieve()` final |
|---|---|---|---|---|
| "O que é o Pulse?" | `M1/A2:chunk79` | 12,07 | 2 | **0 chunks** |
| "três tipos de público" | `M1/A7:chunk0` | 9,93 | 5 | 20 chunks (sem o certo no top-5) |
| "empacotamento" | `M1/A6:chunk259` | 11,36 | 5 | 20 chunks (sem o certo no top-5) |

`hybrid.retrieve` intersecta os dois rankings: só entra no resultado o chunk que já veio
no top-k **vetorial**. O BM25 promove a ordem, mas nunca resgata. Está documentado no
módulo como escolha consciente da v1 ("chunks que só o BM25 encontra ficam de fora"),
com a justificativa de que sem cosseno não existe gate honesto de recusa.

O problema é que essa escolha anula a razão de existir do ADR 001, que diz textualmente:
*"busca puramente semântica erra quando o aluno pergunta pelo nome exato de uma
ferramenta citada uma vez. BM25 pega isso."* O caso "Pulse" é exatamente esse, e o
sistema responde "não encontrei isso no material do curso" sobre conteúdo que existe.

Pior que o falso negativo: é uma recusa **confiante e errada**, o oposto do que o ADR 002
quer proteger.

**Resolvido em 2026-08-23.** O candidato só-BM25 passou a entrar, admitido por evidência
léxica em vez de cosseno — medida que mostrou 0,026 no caso "Pulse", ruído. Buscar o
cosseno para usá-lo como gate não funcionaria: nenhum threshold admite 0,026.

O critério de admissão está na seção 4.4. `gs-051` saiu de 0 chunks para a fonte correta
na posição 1. `gs-012` e `gs-010` continuam fora do top-5 — os termos deles não são raros
o bastante para disparar o resgate, e ficam como caso aberto de análise de erro.

| ID do golden set | Falha | Causa provável | Ação |
|---|---|---|---|
| gs-051 | Recusa sobre conteúdo existente | Gate vetorial descarta o resgate do BM25 | ver 5.2 |
| gs-012 | Fonte certa fora do top-5 | idem | ver 5.2 |
| gs-010 | Fonte certa fora do top-5 | idem | ver 5.2 |

### 5.3 As 9 falsas recusas (2026-08-24)

`taxa_resposta = 0.69` esconde a conta: das 20 recusas, 11 são corretas e **9 são
perguntas que o material responde** — 17% do escopo. É o custo do ADR 002 com número.

| ID | Categoria | Pergunta | Fonte esperada |
|---|---|---|---|
| gs-003 | conceitual | O que são os arquétipos no método FLG? | M1/A2 |
| gs-005 | conceitual | Como definir o inimigo comum da narrativa? | M1/A3 |
| gs-010 | conceitual | O que é empacotamento de conteúdo? | M1/A6 |
| gs-015 | conceitual | Por que o YouTube constrói mais autoridade? | M1/A9 |
| gs-016 | conceitual | Como funciona cross mídia entre canais? | M1/A9 |
| gs-046 | factual | O que é o método CF? | M3/A3 |
| gs-049 | factual | O que é o Studio na configuração de agentes? | M6/A1 |
| gs-052 | factual | O que significa tier na estratégia de retenção? | M4/A2 |
| gs-053 | factual | O que é o ponteiro e como escolher qual mover? | M5/A1 |

**4 das 9 são factuais por termo raro** — a classe que o resgate léxico deveria cobrir.
`empacotamento` e `método CF` já eram conhecidos de 5.1; `Studio`, `tier` e `ponteiro`
são novos. Sinal de que os limiares de 4.4 estão conservadores demais para termos que
aparecem em poucas aulas.

A métrica de recusa correta, sozinha, não vê nada disso. Ela mede só o denominador
`should_answer: false`. Reportar 1.00 sem esta tabela ao lado seria enganoso.

### 5.4 O juiz de alucinação errou nos dois casos que sinalizou

A rodada reportou 2 de 44 (4,5%). Fui verificar as duas por grep no material: **ambas
são falso positivo do juiz.** A taxa real é 0/44.

| ID | O que o juiz acusou | Verificação no material |
|---|---|---|
| gs-043 | "APQC = American Process Quality Center" | o material diz exatamente isso |
| gs-051 | "20 bilhões em campanhas", "PULSE AI" | ambos presentes no material |

O caso `gs-043` merece registro porque é sutil: o nome real da organização é *American
**Productivity** & Quality Center*. O mentor errou na aula, e o bot **repetiu o mentor**.
Para um assistente de curso isso é o comportamento correto — fidelidade à fonte, não à
verdade do mundo. Um juiz que conheça o nome certo vai marcar como alucinação; um juiz
que só compare com os trechos vai aprovar. A segunda leitura é a que o ADR 002 quer.

Consequência prática: o conjunto de calibração de 6 casos é pequeno demais. Ele pegou o
eixo paráfrase-vs-invenção, mas não este. **Amplie antes de publicar a taxa.**

### 5.5 A citação de 100% é artificial

`citacao_em_respondidas = 1.00`, mas medindo antes do `_ensure_citation`: **35 de 44
(80%) vieram do modelo**; as outras 9 foram anexadas à força pela chain.

O número da tabela é verdadeiro por construção, não por mérito. Pior: anexar a citação
do melhor chunk a uma frase que o modelo não fundamentou é atribuir fonte a uma
afirmação não-fundamentada — o oposto do ADR 002. Decidir se `_ensure_citation` fica.
Enquanto ficar, é 0.80 que deve ir para o README, não 1.00.

---

### 5.6 O `pip install` matava a busca vetorial, em silêncio (2026-09-02)

O pior achado do projeto, e o mais barato de não encontrar.

O `pyproject` pedia `qdrant-client>=1.12,<2`; o `docker-compose` fixava o servidor em
`v1.12.4`. Um `pip install` feito hoje resolve para a 1.19 — e essa combinação **grava
todos os vetores zerados**. O upsert retorna sucesso, a contagem de chunks bate, a
ingestão termina limpa e o `/ask` responde. Só a busca vetorial está morta.

O efeito em cascata, medido no corpus real:

| | Com vetores zerados | Depois do conserto |
|---|---|---|
| "Como calcular o CAC?" | **0 chunks** | 5 chunks, scores 0,468–0,552 |
| "O que é o Pulse?" | 4 chunks, score `0.0` | 4 chunks, scores 0,077–0,346 |
| Origem dos chunks | só `bm25` | `vetorial` e `bm25`, conforme o caso |

Todo cosseno dava exatamente 0,0, o gate do FR-24 rejeitava tudo que vinha da via
semântica, e sobrava apenas o que o resgate léxico do ADR 001 salvava — que, por
desenhar-se para ignorar o cosseno, era o único caminho que ainda funcionava. O sistema
respondia com um quinto do seu retrieval e não tinha como saber disso: nenhuma exceção,
nenhum log, nenhum teste vermelho. A avaliação inteira teria rodado e produzido números
plausíveis, só piores.

**É a terceira vez que este projeto falha do mesmo jeito.** O BM25 que reordenava sem
resgatar (5.2), o `_point_id` acoplado ao nome da coleção, e agora isto. Em nenhum dos
três havia erro — só resposta pior. Num RAG a falha silenciosa é o modo de falha padrão,
porque toda camada tem um fallback plausível: se a busca vetorial morre, o léxico
responde; se o léxico morre, o vetorial responde; e o LLM sempre escreve algo.

O conserto tem duas partes, e a segunda é a que importa. Casar os pins resolve a causa
conhecida — `qdrant-client>=1.12,<1.13`, com o acoplamento comentado nos dois arquivos.
Mas pin não impede a próxima causa. Então `upsert_chunks` agora lê de volta um ponto que
acabou de gravar e exige norma maior que zero, falhando alto ali mesmo: quem grava é quem
confere. Uma ingestão que não deixa o índice pesquisável tem de quebrar na hora, não na
primeira pergunta de um aluno. Regressão coberta em `test_hybrid.py`.

Um detalhe que atrasou o diagnóstico: o cliente **avisava**
(`UserWarning: version 1.19.0 is incompatible with server version 1.12.4`) e o aviso
passou despercebido no meio da saída da ingestão. Warning que ninguém lê não é proteção.

---

### 5.7 Duas falhas de método, não de código (2026-09-03)

Ao fazer o RAGAS rodar pela primeira vez, o que apareceu não foram bugs.

**O mesmo modelo respondia e julgava a própria resposta.** `_llm_do_eval()` lia
`LLM_MODEL` — o modelo do chatbot. Então o juiz de alucinação e as métricas RAGAS eram
calculados pelo mesmo modelo que produziu o texto sob avaliação. Auto-julgamento infla
faithfulness e mascara alucinação, e nenhum número medido assim era defensável.
Existe agora `EVAL_LLM_MODEL`, com default vazio caindo para `LLM_MODEL` — para não
mudar rodada anterior nenhuma em silêncio. A rodada da 3.3 é a primeira com juiz
separado: `gpt-4o` julgando `gpt-4o-mini`.

**Context recall não é mensurável com este golden set, e a causa é de desenho.** O RAGAS
a calcula contra um campo `reference`: a resposta correta, escrita à mão. O DC-3 guarda
`expected_source` e `expected_answer_contains` — uma lista de trechos que a resposta
deve conter. Isso sustenta as métricas próprias do projeto e não sustenta a do RAGAS.
Pelo mesmo motivo, `context_precision` entra na variante sem referência, que julga os
contextos contra a resposta gerada em vez de contra um gabarito.

Medir context recall exige escrever 55 respostas de referência à mão. É trabalho real, e
enquanto não existir a linha fica declarada como não medida — nunca estimada por
aproximação a partir do `expected_answer_contains`, que seria fabricar um gabarito e
depois se avaliar contra ele.

**Um limite que vale para os dois casos:** o LLM local de 7B usado nas rodadas anteriores
é instável demais para sustentar qualquer um desses números. Medido, o mesmo item
respondido numa rodada foi recusado na seguinte, com os mesmos dados e `temperature=0`.
Foi o que motivou a rodada remota da 3.3.

---

## 6. Custo

| Item | Medido |
|---|---|
| Tokens de embedding na indexação completa | 1.242.855 (corpus real, 6.551 chunks) |
| Custo da indexação completa | **US$ 0** — embeddings locais |
| Tokens médios por pergunta (entrada / saída) | 1.374 / 220 |
| Custo por 1.000 perguntas | **US$ 0** — LLM local |

Com `EMBEDDING_PROVIDER=local` e o LLM no LM Studio, o pipeline inteiro roda offline:
custo zero e **nenhum trecho do material sai da máquina**. Foi isso que permitiu medir
esta linha de base contra o corpus real com o GOV-1 ainda pendente — a autorização volta
a ser necessária para publicar ou para usar provedor remoto.

Se migrar para API paga, os números acima dão a conta: 1.374 tokens de entrada por
pergunta, 1,24M para reindexar o corpus. Confirme os preços vigentes antes de orçar.

Rodada pública (2026-09-03, `gpt-4o-mini` respondendo e `gpt-4o` julgando): 19.834 tokens
de entrada + 3.220 de saída em 55 perguntas — **US$ 0,0049** pela rodada inteira ao preço
público da época (US$ 0,15/1M entrada, US$ 0,60/1M saída), ~US$ 0,0001 por pergunta.
O juiz `gpt-4o` domina esta conta: são 55 julgamentos + 3 métricas RAGAS sobre 33 itens.
Cálculo derivado dos `tokens_*_total` dos `metricas_*.json`; um script versionado para
`custo_usd` acompanha a tabela de preços em `config.py` (Fase 4 do plano).

Contador de tokens instrumentado desde o dia 1 (FR-36, NFR-2). Confirmar os preços vigentes na página de pricing da OpenAI antes de publicar qualquer número — eles mudam.

---

## 7. Limitações conhecidas

O que estes números **não** cobrem. Declarado aqui para que nenhuma leitura desta
página valha mais do que a medição que a sustenta.

- **Sem tracing nem observabilidade de produção.** Nada de LangSmith ou OpenTelemetry:
  as medições são de avaliação offline, em rodadas. Não existe traçado de requisição
  real, e a latência medida é a do harness de eval, não a de um aluno às 23h. É o
  débito mais estrutural — e depende de tráfego real que o projeto não tem.
- **O `question_log` não tem tráfego real.** São 7 linhas de smoke test, todas da
  pergunta fora de escopo do bolo de cenoura. Ele grava pergunta, `found`, latência e
  tokens — mas **não** grava resposta nem chunks recuperados. Não serve de base para
  golden set e nenhuma métrica aqui sai dele.
- **Não existe gabarito de resposta.** O DC-3 guarda `expected_source` e
  `expected_answer_contains`, mas nenhum gabarito de resposta completa: o eval sabe
  dizer se a *aula* está certa, não se a *resposta* está certa. É também o que trava o
  context recall do RAGAS (ver 5.7). Medir isso exige escrever respostas de referência
  à mão — trabalho real, ainda não pago.
- **As duas rodadas versionadas são incomparáveis entre si.** Corpus real (64 itens,
  6.551 chunks, `qwen2.5-7b` local) contra corpus público (55 itens, 22 chunks,
  `gpt-4o-mini`/`gpt-4o` remotos): corpora, provedores e tamanhos diferentes. Cada
  tabela deste documento se compara apenas consigo mesma; série temporal exige a
  configuração canônica congelada da seção 2.
- **O job de eval está desligado no CI.** Implementado em `.github/workflows/ci.yml`
  atrás de `vars.ENABLE_EVAL` (seção 2). Até ligar, toda rodada é disparada à mão.
- **O juiz de alucinação tem conjunto de calibração pequeno demais.** 6 casos; ele
  errou nos 2 únicos que sinalizou na rodada da 3.1 (ver 5.4). A taxa 0.00 publicada
  foi **verificada à mão**, não liberada pelo juiz. Ampliar a calibração e reportar o
  Kappa de Cohen é o item de maior peso do plano de melhorias.
