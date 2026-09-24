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
- `judge_calibration.jsonl` — casos de referência do juiz. Cada um carrega
  `procedencia`: `humano` (alguém leu e decidiu) ou `construcao` (o rótulo decorre da
  construção e foi verificado por código). `"rascunho": true` = sem rótulo confirmado,
  fora da conta do kappa.
- `confirmar_rotulos.py` — promove rascunho a rótulo confirmado **por verificação**:
  injetado precisa ter o marcador na resposta e ausente do contexto; fiel e paráfrase
  precisam não ter número ou nome próprio fora do contexto. O que não passa no próprio
  invariante continua em rascunho. `--aplicar` grava; sem ele, só relata.
- `gerar_rascunhos_calibracao.py` — gera rascunhos de calibração a partir das respostas
  reais da rodada pública (fiéis verbatim, paráfrases agressivas, fatos injetados com
  marcador verificado ausente do contexto). Idempotente: descarta rascunhos e preserva
  o que já foi confirmado.
- `triagem_calibracao.py` — audita **os rótulos**, não o juiz: assinatura de superfície
  (a classe positiva se separa sem ler o contexto?), n efetivo (casos ÷ contextos
  distintos), fato novo em paráfrase e positivo tardio. Sem LLM, determinístico.
  Rode antes de publicar qualquer kappa. Hoje **aprova** — o histórico está abaixo.
- `grafico_calibracao.py` — gera `docs/calibracao-threshold.png` a partir da tabela do
  EVALUATION.md.
- `results/` — uma execução por arquivo. Só `metricas_*.json` e `calibracao_juiz.json`
  são versionados; o resto carrega texto do curso.

Composição do golden set (SPEC DC-3): 60% conceitual, 20% factual/sigla (testa o BM25),
20% fora de escopo (`should_answer: false` — testa a regra de recusa).

Distribuição-alvo da calibração do juiz (plano de execução, Fase 1): ~40% fiéis,
~30% paráfrase fiel agressiva, ~30% com fato novo injetado — sem casos positivos
suficientes o kappa é indefinido.

**O que a triagem já pegou, e por que ela continua rodando.** Na primeira execução
(2026-09-06) o conjunto reprovava: 61% dos casos positivos terminavam numa frase que
abria com fórmula de atribuição ("O material recomenda…") contra 2% dos negativos, e os
positivos eram mais curtos (mediana 214 contra 308 chars). Duas pistas de **forma** que
separavam as classes sem ler o contexto — um juiz acertaria por elas, e o kappa subiria
medindo a fabricação em vez do juiz. Os 30 injetados foram reescritos com o fato novo
costurado no MEIO da resposta, sem fórmula de atribuição e no comprimento dos negativos:
gap de 2pp, razão de tamanho 1.05, triagem aprovando. **Rode de novo a cada lote novo de
casos** — a assinatura volta sozinha quando se fabrica em série.

A triagem também reporta que os 99 casos cobrem só 33 contextos distintos (3 casos por
contexto, uma família cada): itens que compartilham contexto não são independentes, então
o kappa se publica como "97 casos sobre 33 contextos" — os 97 confirmados, que cobrem os
mesmos 33.

**Estado do kappa:** `gpt-4o` 0.905, `qwen2.5-7b` 0.408, mesmo prompt e mesmos casos
(EVALUATION.md 5.9). 91 rótulos por construção, 6 humanos, 2 em rascunho.

**Antes de rotular, leia a regra de fronteira** (EVALUATION.md 3.2): elaboração inferida
não conta como alucinação; só fato novo ausente dos trechos conta. Decidir isso caso a
caso durante a revisão faz o kappa medir a inconsistência de quem rotula.

Perguntas fora do escopo não são enfeite: a taxa de recusa correta é a métrica que quase
ninguém mede e a que você vai defender em entrevista.
