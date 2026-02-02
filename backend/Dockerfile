# QuantSight Cloud Backend - Dockerfile for Google Cloud Run
# ===========================================================
# Optimized Python 3.11-slim build with shared_core support

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PORT=8080

# Install system dependencies (minimal)
RUN apt-get update && apt-get install -y \
    --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY backend/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Critical: Copy shared_core for math parity with desktop
COPY shared_core /app/shared_core

# Copy backend application code
COPY backend /app

# Create data directory for SQLite (local testing)
RUN mkdir -p /app/data

# Expose port (Cloud Run will override with $PORT)
EXPOSE 8080

# Health check (optional, Cloud Run has built-in checks)
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8080/health', timeout=5)"

# Run with Uvicorn (production ASGI server)
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT} --workers 1 --log-level info
