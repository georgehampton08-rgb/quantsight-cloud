# QuantSight Cloud Backend - Optimized Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install essential system dependencies (git required for GitPython/Vanguard)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies first (for layer caching)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code from backend/ (authoritative source)
COPY backend/ .

# Expose port
EXPOSE 8080

# Run with Uvicorn
CMD exec uvicorn main:app --host 0.0.0.0 --port $PORT --workers 2
