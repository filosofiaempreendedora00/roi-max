#!/usr/bin/env bash
# Backtest sem gastar um único crédito de API.
set -euo pipefail
cd "$(dirname "$0")/../backend"
exec ../.venv/bin/python -m roimax.backtest "$@"
