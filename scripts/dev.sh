#!/usr/bin/env bash
# Desenvolvimento: backend com reload + Vite com HMR, os dois na rede local.
set -euo pipefail
cd "$(dirname "$0")/.."

./.venv/bin/python -m uvicorn roimax.main:app --reload --host 0.0.0.0 --port 8000 --app-dir backend &
BACK=$!
trap 'kill $BACK 2>/dev/null || true' EXIT
(cd web && npm run dev -- --host)
