#!/bin/bash

set -e

echo "=== Django Production Entrypoint ==="

# Wait for database to be ready
echo "Waiting for database to be ready..."
while ! poetry run python django_app/manage.py check --database default; do
  echo "Database is unavailable - sleeping"
  sleep 1
done
echo "Database is ready!"

# Wait for Redis to be ready
echo "Waiting for Redis to be ready..."
until poetry run python -c "import redis; r = redis.from_url('$REDIS_URL'); r.ping()"; do
  echo "Redis is unavailable - sleeping"
  sleep 1
done
echo "Redis is ready!"

# Run database migrations
echo "Running database migrations..."
poetry run python django_app/manage.py migrate --noinput

# Create superuser if it doesn't exist
echo "Creating superuser if needed..."
poetry run python django_app/manage.py shell -c "
from django.contrib.auth import get_user_model;
User = get_user_model();
if not User.objects.filter(email='admin@example.com').exists():
    User.objects.create_superuser('admin@example.com', 'admin123');
    print('Superuser created')
else:
    print('Superuser already exists')
"

# Collect static files
echo "Collecting static files..."
poetry run python django_app/manage.py collectstatic --noinput

# Create log directory if it doesn't exist
mkdir -p /app/logs

# Set proper permissions for logs
chown -R appuser:appgroup /app/logs

echo "Starting supervisord..."
exec /usr/bin/supervisord -c /etc/supervisord.conf