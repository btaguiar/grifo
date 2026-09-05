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

| Métrica | Meta | Corpus real, LLM local | Corpus de exemplo, LLM remoto |
|---|---|---|---|
| **Taxa de recusa correta** | > 0.95 | **1.00** (11/11) | **1.00** |
| **Taxa de alucinação** | < 2% | **0.00** (verificado à mão) | **0.00** |
| Acerto de fonte | — | 0.79 | **0.97** |
| Faithfulness (RAGAS) | > 0.90 | — | 0.81 — **não atinge** |
| Context Precision (RAGAS) | > 0.75 | — | **0.96** |
| Answer Relevance (RAGAS) | > 0.80 | — | **0.83** |
| Latência p95 | < 3s | 19,9s — não atinge | **2,58s** — atinge |

A segunda coluna é a linha de base sobre o material real (64 perguntas, 20% fora do
escopo). A terceira é o corpus de exemplo deste repositório (55 perguntas), com
`gpt-4o-mini` respondendo e **`gpt-4o` julgando** — modelos separados de propósito, para
o avaliador não ser o avaliado. As colunas **não são comparáveis entre si**: corpora de
tamanhos muito diferentes.

As duas primeiras são métricas próprias, não do RAGAS. São as que importam num contexto
educacional: um aluno que recebe informação errada com confiança está pior do que um
aluno sem resposta.

**Três ressalvas que valem mais que os números**, e estão detalhadas no EVALUATION.md:

- 9 perguntas dentro do escopo foram recusadas indevidamente (17%). É o custo da regra
  de recusa, e a métrica de recusa correta sozinha não mostra isso.
- O juiz de alucinação sinalizou 2 casos; os dois eram falso positivo, achados só na
  inspeção manual.
- A citação em 100% é artificial — 80% vieram do modelo, o resto a chain anexou.

![Calibração do threshold: cobertura e acerto de fonte estáveis até 0.45, enquanto a recusa correta salta de 9% para 55%](docs/calibracao-threshold.png)

## O que a calibração revelou

O projeto começou com os parâmetros sugeridos num documento de planejamento. Medir
mudou três deles, e as três mudanças estão em [EVALUATION.md](EVALUATION.md) seção 4:

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
container: você não precisa de Python na máquina. Custo de rodar assim: frações de
centavo para indexar, ~US$ 0,00002 por pergunta. Para custo zero e nada saindo da
máquina, use o setup local do `.env.example`.

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
  Com provedor remoto o p95 é 2,58s e cumpre a meta; com um 7B local, 19,9s.
- O juiz de alucinação é um modelo 7B calibrado contra 6 casos. Suficiente para não
  estar obviamente quebrado, insuficiente para publicar a taxa sem revisão manual.

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

**RAGAS de fato instalado.** Quatro métricas da SPEC continuam como "não medida". Elas
não substituem as duas métricas próprias — que são as que importam num contexto
educacional — mas são a linguagem comum para comparar com outros sistemas RAG.

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
