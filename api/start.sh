#!/bin/sh
set -e

echo "Starting API server on 0.0.0.0:8000..."
exec uvicorn api.api_server:app --host 0.0.0.0 --port 8000
