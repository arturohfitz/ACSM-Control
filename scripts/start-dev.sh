#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

"$ROOT_DIR/scripts/update-version.sh"

echo "API: http://127.0.0.1:8000"
echo "Web: http://127.0.0.1:5173"
echo
echo "Abre dos terminales o usa tu supervisor favorito:"
echo "  cd $ROOT_DIR/constructora-api && source .venv/bin/activate && PYTHONPATH=. uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
echo "  cd $ROOT_DIR/constructora-web && npm run dev -- --host 127.0.0.1 --port 5173"
