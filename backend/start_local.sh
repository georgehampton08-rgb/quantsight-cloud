#!/bin/bash
# Quick Start Script for Local Testing

echo "🚀 Starting QuantSight Backend Locally..."
echo "=========================================="

# Check if in correct directory
if [ ! -f "main.py" ]; then
    echo "❌ Error: main.py not found. Please run from backend/ directory"
    exit 1
fi

# Check Python version
python_version=$(python --version 2>&1)
echo "✅ $python_version"

# Check dependencies
echo ""
echo "📦 Checking dependencies..."
pip show fastapi uvicorn > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ FastAPI & Uvicorn installed"
else
    echo "❌ Installing FastAPI..."
    pip install fastapi uvicorn python-dotenv
fi

# Set environment
export PORT=8000
export ENV=development

echo ""
echo "🔥 Starting server on http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs (disabled)"
echo "   Health: http://localhost:8000/health"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Start uvicorn
uvicorn main:app --reload --host 0.0.0.0 --port 8000 --log-level info
