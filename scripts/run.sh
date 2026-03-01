#!/usr/bin/env bash
# Start DjwalaAI server
set -e
cd "$(dirname "$0")/.."
source .venv/bin/activate 2>/dev/null || true
echo "Starting DjwalaAI on http://localhost:8000"
echo "Open http://localhost:8000/static/index.html"
uvicorn djwala.main:app --reload --port 8000
