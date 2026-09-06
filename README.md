# Grifo

**Assistente de dúvidas para cursos online. Responde só com o material oficial, cita módulo, aula e o minuto do vídeo — e recusa quando a resposta não está lá.**

[![CI](https://github.com/btaguiar/grifo/actions/workflows/ci.yml/badge.svg)](https://github.com/btaguiar/grifo/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11-blue)
![Testes](https://img.shields.io/badge/testes-122-green)

> **Status:** pipeline completo funcionando e primeira linha de base medida sobre um corpus real de 24 sessões e 6.551 trechos. Falta resolver latência e publicar a demo. Nenhum número aqui é estimativa: ou foi medido, ou está vazio.

---

## O problema

Aluno de curso online trava às 23h. A resposta existe — está num vídeo de 40 minutos, módulo 3, aula 7, minuto 22. Ele não tem falta de conteúdo, tem um problema de **recuperação** de conteúdo.

Do outro lado, o suporte responde as mesmas 20 perguntas toda semana, em canais diferentes.

Grifar é marcar o trecho certo no material. É o que o projeto faz.

## Demo

Ainda não há demo pública hospedada — coerente com o resto deste README, o que não
existe fica declarado em vez de prometido. Para ver funcionando, [suba local](#como-rodar):
são três comandos e o corpus de exemplo já vem no repositório.

O comportamento que vale observar são os dois lados da mesma regra: *"Como calcular o
CAC?"* devolve a resposta com módulo, aula e minuto; *"Qual a receita do bolo de
cenoura?"* devolve a recusa. As duas respostas estão certas.

## Métricas

Dois corpora, dois setups, nenhuma estimativa. Metodologia, calibração e análise de erro
em [EVALUATION.md](EVALUATION.md).

| Métrica | Denominador | Meta | Corpus real, LLM local | Corpus de exemplo, LLM remoto | Reproduzir |
|---|---|---|---|---|---|
| **Taxa de recusa correta** | 11 fora do escopo | > 0.95 | **1.00** (11/11) | **1.00** (11/11) | `python eval/run_eval.py` |
| **Taxa de alucinação** | respondidas | < 2% | **0.00** (0/44)¹ | **0.00** (0/33)¹ | `python eval/run_eval.py` |
| **fonte@5** — retrieval puro | 53 em escopo | — | **0.79** | — | `python eval/calibrar_retrieval.py --ablacao` |
| **Fonte correta nas respondidas** — end-to-end | respondidas | — | **0.82** (36/44) | **0.97** (32/33) | `python eval/run_eval.py` |
| **Citação espontânea** | respondidas | — | **0.80** (35/44)² | **1.00** (33/33, contrato)³ | `python eval/run_eval.py` |
| Citação final | respondidas | — | 1.00 — pós-processada | 1.00 — espontânea³ | `python eval/run_eval.py` |
| Faithfulness (RAGAS) | respondidas | > 0.90 | — | 0.87 — **não atinge** | `python eval/run_eval.py` |
| Context Precision (RAGAS) | respondidas | > 0.75 | — | **0.96** | `python eval/run_eval.py` |
| Answer Relevance (RAGAS) | respondidas | > 0.80 | — | **0.84** | `python eval/run_eval.py` |
| Retry de validação do contrato | todas as perguntas | — | — | **0.000** (55/55 de primeira) | `python eval/run_eval.py` |
| **Latência p95** | todas as perguntas | < 3s | 19,9s — não atinge | 3,53s — não atinge³ | `python eval/run_eval.py` |

¹ Verificada à mão: o juiz sinalizou 2 casos, ambos falso positivo (EVALUATION.md 5.4).
Regra de publicação (plano de execução): a taxa de alucinação só aparece ao lado do
**Kappa de Cohen** do juiz — `python eval/calibrar_juiz.py` gera matriz de confusão,
precisão, recall e kappa, gravados no bloco `config` de cada rodada. Kappa < 0.70:
taxa não liberada para produção sem revisão manual.
² Medição única da rodada de 2026-08-24, contada antes do `_ensure_citation`
(EVALUATION.md 5.5) — prompt antigo, `qwen2.5-7b` local, corpus real.
³ Rodada do contrato de saída Pydantic (2026-09-06, EVALUATION.md 3.4): a citação
passou a sair do modelo validada por Pydantic/instructor com retry instruído — 1.00
espontânea com zero re-validações. O custo do contrato é visível e publicado: o p95
saiu de 2,58s (prosa, 2026-09-03) para 3,53s, e os tokens de entrada por pergunta
subiram de 361 para 561.

A segunda coluna é a linha de base sobre o material real (64 perguntas, 20% fora do
escopo). A terceira é o corpus de exemplo deste repositório (55 perguntas), com
`gpt-4o-mini` respondendo e **`gpt-4o` julgando** — modelos separados de propósito, para
o avaliador não ser o avaliado. As colunas **não são comparáveis entre si**: corpora de
tamanhos muito diferentes. "Acerto de fonte" virou **duas métricas** com denominadores
explícitos: `fonte@5` isola o retriever sem LLM; a end-to-end mede a resposta final, mas
só sobre o que foi respondido — denominador que esconde as recusas.

As duas primeiras são métricas próprias, não do RAGAS. São as que importam num contexto
educacional: um aluno que recebe informação errada com confiança está pior do que um
aluno sem resposta.

**Três ressalvas que valem mais que os números**, e estão detalhadas no EVALUATION.md:

- 9 perguntas dentro do escopo foram recusadas indevidamente (17%, derivado da taxa de
  resposta 0.69 nos `metricas_*.json`). É o custo da regra de recusa, e a métrica de
  recusa correta sozinha não mostra isso.
- O juiz de alucinação sinalizou 2 casos; os dois eram falso positivo, achados só na
  inspeção manual.
- A citação em 100% **era** artificial na rodada do corpus real: 80% espontânea, o
  resto a chain anexava à força. O contrato Pydantic (2026-09-06) encerrou o
  pós-processamento no corpus público — citação 1.00 espontânea, zero re-validações
  (EVALUATION.md 3.4); o corpus real ainda não foi re-medido com o contrato.

![Calibração do threshold: cobertura e acerto de fonte estáveis até 0.45, enquanto a recusa correta salta de 9% para 55%](docs/calibracao-threshold.png)

## O que a calibração revelou

O projeto começou com os parâmetros sugeridos num documento de planejamento. Medir
mudou três deles, e as três mudanças estão em [EVALUATION.md](EVALUATION.md) seção 4,
com os comandos que geram cada tabela: `python eval/calibrar_retrieval.py --threshold`
para o limiar de corte, `--ablacao` para o reranker e o BM25 — só retrieval, sem LLM
no caminho (~30ms por consulta, rodável à vontade):

**O limiar de corte estava errado.** 0.35 deixava passar 10 de 11 perguntas fora do
escopo. Em 0.45 a recusa sobe para 55% sem perder cobertura nenhuma — ganho nos dois
eixos, não trade-off.

**O reranker piorava o resultado.** Tirava 3 pontos de acerto de fonte e custava 613ms
por pergunta. A causa é o modelo: `ms-marco-MiniLM` é treinado em inglês, e reordenar
português com ele fica pior que a ordem que o RRF já tinha produzido. Desligado por
medição, não por prazo.

**O BM25 era a peça mais valiosa, não a mais descartável.** O plano original mandava
cortá-lo primeiro sob pressão de prazo. A ablação mostra que sozinho ele vale 9 pontos
de acerto de fonte — e um resgate léxico por cima leva a cobertura a 100%.

## Arquitetura

Ingestão offline: loaders (PDF, VTT/SRT, Markdown, transcrição com timestamp) →
anonimização de PII → chunking estrutural → embeddings → Qdrant.

Consulta online: retriever híbrido (vetorial + BM25 com RRF e resgate léxico) → prompt
com regra de citação → LLM → resposta com fontes.

Diagrama e os três ADRs em [ARCHITECTURE.md](ARCHITECTURE.md). Requisitos com critério
de aceite em [SPEC.md](SPEC.md).

**Stack:** Python 3.11 · LangChain (LCEL) · Qdrant · FastAPI · Streamlit · Docker Compose · GitHub Actions.

O LLM e os embeddings entram por qualquer API compatível com OpenAI, escolhida só por
variável de ambiente — nenhum código muda entre elas. Três setups em [.env.example](.env.example):
**OpenRouter** (uma chave para os dois, é o default), **OpenAI direto**, e **100% local**
via LM Studio ou Ollama.

## Como rodar

```bash
cp .env.example .env               # preencha só OPENAI_API_KEY
docker compose up -d               # sobe Qdrant + API + UI
docker compose run --rm ingest     # indexa o corpus de exemplo
```

- API e Swagger: http://127.0.0.1:8000/docs
- UI de chat: http://127.0.0.1:8501

Pergunte *"Como calcular o CAC?"* e você recebe a resposta com a aula citada. Pergunte
*"Qual a receita do bolo de cenoura?"* e recebe a recusa — que é o comportamento correto.

A primeira build baixa PyTorch e leva alguns minutos. A ingestão roda dentro do
container: você não precisa de Python na máquina. Custo de rodar assim, sobre o corpus
de exemplo: **US$ 0,0049 pela rodada de avaliação inteira** — 19.834 tokens de entrada
+ 3.220 de saída medidos em 55 perguntas, ao preço público do `gpt-4o-mini`
(US$ 0,15/1M entrada, US$ 0,60/1M saída), ~US$ 0,0001 por pergunta. Cálculo e ressalvas
no [EVALUATION.md §6](EVALUATION.md). Para custo zero e nada saindo da máquina, use o
setup local do `.env.example`.

Desenvolvimento:

```bash
python -m venv .venv && .venv\Scripts\activate
pip install -e ".[dev]"
pytest                                # 122 testes, sem serviços externos
pytest -m integration                 # 4 testes, exigem Qdrant no ar
python eval/calibrar_retrieval.py     # varreduras de calibração
python eval/run_eval.py               # suite completa de avaliação
pip-audit                             # vulnerabilidades conhecidas nas dependências
```

## Privacidade

O material do curso nunca entra no repositório. O `.gitignore` foi o primeiro commit,
antes de qualquer arquivo de dados, e cobre também os resultados brutos da avaliação —
eles carregam o texto dos trechos recuperados.

Dois corpora, um código: o real fica local, o sanitizado em `samples/` é commitado e é o
que a demo e o CI usam. O código recebe um caminho e não sabe a diferença.

A ingestão anonimiza e-mail, telefone e CPF antes de indexar, e aplica o mesmo passo à
pergunta do aluno antes de gravá-la no log.

Com o setup local, embeddings **e** LLM rodam na máquina: nenhum trecho do material sai
dali. É o modo a usar para material que você não pode enviar a terceiros.

## Limitações da v1

Declaradas de propósito, não esquecidas:

- Um curso por índice — sem multi-tenant.
- Sem autenticação de aluno nem integração com plataforma.
- Contexto de sessão curto, sem memória de conversa longa.
- Sem streaming de resposta — e com LLM local, ele faz falta.
- A latência depende inteiramente do modelo, não da arquitetura: o retrieval custa 30ms.
  Com provedor remoto o p95 era 2,58s (prosa) e passou a 3,53s com o contrato de saída
  estruturado — acima da meta de 3s, custo publicado (EVALUATION.md 3.4). Com um 7B
  local, 19,9s.
- O conjunto de calibração do juiz tinha 6 casos quando a taxa 0.00 foi medida; agora
  tem 99 (33 positivos), com Kappa de Cohen calculado em `calibrar_juiz.py`. A taxa não
  é liberada para produção sem kappa >= 0.70 na calibração revisada.

## Próximos passos

Em ordem de quanto mudariam o projeto, não de esforço:

**Streaming, antes de qualquer otimização de latência.** O p95 de 6,6s é quase todo
geração, e o retrieval já custa ~30ms. Enquanto a resposta chega inteira de uma vez, o
tempo total *é* o tempo percebido; com streaming o que conta passa a ser o primeiro
token, que já está em ~1s. Otimizar o retriever aqui seria trabalhar no lugar errado.

**Um reranker multilíngue.** O cross-encoder foi desligado por medição, não por prazo:
`ms-marco-MiniLM` é treinado em inglês e piorava a ordem em português. A decisão certa
foi desligar; a decisão melhor é testar um modelo que fale a língua do corpus.

**Fechar as 9 falsas recusas.** É o número que a taxa de recusa correta esconde: 17% das
perguntas dentro do escopo foram recusadas indevidamente. Métrica boa não é a que
parece boa, é a que mostra o custo da própria regra — e essa é a que falta atacar.

**Um juiz de alucinação em que dê para confiar sozinho.** Hoje é um 7B calibrado contra
6 casos, e ele errou nos dois casos que sinalizou. A taxa de 0% é real, mas foi
verificada à mão; publicar esse número sem revisão manual exigiria um juiz melhor e um
conjunto de calibração maior.

**Context recall do RAGAS — o que falta.** Três das quatro métricas da SPEC já rodam
(EVALUATION.md 3.3). A quarta, context recall, esbarra no desenho do golden set: ela
exige respostas de referência escritas à mão, que não existem — e fabricá-las por
aproximação seria avaliar contra um gabarito inventado.

### O que eu faria diferente

**Mediria antes de decidir, e mais cedo.** Três parâmetros vieram de um documento de
planejamento e os três estavam errados: o threshold deixava passar 10 de 11 perguntas
fora do escopo, o reranker piorava o resultado, e o BM25 — que o plano mandava cortar
primeiro sob pressão de prazo — era a peça mais valiosa. Nenhuma dessas descobertas
exigia código novo, só uma medição que eu podia ter feito na primeira semana.

**Desconfiaria de componente que "funciona".** Os dois piores bugs foram silenciosos: o
BM25 que reordenava mas nunca resgatava, anulando o ADR 001 que ele existia para
cumprir, e o cache léxico que servia um corpus congelado depois de cada ingestão. Em
nenhum dos dois havia erro, log ou teste vermelho — a busca seguia respondendo, só que
pior. Num RAG, a falha silenciosa é o modo de falha padrão, e o teste que a pega tem de
afirmar o que o componente *recupera*, não que ele rodou.

---

Documentação: [SPEC.md](SPEC.md) · [ARCHITECTURE.md](ARCHITECTURE.md) · [EVALUATION.md](EVALUATION.md) · [CHANGELOG.md](CHANGELOG.md)
