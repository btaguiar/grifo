FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1     PYTHONDONTWRITEBYTECODE=1     PIP_NO_CACHE_DIR=1     PORT=8000

WORKDIR /app

# Dependências primeiro, para aproveitar o cache de camada. Sem o extra `local`: ele
# arrasta torch (526MB) e transformers (113MB), e em produção o embedding é remoto e o
# reranker está desligado por medição (EVALUATION.md 4.4). Medido: 559MB com esta
# instalação, 2,5GB com o extra.
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --upgrade pip && pip install -e .

COPY samples/ ./samples/

EXPOSE 8000

# Forma de shell para `$PORT` ser expandida: o Cloud Run injeta a porta em que o
# container PRECISA escutar (8080), e um valor fixo aqui faz o deploy falhar no health
# check sem dizer por quê. `--proxy-headers` porque há um proxy com TLS na frente.
CMD exec uvicorn grifo.api.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers
