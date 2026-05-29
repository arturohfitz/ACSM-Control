#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_LOG="$ROOT_DIR/.runtime-api.log"
WEB_LOG="$ROOT_DIR/.runtime-web.log"
API_PID="$ROOT_DIR/.runtime-api.pid"
WEB_PID="$ROOT_DIR/.runtime-web.pid"

"$ROOT_DIR/scripts/update-version.sh"

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

stop_port 8000
stop_port 5173

echo "Levantando API desde $ROOT_DIR/constructora-api"
setsid bash -lc "cd '$ROOT_DIR/constructora-api' && source .venv/bin/activate && PYTHONPATH=. exec uvicorn app.main:app --reload --host 127.0.0.1 --port 8000" >"$API_LOG" 2>&1 &
echo $! > "$API_PID"

echo "Levantando Web desde $ROOT_DIR/constructora-web"
setsid bash -lc "cd '$ROOT_DIR/constructora-web' && exec npm run dev -- --host 127.0.0.1 --port 5173" >"$WEB_LOG" 2>&1 &
echo $! > "$WEB_PID"

echo "Esperando servicios..."
for _ in {1..30}; do
  api_code="$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/health || true)"
  web_code="$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:5173/ || true)"
  if [[ "$api_code" == "200" && "$web_code" == "200" ]]; then
    echo "API: http://127.0.0.1:8000"
    echo "Web: http://127.0.0.1:5173"
    echo "Version:"
    sed -n '1,8p' "$ROOT_DIR/constructora-web/src/config/buildInfo.ts"
    exit 0
  fi
  sleep 1
done

echo "No se pudo confirmar el arranque."
echo "API log: $API_LOG"
echo "Web log: $WEB_LOG"
exit 1
