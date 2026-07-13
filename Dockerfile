# Cloud Run (or any Docker host) — read-only, password-gated EWT dashboard
FROM python:3.12-slim
WORKDIR /app

COPY requirements-hosted.txt .
RUN pip install --no-cache-dir -r requirements-hosted.txt

# code + the precomputed state (caches/big CSV excluded via .gcloudignore)
COPY ewt ./ewt
COPY calib ./calib
COPY records ./records

ENV EWT_HOSTED=1 \
    PORT=8080 \
    PYTHONUNBUFFERED=1
EXPOSE 8080
# Cloud Run injects $PORT. Shell form expands it; `exec` makes gunicorn PID 1 for clean shutdowns.
CMD exec gunicorn --bind 0.0.0.0:${PORT} --workers 1 --threads 8 --timeout 120 calib.app:app
