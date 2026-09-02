# tests/

`tests/unit/` roda sem serviço externo e é o que o CI executa em todo push.
`tests/integration/` exige Qdrant e OpenAI, marcado com `@pytest.mark.integration` e
excluído do job padrão (`pytest -m "not integration"`).

## A escrever, por requisito

Escreva o teste junto com o código, não depois.

| Requisito | Teste | Onde |
|---|---|---|
| FR-11 | Um fixture por formato (PDF, VTT, SRT, MD) → Documents com texto não vazio | unit |
| FR-12 | Texto com e-mail, telefone e CPF → nenhum sobrevive | unit (fixture `texto_com_pii`) |
| FR-13 | Nenhum chunk cruza fronteira de aula; schema DC-1 completo em todo chunk | unit |
| FR-15 | Ingerir 2x o mesmo diretório → mesma contagem | integration |
| FR-20 | Query filtrada por módulo só devolve chunks do módulo | integration |
| FR-21 | Sigla citada uma única vez é recuperada pelo BM25 | unit |
| FR-24 | Query fora do domínio → zero chunks acima do threshold | unit |
| FR-31 | Resposta com `found: true` contém `[Módulo X, Aula Y]` bem formado | unit (LLM mockado) |
| FR-32 | Pergunta fora do escopo → string de recusa exata e `found: false` | unit (LLM mockado) |
| FR-35 | Amostra do golden set respeita o limite de 200 palavras | integration |
| FR-52 | Pergunta gravada no log passou pela anonimização | unit |

Os dois que **não** podem faltar são FR-31 e FR-32: são o ADR 002 virando garantia
executável, e é isso que separa este projeto de uma demo.
