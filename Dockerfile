# KlinkPPI in one container: the built web app at / and the API at /api.
#
# Needs a KlinkPPI clone with embedding_FW/ cloned next to the code (see README).
# Data/ is NOT baked into the image; it is mounted at run time so the
# interaction databases, model weights and saved results live on the host.
#
#   docker build -t klinkppi .
#   docker run -d --name klinkppi -p 8000:8000 -v "$PWD/Data:/app/Data" klinkppi
#   open http://localhost:8000
#
# First run on an empty Data/ folder (downloads databases; --models also the
# embedding weights):
#   docker run --rm -v "$PWD/Data:/app/Data" klinkppi python scripts/prepare_server.py --models
#
# GPU build (needs the NVIDIA container toolkit, run with --gpus all):
#   docker build -t klinkppi:gpu --build-arg TORCH_INDEX=https://download.pytorch.org/whl/cu128 .
#
# Behind HTTPS (deploy/nginx-klinkppi.conf), publish only on localhost and let
# the proxy terminate TLS:
#   docker run -d -p 127.0.0.1:8000:8000 -e FORWARDED_ALLOW_IPS='*' \
#     -e KLINKPPI_PUBLIC_API_URL=https://<host>/api -v /srv/klinkppi/Data:/app/Data klinkppi
#
# All KLINKPPI_* settings from deploy/README.md can be passed with -e.

# ---------- Stage 1: build the web app ----------
FROM node:22-slim AS frontend
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------- Stage 2: Python runtime ----------
FROM python:3.12-slim

# CPU-only PyTorch by default (about 1 GB instead of 5+ GB with CUDA).
ARG TORCH_INDEX=https://download.pytorch.org/whl/cpu
ARG UID=1000

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Model weights go into the mounted Data/ folder, so they are downloaded once.
    HF_HOME=/app/Data/model_cache/huggingface \
    TORCH_HOME=/app/Data/model_cache/torch \
    HOST=0.0.0.0 \
    PORT=8000 \
    FORWARDED_ALLOW_IPS=127.0.0.1

WORKDIR /app

# Dependencies first so code changes do not reinstall PyTorch.
COPY requirements.txt ./
COPY embedding_FW/ ./embedding_FW/
RUN pip install --index-url "$TORCH_INDEX" "torch>=2.11,<2.12" \
 && pip install -r requirements.txt

COPY backend/ ./backend/
COPY scripts/ ./scripts/
COPY Supported_Organisms/ ./Supported_Organisms/
COPY klinkppi.py klinkppi_template.py klinkppi_network.py ./
COPY --from=frontend /src/frontend/dist ./frontend/dist

RUN useradd --uid "$UID" --create-home klinkppi \
 && mkdir -p /app/Data \
 && chown -R klinkppi /app/Data
USER klinkppi

VOLUME ["/app/Data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/api/health', timeout=5)"

# One worker on purpose: jobs run in-process and are persisted in Data/jobs.
CMD ["sh", "-c", "cd /app/backend && exec python -m uvicorn app.server:application --host \"$HOST\" --port \"$PORT\" --workers 1 --proxy-headers --forwarded-allow-ips \"$FORWARDED_ALLOW_IPS\""]
