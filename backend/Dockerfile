# KrishiMitra backend (FastAPI + AI models), CPU build.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/trained_models/cache/huggingface

# FFmpeg converts browser recordings for Whisper; libgomp is needed by CTranslate2/ONNX Runtime
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend

# CPU-only PyTorch first (much smaller than the default CUDA build), then the rest
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Run as a non-root user
RUN useradd --create-home --uid 1000 app \
    && mkdir -p /app/storage /app/knowledge_base /app/trained_models \
    && chown -R app:app /app
USER app

ENV STORAGE_DIR=/app/storage \
    CHROMA_DIR=/app/knowledge_base/chroma_db \
    MODELS_DIR=/app/trained_models \
    MODEL_CACHE_DIR=/app/trained_models/cache

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/health || exit 1

# One worker: each worker would load its own copy of the AI models into RAM
CMD ["sh", "-c", "alembic upgrade head && python -m scripts.seed_data && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --proxy-headers --forwarded-allow-ips='*'"]
