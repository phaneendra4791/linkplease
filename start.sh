#!/bin/sh

set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting Celery..."
celery -A app.workers.celery_app worker --loglevel=info --concurrency=4 &

echo "Starting FastAPI..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}