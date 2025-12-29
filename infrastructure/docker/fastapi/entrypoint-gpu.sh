#!/bin/bash

set -e

echo "=== FastAPI ML Service GPU Production Entrypoint ==="

# Check GPU availability
echo "Checking GPU availability..."
if command -v nvidia-smi &> /dev/null; then
    echo "GPU Information:"
    nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv
    export USE_GPU=true
else
    echo "No GPU detected, falling back to CPU"
    export USE_GPU=false
fi

# Wait for Redis to be ready
echo "Waiting for Redis to be ready..."
until python -c "import redis; r = redis.from_url('$REDIS_URL'); r.ping()"; do
  echo "Redis is unavailable - sleeping"
  sleep 1
done
echo "Redis is ready!"

# Create necessary directories
echo "Creating directories..."
mkdir -p /app/logs
mkdir -p /app/fastapi_ml/ml_artifacts/models

# Set proper permissions
chown -R mluser:mlgroup /app/logs
chown -R mluser:mlgroup /app/fastapi_ml/ml_artifacts

# Install GPU-specific packages if available
if [ "$USE_GPU" = "true" ]; then
    echo "Installing GPU packages..."
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
fi

# Download/load ML models if they don't exist
echo "Checking ML models..."
python -c "
import os
from pathlib import Path

models_dir = Path('/app/fastapi_ml/ml_artifacts/models')
if not any(models_dir.glob('*')):
    print('No models found. Creating placeholder...')
    (models_dir / '.placeholder').touch()
    print('Placeholder created. Please load actual models.')
else:
    print(f'Found {len(list(models_dir.glob(\"*\")))} model files')
"

# Health check before starting
echo "Running health check..."
timeout 10 python -c "
import asyncio
from main import app

async def health_check():
    # Basic application startup check
    print('Application structure validated')
    
asyncio.run(health_check())
"

# Start with single worker for GPU
echo "Starting ML service with GPU support..."
exec python -m gunicorn main:app -c /app/gunicorn.conf.py --workers 1