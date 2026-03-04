# QuantSight Cloud Backend — Optimized Dockerfile
# =================================================
# AUTHORITATIVE SOURCE: backend/
# The Vanguard module lives exclusively at backend/vanguard/
# Root-level vanguard/ has been deleted. Do NOT recreate it.

FROM python:3.11-slim

WORKDIR /app

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install system dependencies (git required for GitPython / Vanguard context fetcher)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer cache optimization)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code — backend/ is the only source of truth
COPY backend/ .

# Expose port (Cloud Run sets $PORT at runtime)
EXPOSE 8080

# Run with Uvicorn (2 workers for Cloud Run single-container)
CMD exec uvicorn main:app --host 0.0.0.0 --port $PORT --workers 2
