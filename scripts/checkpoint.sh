#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MESSAGE="${1:-}"

if [[ -z "$MESSAGE" ]]; then
  echo "Uso: scripts/checkpoint.sh \"mensaje del cambio\""
  exit 2
fi

if ! git -C "$ROOT_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Este proyecto no esta inicializado con Git."
  exit 1
fi

"$ROOT_DIR/scripts/verify.sh"

git -C "$ROOT_DIR" add -A

if git -C "$ROOT_DIR" diff --cached --quiet; then
  echo "No hay cambios para commitear."
  exit 0
fi

git -C "$ROOT_DIR" commit -m "$MESSAGE"
"$ROOT_DIR/scripts/update-version.sh"

echo
echo "Checkpoint creado:"
git -C "$ROOT_DIR" log -1 --oneline --decorate

if git -C "$ROOT_DIR" remote get-url origin >/dev/null 2>&1; then
  echo
  echo "Remote origin detectado. Para respaldar en GitHub:"
  echo "  git push"
else
  echo
  echo "No hay remote origin configurado. Agrega GitHub con:"
  echo "  git remote add origin git@github.com:TU_USUARIO/acsm-control.git"
  echo "  git push -u origin main"
fi
