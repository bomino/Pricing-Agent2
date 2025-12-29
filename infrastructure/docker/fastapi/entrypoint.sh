#!/bin/bash

set -e

echo "=== FastAPI ML Service Production Entrypoint ==="

# Wait for Redis to be ready
echo "Waiting for Redis to be ready..."
until poetry run python -c "import redis; r = redis.from_url('$REDIS_URL'); r.ping()"; do
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

# Download/load ML models if they don't exist
echo "Checking ML models..."
poetry run python -c "
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
timeout 10 poetry run python -c "
import asyncio
from main import app

async def health_check():
    # Basic application startup check
    print('Application structure validated')
    
asyncio.run(health_check())
"

echo "Starting supervisord..."
exec /usr/bin/supervisord -c /etc/supervisord.conf