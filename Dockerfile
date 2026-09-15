FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AML_DB_PATH=/data/memory.db \
    AML_EMBED_ENABLED=true \
    AML_EMBED_MODEL=BAAI/bge-small-en-v1.5 \
    AML_EMBED_CONCURRENCY=2 \
    AML_EMBED_BATCH_SIZE=64 \
    AML_MAX_ADD_CHARS=200000 \
    AML_MAX_SEARCH_CHARS=200000 \
    AML_MODEL_CACHE=/models

WORKDIR /app
COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
RUN mkdir -p /models && python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5', cache_dir='/models')"
COPY app ./app

ARG VCS_REF=unknown
LABEL org.opencontainers.image.source="https://github.com/M1IH/agent-memory-challenge" \
      org.opencontainers.image.revision="$VCS_REF"

RUN mkdir -p /data
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
