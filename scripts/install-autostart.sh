#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
NODE_BIN="$(command -v node)"

mkdir -p "$UNIT_DIR"

render_unit() {
  local source="$1"
  local target="$2"

  sed \
    -e "s|@ROOT_DIR@|$ROOT_DIR|g" \
    -e "s|@NODE_BIN@|$NODE_BIN|g" \
    "$source" > "$target"
}

render_unit \
  "$ROOT_DIR/scripts/systemd/acsm-control-api.service.in" \
  "$UNIT_DIR/acsm-control-api.service"
render_unit \
  "$ROOT_DIR/scripts/systemd/acsm-control-web.service.in" \
  "$UNIT_DIR/acsm-control-web.service"

for port in 8001 5173; do
  pids="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    kill $pids 2>/dev/null || true
  fi
done

systemctl --user daemon-reload
systemctl --user enable acsm-control-api.service acsm-control-web.service
systemctl --user restart acsm-control-api.service acsm-control-web.service

echo "Inicio automatico instalado."
systemctl --user --no-pager --full status \
  acsm-control-api.service acsm-control-web.service | sed -n '1,28p'
