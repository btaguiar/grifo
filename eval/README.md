# eval/

- `golden_set.jsonl` — **seed com 6 itens de exemplo, no formato DC-3.** Falta chegar a 50+.
  Escreva na semana 2, a partir das dúvidas que realmente se repetiam. Os itens atuais
  ilustram as três categorias e devem ser substituídos por perguntas reais.
- `run_eval.py` — executa a suite. Semana 3.
- `results/` — saída versionada, uma execução por arquivo, nomeada com timestamp e hash do commit.

Composição alvo do golden set (SPEC DC-3): 60% conceitual, 20% factual/sigla (testa o BM25),
20% fora de escopo (`should_answer: false` — testa a regra de recusa).

Perguntas fora do escopo não são enfeite: a taxa de recusa correta é a métrica que quase
ninguém mede e a que você vai defender em entrevista.
