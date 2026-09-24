# grifo — Plano de execução

Objetivo: transformar o `grifo` na peça central de um portfólio de AI Engineer,
fechando o ciclo de avaliação que já está 70% construído.

Contexto para quem executa: o repositório já tem Ruff + mypy + py.typed, 126
testes, ablação de reranker feita por medição, resgate léxico com critério de
IDF, juiz binário e três arquivos por rodada em `eval/results/`. **Nada disso
deve ser reescrito.** O trabalho é fechar lacunas específicas.

## Regras que valem para todas as fases

- Não invente números. Toda métrica publicada tem que sair de um script
  versionado neste repositório, com o comando de reprodução no README.
- Se uma métrica piorar depois de uma mudança, publique a piora e escreva por
  quê. O valor do repositório está na honestidade metodológica, não nos valores.
- Nenhuma métrica nova entra sem um teste em `tests/unit/` cobrindo o cálculo.
- Preserve o padrão de docstring existente: todo parâmetro numérico novo explica
  por que aquele valor, citando a medição que o justificou.
- Não mexer em `hybrid.py` (resgate léxico) nem em `chunker.py`. Estão medidos e
  documentados.

---

## Fase 0 — Higiene dos números publicados

**Por quê:** hoje o README publica como "Acerto de fonte" a fusão de duas
métricas diferentes, e declara citação 100% num número que é anexado à força.
Um avaliador que abrir o código vê isso em dois minutos.

**Tarefas**

1. Separar as duas métricas de fonte no README e no `EVALUATION.md`, cada uma
   com denominador explícito:
   - `fonte@5 (retrieval)` — 0.79, saída de `sweep_ablacao()` em
     `calibrar_retrieval.py:126`, denominador 53, sem LLM no caminho.
   - `fonte correta nas respondidas (end-to-end)` — 0.8182, saída de
     `run_eval.py`, denominador = itens com `found=true`.
2. No README, reportar citação como dois números: espontânea (80%) e final após
   `_ensure_citation` (100%), deixando claro que o segundo é pós-processamento.
3. Adicionar ao `EVALUATION.md` uma seção "Limitações conhecidas" com, no
   mínimo: ausência de tracing em produção, `question_log` sem tráfego real,
   ausência de gabarito de resposta, e as duas rodadas versionadas serem
   incomparáveis entre si (corpora e provedores diferentes).

**Critério de aceite:** nenhum número no README existe sem que o comando que o
gera esteja documentado ao lado.

**Estimativa:** 3h.

---

## Fase 1 — Calibração do juiz e Kappa de Cohen

**Por quê:** este é o item de maior peso do portfólio inteiro. Alucinação 0.00
hoje se apoia num juiz calibrado contra 6 casos, que errou nos dois únicos que
sinalizou — ou seja, zero verdadeiros positivos. Em paralelo, `faithfulness` do
RAGAS mede algo próximo e dá 0.81. Duas métricas discordam e a mais permissiva é
a publicada.

**Trabalho manual (não delegável ao Claude Code)**

Expandir `eval/judge_calibration.jsonl` de 6 para 80–100 casos rotulados à mão,
com a distribuição alvo:

- ~40% respostas fiéis ao contexto (esperado: NÃO alucinou)
- ~30% paráfrase fiel, incluindo reformulação agressiva (esperado: NÃO)
- ~30% com fato novo injetado — número, data, nome, benchmark, recomendação
  ausente do contexto (esperado: SIM)

Os casos positivos podem ser fabricados a partir de respostas reais editadas.
Sem casos positivos suficientes o Kappa é indefinido.

**Tarefas de código**

1. Estender `calibrar_juiz.py` para calcular e reportar:
   - matriz de confusão completa (TP, FP, TN, FN)
   - precisão, recall e taxa de falso positivo
   - Kappa de Cohen entre o rótulo humano e o veredito do juiz
2. Mitigar viés de posição: onde o julgamento for comparativo, executar a
   avaliação duas vezes com a ordem das respostas invertida nas tags e só contar
   como veredito o que for estável nas duas ordens. Se o julgamento atual é
   estritamente single-answer, registrar isso no `EVALUATION.md` e pular o item.
3. Gravar o Kappa e a matriz no bloco `config` dos `metricas_*.json`, para que
   toda rodada carregue a confiabilidade do juiz que a produziu.
4. Publicar no README a alucinação **junto** com o Kappa do juiz. Se o Kappa
   ficar abaixo de 0.70, publicar assim mesmo, com uma frase explicando que o
   número não está liberado para produção por esse critério.
5. Reconciliar com o RAGAS: uma seção no `EVALUATION.md` comparando o veredito
   do juiz próprio com `faithfulness` item a item, listando os casos onde
   discordam. A divergência documentada vale mais que a convergência forçada.

**Critério de aceite:** `python eval/calibrar_juiz.py` imprime Kappa, matriz de
confusão e as duas taxas de erro; o README não cita alucinação sem citar Kappa.

**Estimativa:** 8h de código + 12h de rotulagem manual.

---

## Fase 2 — Contrato de saída com Instructor + Pydantic

**Por quê:** hoje a saída do LLM é prosa livre tratada por regex, e
`_ensure_citation` conserta o modelo à força em 20% dos casos. Isso torna a
métrica de citação artificial e faz qualquer mudança de prompt mover números sem
rastro. Resolve o quinto débito da auditoria e entrega um projeto inteiro do
catálogo dentro de um repo que já existe.

**Tarefas**

1. Definir em `generation/schemas.py` (arquivo novo) o contrato:
   - `SourceRef`: `modulo: str`, `aula: str`, `localizador: str` (timestamp ou
     página), com validador exigindo que o par módulo/aula exista entre os
     chunks recuperados naquela query.
   - `GrifoAnswer`: `found: bool`, `answer: str`, `citations: list[SourceRef]`,
     com validador de modelo — se `found=True`, `citations` não pode ser vazia;
     se `found=False`, `answer` tem que ser exatamente `REFUSAL_MESSAGE` e
     `citations` vazia.
2. Integrar `instructor` em `chain.py:126`, com `max_retries=2`. O retry
   instruído devolve ao modelo o erro do Pydantic.
3. Manter `_ensure_citation` no código, mas **desativado por flag**
   (`FORCE_CITATION=false` em `config.py`), exatamente como foi feito com o
   reranker. Rodar o eval nas duas configurações e publicar a comparação.
4. Adicionar ao `run_eval.py` a métrica `retry_rate` — proporção de queries que
   precisaram de pelo menos uma re-tentativa de validação.
5. Preservar o envelope HTTP atual (`AskResponse` em `api/main.py`) sem quebra de
   contrato para a UI e para os testes de integração.

**Critério de aceite:** com `FORCE_CITATION=false`, a citação medida é 100%
espontânea ou o número publicado cai — e o número que cair é o publicado.
Nenhum regex sobre a saída do modelo no caminho de produção.

**Estimativa:** 15–20h.

---

## Fase 3 — Ativar o gabarito de resposta

**Por quê:** `expected_answer_contains` está nos dois golden sets, foi rotulado à
mão, e nenhuma métrica o lê. É trabalho já pago que não rende nada, e é a única
coisa que hoje impede o eval de dizer se a *resposta* está certa — ele só sabe
dizer se a *aula* está certa.

**Tarefas**

1. Implementar `cobertura_conteudo()` em `run_eval.py`: proporção das substrings
   de `expected_answer_contains` presentes na resposta, normalizando caixa e
   acentuação. Reportar tanto a média por item quanto a proporção de itens com
   cobertura total.
2. Adicionar ao `EVAL_STRICT` uma meta para essa métrica. Definir o limiar a
   partir da primeira rodada medida, não a priori — e registrar no
   `EVALUATION.md` que o limiar foi calibrado assim.
3. Avaliar (e documentar a decisão, mesmo que negativa) a adição de um campo
   `reference` ao schema DC-3 do golden set, que destravaria `context_recall` no
   RAGAS. Se a decisão for não fazer, escrever por quê na seção de limitações.

**Critério de aceite:** nenhum campo do golden set fica sem consumidor. Se algum
sobrar, ele é removido do schema.

**Estimativa:** 6h.

---

## Fase 4 — Ligar o eval no CI e criar série temporal

**Por quê:** o job já está escrito em `.github/workflows/ci.yml`, atrás de
`vars.ENABLE_EVAL`. Desligado, o `EVALUATION.md:29` afirma algo que não acontece.
E as duas rodadas versionadas usam corpora e provedores diferentes — são dois
pontos que não formam série.

**Tarefas**

1. Ligar o job com uma configuração canônica e congelada, documentada no
   `EVALUATION.md` como "configuração de série": corpus `samples/`, modelo fixo,
   `SCORE_THRESHOLD=0.45`, reranker off. Qualquer rodada fora dessa configuração
   não entra na série.
2. Marcar os `metricas_*.json` existentes como fora da série, com um campo
   `serie: false`, para que a comparação não seja feita por engano.
3. Gate de regressão no PR: comparar contra a última rodada da série e falhar se
   recusa cair mais de 5 pontos, alucinação subir mais de 2 pontos, ou p95
   ultrapassar 3000ms. Reaproveitar o `EVAL_STRICT` que já existe.
4. Script `eval/serie_temporal.py`: lê todos os `metricas_*.json` com
   `serie: true`, ordena por commit, gera PNG em `docs/`. Seguir o padrão do
   `grafico_calibracao.py` — o gráfico é derivado dos dados, nunca desenhado à
   mão.
5. Custo em dólar: tabela de preço por modelo em `config.py` e campo `custo_usd`
   nos `metricas_*.json`, calculado a partir dos tokens que já são contados.
   Hoje o custo só existe como texto no `EVALUATION.md §6`.

**Critério de aceite:** um PR que degrade o retrieval falha no CI sem
intervenção humana. O gráfico de série tem pelo menos 3 pontos comparáveis.

**Estimativa:** 15h.

---

## Fase 5 — Versionamento de prompt

**Por quê:** `ANSWER_SYSTEM_PROMPT` e `JUDGE_PROMPT` são strings em código sem
hash nos resultados. Trocar uma vírgula move os números sem deixar rastro — e o
histórico `0.43 → 0.795 → 0.045` mostra exatamente esse efeito acontecendo.

**Tarefas**

1. Mover os prompts para `src/grifo/generation/prompts/*.txt`, carregados em
   tempo de import. Manter a f-string de interpolação em `prompts.py`.
2. Gravar o SHA-256 dos dois prompts no bloco `config` dos `metricas_*.json`.
3. Teste unitário que falha se um prompt mudar sem que o hash de referência seja
   atualizado — mudança de prompt vira decisão explícita, não efeito colateral.

**Critério de aceite:** dois `metricas_*.json` com números diferentes sempre têm
como ser explicados por diferença em `config`.

**Estimativa:** 4h.

---

## Fase 6 — README como documento de produto

**Por quê:** o relatório de mercado é explícito — o README é um ensaio
persuasivo, não um manual de instalação. Ele é lido antes do código.

**Estrutura obrigatória, nesta ordem**

1. **Problema real resolvido**, em duas frases, sem jargão de framework.
2. **Métricas acima da dobra**, cada uma com denominador e link para o script:
   recusa correta, fonte@5, fonte end-to-end, alucinação + Kappa do juiz,
   cobertura de conteúdo, p95, custo por query.
3. **Diagrama Mermaid** do fluxo: ingestão → chunking com fronteira estrutural →
   Qdrant + BM25 → RRF → resgate léxico → gate de threshold → chain → contrato
   Pydantic → envelope HTTP.
4. **Decisões medidas** — a seção que diferencia este repositório. Uma tabela com
   a decisão, o número que a justificou e o link para a ablação: reranker
   desligado (77% → 74%, +613ms), resgate léxico com IDF e concentração (recusa
   82% vs 27% sem os critérios), threshold em 0.45, escala binária no juiz em vez
   de Likert.
5. **Limitações conhecidas**, herdadas da Fase 0.
6. **Rodar**: `docker compose up -d` e o comando de eval. No fim, não no começo.

**Estimativa:** 5h.

---

## Ordem e total

Fases 0 → 1 → 2 → 3 → 4 → 5 → 6, nesta ordem. A Fase 1 tem rotulagem manual que
pode correr em paralelo com a Fase 2.

Total estimado: 55–65h, das quais ~12h são rotulagem manual.

## Fora de escopo

Não fazer agora, e registrar como limitação conhecida no README:

- **Tracing / observabilidade de produção** (LangSmith, OpenTelemetry). É o
  débito mais estrutural, mas depende de tráfego real que o projeto não tem.
- **Golden set a partir do `question_log`**. O arquivo tem 7 linhas de smoke
  test e não grava resposta nem chunks.
- **Refatorar chunking para semântico.** O chunking atual está medido e
  justificado; trocar sem necessidade destrói a comparabilidade da série.
