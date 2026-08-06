#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_LOG="$ROOT_DIR/.runtime-api.log"
WEB_LOG="$ROOT_DIR/.runtime-web.log"
API_PID="$ROOT_DIR/.runtime-api.pid"
WEB_PID="$ROOT_DIR/.runtime-web.pid"
API_PORT=8001
POSTGRES_CONTAINER=acsm-control-postgres

"$ROOT_DIR/scripts/update-version.sh"

if docker inspect "$POSTGRES_CONTAINER" >/dev/null 2>&1; then
  docker start "$POSTGRES_CONTAINER" >/dev/null
  for _ in {1..30}; do
    if docker exec "$POSTGRES_CONTAINER" pg_isready -U constructora -d constructora_db >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
fi

wait_for_services() {
  for _ in {1..30}; do
    api_code="$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:$API_PORT/health || true)"
    web_code="$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:5173/ || true)"
    if [[ "$api_code" == "200" && "$web_code" == "200" ]]; then
      return 0
    fi
    sleep 1
  done
  return 1
}

show_services() {
  echo "API: http://127.0.0.1:$API_PORT"
  echo "Web: http://127.0.0.1:5173"
  echo "Version:"
  sed -n '1,8p' "$ROOT_DIR/constructora-web/src/config/buildInfo.ts"
}

if systemctl --user cat acsm-control-api.service acsm-control-web.service >/dev/null 2>&1; then
  echo "Reiniciando servicios de usuario ACSM Control"
  systemctl --user restart acsm-control-api.service acsm-control-web.service
  if wait_for_services; then
    show_services
    exit 0
  fi
  systemctl --user --no-pager --full status acsm-control-api.service acsm-control-web.service || true
  exit 1
fi

stop_port() {
  local port="$1"
  local pids
  pids="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    echo "Deteniendo procesos en puerto $port: $pids"
    kill $pids 2>/dev/null || true
    sleep 1
  fi
}

stop_port "$API_PORT"
stop_port 5173

echo "Levantando API desde $ROOT_DIR/constructora-api"
setsid bash -lc "cd '$ROOT_DIR/constructora-api' && source .venv/bin/activate && PYTHONPATH=. exec uvicorn app.main:app --reload --host 127.0.0.1 --port $API_PORT" >"$API_LOG" 2>&1 &
echo $! > "$API_PID"

echo "Levantando Web desde $ROOT_DIR/constructora-web"
setsid bash -lc "cd '$ROOT_DIR/constructora-web' && exec npm run dev -- --host 127.0.0.1 --port 5173" >"$WEB_LOG" 2>&1 &
echo $! > "$WEB_PID"

echo "Esperando servicios..."
if wait_for_services; then
  show_services
  exit 0
fi

echo "No se pudo confirmar el arranque."
echo "API log: $API_LOG"
echo "Web log: $WEB_LOG"
exit 1
