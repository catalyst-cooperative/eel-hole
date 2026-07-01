#!/bin/sh
set -eux

echo "Starting PR preview startup script..."
echo "whoami=$(whoami)"
echo "pwd=$(pwd)"
echo "PORT=${PORT:-unset}"
ls -la /app
ls -la /app/deployment

echo "Running database migrations..."
uv run --no-dev flask --app eel_hole db upgrade

echo "Starting Flask app on port ${PORT}..."
uv run --no-dev flask --app eel_hole run --host 0.0.0.0 --port "${PORT}"
