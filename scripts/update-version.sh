#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_FILE="$ROOT_DIR/constructora-web/src/config/buildInfo.ts"

if git -C "$ROOT_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1 &&
  git -C "$ROOT_DIR" rev-parse --short HEAD >/dev/null 2>&1; then
  COMMIT="$(git -C "$ROOT_DIR" rev-parse --short HEAD)"
  BRANCH="$(git -C "$ROOT_DIR" branch --show-current 2>/dev/null || true)"
  DIRTY="false"
  if ! git -C "$ROOT_DIR" diff --quiet || ! git -C "$ROOT_DIR" diff --cached --quiet; then
    DIRTY="true"
  fi
else
  COMMIT="sin-git"
  BRANCH="sin-rama"
  DIRTY="true"
fi

UPDATED_AT="$(date '+%Y-%m-%d %H:%M:%S %Z')"

cat > "$OUT_FILE" <<EOF_VERSION
export const buildInfo = {
  version: '${COMMIT}',
  branch: '${BRANCH:-local}',
  dirty: ${DIRTY},
  updatedAt: '${UPDATED_AT}',
}
EOF_VERSION

echo "Version actualizada: ${COMMIT}${DIRTY:+ dirty=${DIRTY}} (${UPDATED_AT})"
