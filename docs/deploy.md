# Deploy da demo pública

Três peças, três serviços gratuitos. O front é estático, a API é um container e o
índice é gerenciado. Nenhuma delas guarda material do curso: o corpus é reconstruído a
partir dos links (`corpus/aulas-publicas/fontes.json`).

| Peça | Serviço | Custo | Por quê |
|---|---|---|---|
| Front (`web/`) | Vercel | gratuito | casa do Next: build a cada push, preview por PR |
| API (FastAPI) | Hugging Face Spaces (Docker) | gratuito | sem cartão, 16GB de RAM, Dockerfile direto do repo |
| Índice | Qdrant Cloud | gratuito até 1GB | 332 chunks ocupam alguns MB |

**A configuração de produção usa embedding remoto**, e isso não é detalhe de
empacotamento: com embedding local a imagem passa de 2,5GB (torch + transformers); sem eles
ficou em 559MB, medido no build. A troca muda o retrieval, então ela foi medida
([EVALUATION.md 3.7](../EVALUATION.md)) antes de ir ao ar.

---

## 1. Índice no Qdrant Cloud

1. Crie um cluster gratuito em <https://cloud.qdrant.io> e guarde a URL e a chave.
2. Indexe o corpus a partir da sua máquina (a ingestão fala com o cluster remoto):

```bash
python scripts/baixar_aulas.py --transcrever     # reconstrói as transcrições
QDRANT_URL=https://SEU-CLUSTER.qdrant.io:6333 \
QDRANT_API_KEY=... \
QDRANT_COLLECTION=grifo_aulas_publicas \
EMBEDDING_PROVIDER=openai \
EMBEDDING_MODEL=openai/text-embedding-3-small \
OPENAI_API_KEY=... OPENAI_BASE_URL=https://openrouter.ai/api/v1 \
python -m grifo.ingest corpus/aulas-publicas --curso "G4 Business (aulas públicas)"
```

A ingestão confere os vetores gravados e falha alto se algum sair zerado. Vale conferir
uma vez também pelo painel do Qdrant: coleção com 332 pontos e dimensão 1536.

## 2. API no Hugging Face Spaces

1. Crie um Space do tipo **Docker** (visibilidade pública, hardware CPU basic).
2. No Space, aponte para este repositório ou copie `deploy/Dockerfile.hf` como
   `Dockerfile` na raiz do Space, junto de `pyproject.toml`, `README.md` e `src/`.
3. Em **Settings → Variables and secrets**, defina:

| Nome | Tipo | Valor |
|---|---|---|
| `OPENAI_API_KEY` | secret | a chave da OpenRouter |
| `OPENAI_BASE_URL` | variable | `https://openrouter.ai/api/v1` |
| `LLM_MODEL` | variable | `openai/gpt-4o-mini` |
| `EMBEDDING_PROVIDER` | variable | `openai` |
| `EMBEDDING_MODEL` | variable | `openai/text-embedding-3-small` |
| `QDRANT_URL` | variable | a URL do cluster |
| `QDRANT_API_KEY` | secret | a chave do cluster |
| `QDRANT_COLLECTION` | variable | `grifo_aulas_publicas` |
| `CURSO_NOME` | variable | o mesmo valor usado na ingestão |
| `CORS_ORIGINS` | variable | o domínio do front na Vercel |

O `CURSO_NOME` precisa bater com o da ingestão: o retrieval filtra por ele, e um valor
diferente devolve zero resultado para tudo, sem erro nenhum.

4. Confira: `https://SEU-SPACE.hf.space/health` deve responder `{"status":"ok"}`.

**O Space dorme por inatividade.** O primeiro acesso depois da soneca leva alguns
segundos. Para uma demo de portfólio isso é aceitável; se incomodar, o plano pago
mantém acordado.

## 3. Front na Vercel

1. Importe o repositório e aponte **Root Directory** para `web/`.
2. Variáveis de ambiente:

| Nome | Valor |
|---|---|
| `NEXT_PUBLIC_API_URL` | `https://SEU-SPACE.hf.space` |
| `NEXT_PUBLIC_CURSO` | o mesmo `CURSO_NOME` |

3. Depois do primeiro deploy, volte ao Space e ponha o domínio da Vercel em
   `CORS_ORIGINS`. Sem isso o navegador barra o `POST /ask` antes de ele sair da
   máquina do visitante, e a tela erra em silêncio.

---

## Uma armadilha do Windows que custa meia hora

Passar a chave para o container lendo o `.env` com `grep | cut` leva junto o `` do
CRLF. O cabeçalho `Authorization` fica inválido, e o SDK da OpenAI embrulha a falha de
transporte como `APIConnectionError: Connection error` — que parece falta de internet
e não é. Aconteceu aqui: DNS e HTTPS funcionavam de dentro do container, e mesmo assim
toda chamada de embedding falhava. Use `tr -d ''` ao extrair, ou defina a variável
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

As duas últimas são em memória e valem por instância. O Space roda uma instância só,
então basta; num deploy com réplicas isso precisaria de um contador compartilhado.

Uma conta grosseira do custo por visitante, com os números medidos em 3.7: cada pergunta
custa cerca de US$ 0,00026. Mil perguntas por dia dão US$ 0,26. O teto diário existe
para o dia em que não forem mil.
