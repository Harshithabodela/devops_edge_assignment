# Stage 1 — install deps
FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --target /app/deps -r requirements.txt

# Stage 2 — slim runtime
FROM python:3.11-slim
WORKDIR /app
RUN useradd -m appuser

COPY --from=builder /app/deps /app/deps
COPY sensor_service.py dashboard.html ./

USER appuser
ENV PYTHONPATH=/app/deps \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

# Gunicorn: 2 workers match the 2-core CPU; --timeout prevents scrape hangs.
CMD ["/app/deps/bin/gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "2", "--timeout", "30", "--max-requests", "500", "sensor_service:app"]
