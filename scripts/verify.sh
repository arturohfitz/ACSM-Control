#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "== Backend: compilacion Python =="
(
  cd "$ROOT_DIR/constructora-api"
  source .venv/bin/activate
  PYTHONPATH=. python -m compileall app
)

echo
echo "== Backend: pruebas unitarias =="
(
  cd "$ROOT_DIR/constructora-api"
  source .venv/bin/activate
  PYTHONPATH=. python -m unittest discover -s tests
)

echo
echo "== Frontend: build =="
(
  cd "$ROOT_DIR/constructora-web"
  npm run build
)

echo
echo "Verificacion completa."
