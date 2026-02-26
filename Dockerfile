# QuantSight Cloud Backend — Optimized Dockerfile
# =================================================
# AUTHORITATIVE SOURCE:  backend/
# Vanguard module lives at backend/vanguard/ (deployed) and vanguard/ (dev mirror).
# ALWAYS edit backend/vanguard/ for production changes, or run sync script.
# Both copies are included here as belt-and-suspenders; backend/ wins on conflict.

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

# Copy all application source
# 1. Root-level vanguard/ (dev mirror) — gives backward compat if edits land here
COPY vanguard/ ./vanguard/
# 2. backend/ (authoritative) — overwrites vanguard/ content if backend/vanguard/ differs
COPY backend/ .

# Expose port (Cloud Run sets $PORT at runtime)
EXPOSE 8080

# Run with Uvicorn (2 workers for Cloud Run single-container)
CMD exec uvicorn main:app --host 0.0.0.0 --port $PORT --workers 2
