#!/usr/bin/env bash
# Sobe o ROI Max em produção local: build da PWA + servidor único.
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f .env ] || { cp .env.example .env; echo "Criei .env — preencha antes de operar."; }

echo "==> build da PWA"
(cd web && npm install --silent && npm run build)

echo "==> servidor em http://0.0.0.0:8000"
echo "    desktop: http://localhost:8000"
echo "    celular: http://$(ipconfig getifaddr en0 2>/dev/null || echo SEU_IP):8000"
exec ./.venv/bin/python -m uvicorn roimax.main:app --host 0.0.0.0 --port 8000 --app-dir backend
