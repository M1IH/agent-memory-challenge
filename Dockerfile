FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea

WORKDIR /app
COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
RUN mkdir -p /models && python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5', cache_dir='/models')"

ARG AML_EMBED_MODEL_REVISION=52398278842ec682c6f32300af41344b1c0b0bb2
ARG AML_EMBED_MODEL_SHA256=51f1bd0addd6e859e42c2c8021a5e5461385bb676a649f4b269aa445449f2431
ARG AML_EMBED_TOKENIZER_SHA256=d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66
RUN test "$(cat /models/models--qdrant--bge-small-en-v1.5-onnx-q/refs/main)" = "$AML_EMBED_MODEL_REVISION" \
    && echo "$AML_EMBED_MODEL_SHA256  /models/models--qdrant--bge-small-en-v1.5-onnx-q/snapshots/$AML_EMBED_MODEL_REVISION/model_optimized.onnx" | sha256sum -c - \
    && echo "$AML_EMBED_TOKENIZER_SHA256  /models/models--qdrant--bge-small-en-v1.5-onnx-q/snapshots/$AML_EMBED_MODEL_REVISION/tokenizer.json" | sha256sum -c -
COPY app ./app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AML_DB_PATH=/data/memory.db \
    AML_EMBED_ENABLED=true \
    AML_EMBED_MODEL=BAAI/bge-small-en-v1.5 \
    AML_EMBED_MODEL_REVISION=$AML_EMBED_MODEL_REVISION \
    AML_EMBED_MODEL_SHA256=$AML_EMBED_MODEL_SHA256 \
    AML_EMBED_TOKENIZER_SHA256=$AML_EMBED_TOKENIZER_SHA256 \
    AML_EMBED_CONCURRENCY=2 \
    AML_EMBED_BATCH_SIZE=64 \
    AML_MAX_ADD_CHARS=200000 \
    AML_MAX_SEARCH_CHARS=200000 \
    AML_MODEL_CACHE=/models

ARG VCS_REF=unknown
LABEL org.opencontainers.image.source="https://github.com/M1IH/agent-memory-challenge" \
      org.opencontainers.image.revision="$VCS_REF"

RUN mkdir -p /data
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
