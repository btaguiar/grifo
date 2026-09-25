# Deploy da demo pública

Três peças, três serviços. O front é estático, a API é um container e o índice é
gerenciado; os três cabem no uso gratuito de cada plataforma, e o Cloud Run pede cartão
sem cobrar dentro do free tier.

**Uma advertência que vale mais que qualquer recomendação:** plano gratuito muda. Este
guia recomendava Hugging Face Spaces até o Spaces Docker virar recurso pago, em
setembro de 2026. Confira os termos na hora de criar a conta em vez de confiar nesta
tabela. Nenhuma delas guarda material do curso: o corpus é reconstruído a
partir dos links (`corpus/aulas-publicas/fontes.json`).

| Peça | Serviço | Custo | Por quê |
|---|---|---|---|
| Front (`web/`) | Vercel | gratuito | casa do Next: build a cada push, preview por PR |
| API (FastAPI) | Google Cloud Run | free tier cobre a demo | escala a zero, cold start de segundos, a porta vem injetada |
| Índice | Qdrant Cloud | gratuito até 1GB | 332 chunks ocupam alguns MB |

**A configuração de produção usa embedding remoto**, e isso não é detalhe de
empacotamento: com embedding local a imagem passa de 2,5GB (torch + transformers); sem eles
ficou em 559MB, medido no build. A troca muda o retrieval, então ela foi medida
([EVALUATION.md 3.7](../EVALUATION.md)) antes de ir ao ar.

---

## 1. Índice no Qdrant Cloud

1. Crie um cluster gratuito em <https://cloud.qdrant.io> e guarde a URL e a chave.
   A URL do painel funciona como está: o Cloud atende em 443, e a porta `:6333`
   é opcional (testado nas duas formas). A chave aparece uma vez só.
2. Indexe o corpus a partir da sua máquina (a ingestão fala com o cluster remoto):

```bash
python scripts/baixar_aulas.py --transcrever     # reconstrói as transcrições
QDRANT_URL=https://SEU-ID.REGIAO.aws.cloud.qdrant.io \
QDRANT_API_KEY=... \
QDRANT_COLLECTION=grifo_aulas_publicas \
EMBEDDING_PROVIDER=openai \
EMBEDDING_MODEL=openai/text-embedding-3-small \
OPENAI_API_KEY=... OPENAI_BASE_URL=https://openrouter.ai/api/v1 \
python -m grifo.ingest corpus/aulas-publicas --curso "G4 Business (aulas públicas)"
```

A ingestão confere os vetores gravados e falha alto se algum sair zerado, e cria o
índice de payload do campo que a busca filtra. Vale conferir uma vez pelo painel do
Qdrant: coleção com 332 pontos, dimensão 1536 e um índice em `metadata.curso`.

**Por que o índice importa.** O Qdrant local aceita filtrar um campo sem índice; o
Qdrant Cloud recusa com `400 Bad request: Index required but not found for
"metadata.curso"`. O erro só aparece na primeira consulta, com a ingestão já terminada
limpa. Coleção criada antes dessa correção se conserta rodando a ingestão de novo.

## 2. API no Cloud Run

A imagem tem 559MB e a API usa 161MiB de memória em uso (medido no container), então o
menor tamanho de instância serve.

```bash
gcloud run deploy grifo-api   --source .   --region southamerica-east1   --allow-unauthenticated   --memory 512Mi   --set-env-vars "OPENAI_BASE_URL=https://openrouter.ai/api/v1,LLM_MODEL=openai/gpt-4o-mini,EMBEDDING_PROVIDER=openai,EMBEDDING_MODEL=openai/text-embedding-3-small,QDRANT_URL=https://SEU-ID.REGIAO.aws.cloud.qdrant.io,QDRANT_COLLECTION=grifo_aulas_publicas,CURSO_NOME=G4 Business (aulas públicas),RATE_LIMIT_POR_MINUTO=6,RATE_LIMIT_DIARIO=300"   --set-secrets "OPENAI_API_KEY=grifo-openai:latest,QDRANT_API_KEY=grifo-qdrant:latest"
```

Os dois segredos entram no Secret Manager antes, uma vez:

```bash
printf '%s' "sua-chave-openrouter" | gcloud secrets create grifo-openai --data-file=-
printf '%s' "sua-chave-qdrant"    | gcloud secrets create grifo-qdrant --data-file=-
```

`printf` em vez de `echo` de propósito: o `echo` acrescenta uma quebra de linha, e a
chave com `
` no fim vira cabeçalho `Authorization` inválido. O SDK relata isso como
`APIConnectionError: Connection error`, que parece falta de internet e não é.

**O `Dockerfile` da raiz já serve os dois casos.** Ele escuta em `$PORT`, que o Cloud
Run injeta (8080) e o compose local não define (fica em 8000). Porta fixa aqui faz o
deploy falhar no health check sem dizer por quê.

Confira: `curl https://SEU-SERVICO.run.app/health` deve responder `{"status":"ok"}`.

## 3. Front na Vercel

1. Importe o repositório e aponte **Root Directory** para `web/`.
2. Variáveis de ambiente:

| Nome | Valor |
|---|---|
| `NEXT_PUBLIC_API_URL` | `https://SEU-SERVICO.run.app` |
| `NEXT_PUBLIC_CURSO` | o mesmo `CURSO_NOME` |

3. Depois do primeiro deploy, volte ao Cloud Run e ponha o domínio da Vercel em
   `CORS_ORIGINS`. Sem isso o navegador barra o `POST /ask` antes de ele sair da
   máquina do visitante, e a tela erra em silêncio.

---

## Uma armadilha do Windows que custa meia hora

Passar a chave para o container lendo o `.env` com `grep | cut` leva junto o `
` do
CRLF. O cabeçalho `Authorization` fica inválido, e o SDK da OpenAI embrulha a falha de
transporte como `APIConnectionError: Connection error` — que parece falta de internet
e não é. Aconteceu aqui: DNS e HTTPS funcionavam de dentro do container, e mesmo assim
toda chamada de embedding falhava. Use `tr -d '
'` ao extrair, ou defina a variável
direto no painel do serviço, que é o caminho normal em produção.

## O risco que vale mais atenção que o deploy

**Cada visitante gasta token do seu bolso.** Um robô batendo no `/ask` queima crédito
enquanto você dorme. Três travas, em ordem de importância:

1. **Limite de crédito na OpenRouter.** É a única que não depende do seu código estar
   certo. Defina um teto mensal baixo na conta.
2. **Limite por IP na API** (`RATE_LIMIT_POR_MINUTO`, padrão 6). Segura o acesso
   repetido sem atrapalhar quem está usando de verdade.
3. **Teto diário global** (`RATE_LIMIT_DIARIO`, padrão 300 perguntas). Quando estoura,
   a API responde 429 até o dia seguinte, e a conta para de crescer.

As duas últimas são em memória e valem por instância. Com `--max-instances 1` no Cloud
Run a conta fecha; acima disso cada réplica teria o próprio contador, e o teto real
seria o dobro, o triplo. Um contador compartilhado exigiria Redis, e fingir que
funciona sem ele seria pior que não ter.

Uma conta grosseira do custo por visitante, com os números medidos em 3.7: cada pergunta
custa cerca de US$ 0,00026. Mil perguntas por dia dão US$ 0,26. O teto diário existe
para o dia em que não forem mil.
