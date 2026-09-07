# eval/

- `golden_set.jsonl` — 55 itens no formato DC-3 (44 em escopo, 11 fora), corpus público
  de `samples/`. O do corpus real (`golden_set.local.jsonl`, 64 itens) é local por
  privacidade — o código recebe um caminho e não sabe a diferença.
- `run_eval.py` — suite completa: métricas próprias, juiz de alucinação e RAGAS.
  Grava em `results/` o bruto (local) e o `metricas_*.json` versionado.
- `calibrar_retrieval.py` — varreduras de calibração (threshold, final_k, ablação).
  Só retrieval, sem LLM.
- `calibrar_juiz.py` — calibra o juiz de alucinação: matriz de confusão, precisão,
  recall, taxa de falso positivo e **Kappa de Cohen**. Grava `results/calibracao_juiz.json`
  (versionado), que o `run_eval.py` carrega no bloco `config` de cada rodada.
- `judge_calibration.jsonl` — casos rotulados à mão. Casos com `"rascunho": true` ainda
  não foram revisados e ficam fora da conta do kappa.
- `gerar_rascunhos_calibracao.py` — gera rascunhos de calibração a partir das respostas
  reais da rodada pública (fiéis verbatim, paráfrases agressivas, fatos injetados com
  marcador verificado ausente do contexto). Revisão humana é o passo que falta.
- `triagem_calibracao.py` — audita **os rótulos**, não o juiz: assinatura de superfície
  (a classe positiva se separa sem ler o contexto?), n efetivo (casos ÷ contextos
  distintos), fato novo em paráfrase e positivo tardio. Sem LLM, determinístico.
  Rode antes de publicar qualquer kappa — hoje **reprova**, e o motivo está abaixo.
- `grafico_calibracao.py` — gera `docs/calibracao-threshold.png` a partir da tabela do
  EVALUATION.md.
- `results/` — uma execução por arquivo. Só `metricas_*.json` e `calibracao_juiz.json`
  são versionados; o resto carrega texto do curso.

Composição do golden set (SPEC DC-3): 60% conceitual, 20% factual/sigla (testa o BM25),
20% fora de escopo (`should_answer: false` — testa a regra de recusa).

Distribuição-alvo da calibração do juiz (plano de execução, Fase 1): ~40% fiéis,
~30% paráfrase fiel agressiva, ~30% com fato novo injetado — sem casos positivos
suficientes o kappa é indefinido.

**O que a triagem reprova hoje, e o que fazer com isso.** Medido em 2026-09-06 sobre os
99 casos: 61% dos positivos terminam numa frase que abre com fórmula de atribuição ("O
material recomenda…") contra 2% dos negativos, e os positivos são mais curtos (mediana
214 contra 308 chars). São duas pistas de **forma** que separam as classes sem ler o
contexto — um juiz pode acertar por elas, e o kappa subiria medindo a fabricação em vez
do juiz. Antes de rotular: reescrever parte dos positivos com o fato novo no MEIO da
resposta, sem fórmula de atribuição, no mesmo comprimento dos negativos. A triagem
também reporta que os 99 casos cobrem só 33 contextos distintos (3 casos por contexto,
uma família cada): itens que compartilham contexto não são independentes, então o kappa
se publica como "99 casos sobre 33 contextos".

Perguntas fora do escopo não são enfeite: a taxa de recusa correta é a métrica que quase
ninguém mede e a que você vai defender em entrevista.
