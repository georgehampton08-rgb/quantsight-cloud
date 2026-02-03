# QuantSight Cloud Backend - Production Dockerfile
# =================================================
# Full FastAPI deployment with admin routes and database support

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY backend/requirements.txt .

# Install Python dependencies (including SQLAlchemy for PostgreSQL)
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir sqlalchemy psycopg2-binary

# Copy shared_core for math parity with desktop
COPY shared_core /app/shared_core

# Copy backend application code
COPY backend /app

# Create data directory
RUN mkdir -p /app/data

# Environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PORT=8080

EXPOSE 8080

# Run with Uvicorn
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT} --workers 1 --log-level info
