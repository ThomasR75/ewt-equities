# Hugging Face Space (Docker SDK) — read-only EWT dashboard
FROM python:3.12-slim
WORKDIR /app

COPY requirements-hosted.txt .
RUN pip install --no-cache-dir -r requirements-hosted.txt

# app code + the precomputed state (assembled at the Space repo root)
COPY ewt ./ewt
COPY calib ./calib
COPY records ./records

ENV EWT_HOSTED=1 \
    PORT=7860 \
    PYTHONUNBUFFERED=1
EXPOSE 7860
# Production WSGI server (2 worker processes, threaded) instead of Flask's dev server
CMD ["gunicorn", "--bind", "0.0.0.0:7860", "--workers", "2", "--threads", "4", \
     "--timeout", "120", "calib.app:app"]
