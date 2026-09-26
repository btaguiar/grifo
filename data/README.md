# data/ — nada aqui vai para o git

Os subdiretórios estão no `.gitignore` desde o primeiro commit (SPEC GOV-2). Um PDF que
entra no histórico do git só sai com `filter-repo` e force-push.

| Diretório | Conteúdo |
|---|---|
| `raw/` | Material original do curso. **Corpus real, só na sua máquina.** |
| `processed/` | Saídas intermediárias e `question_log.jsonl` |
| `index/` | Artefatos locais de índice (BM25 serializado, caches) |

O corpus público e sanitizado fica em [samples/](../samples/), esse sim commitado. O código
recebe um path e não sabe a diferença (FR-10).

**GOV-1, a autorização por escrito para usar o material real, voltou concedida em
setembro de 2026** ([docs/autorizacao-material.md](../docs/autorizacao-material.md)).
Isso permite indexar e processar o material — **não** publicá-lo. Este diretório
continua fora do git, e é o `.gitignore` que garante isso, não a lembrança de quem
commita.
