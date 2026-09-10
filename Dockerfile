FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependências primeiro, para aproveitar o cache de camada
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --upgrade pip && pip install -e .

COPY app/ ./app/
COPY .streamlit/ ./.streamlit/
COPY samples/ ./samples/

EXPOSE 8000 8501

CMD ["uvicorn", "grifo.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
