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
- `grafico_calibracao.py` — gera `docs/calibracao-threshold.png` a partir da tabela do
  EVALUATION.md.
- `results/` — uma execução por arquivo. Só `metricas_*.json` e `calibracao_juiz.json`
  são versionados; o resto carrega texto do curso.

Composição do golden set (SPEC DC-3): 60% conceitual, 20% factual/sigla (testa o BM25),
20% fora de escopo (`should_answer: false` — testa a regra de recusa).

Distribuição-alvo da calibração do juiz (plano de execução, Fase 1): ~40% fiéis,
~30% paráfrase fiel agressiva, ~30% com fato novo injetado — sem casos positivos
suficientes o kappa é indefinido.

Perguntas fora do escopo não são enfeite: a taxa de recusa correta é a métrica que quase
ninguém mede e a que você vai defender em entrevista.
