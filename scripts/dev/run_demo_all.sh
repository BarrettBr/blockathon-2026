#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PIDS=()
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
DEMO_PORT="${DEMO_PORT:-7777}"

start_process() {
  local cmd="$1"
  setsid bash -lc "$cmd" &
  PIDS+=("$!")
}

cleanup() {
  trap - INT TERM EXIT
  for pid in "${PIDS[@]:-}"; do
    kill -TERM "-$pid" 2>/dev/null || true
    kill -TERM "$pid" 2>/dev/null || true
  done
  sleep 1
  for pid in "${PIDS[@]:-}"; do
    kill -KILL "-$pid" 2>/dev/null || true
    kill -KILL "$pid" 2>/dev/null || true
  done
}

trap cleanup INT TERM EXIT

start_process "cd '$ROOT_DIR/src/backend/api' && ../../../.venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port '$BACKEND_PORT'"
start_process "cd '$ROOT_DIR/src/frontend' && npm run dev -- --host 0.0.0.0 --port '$FRONTEND_PORT'"
start_process "cd '$ROOT_DIR/src/demo/novabeat' && NOVA_DEMO_PORT='$DEMO_PORT' EQUIPAY_BASE_URL=http://127.0.0.1:'$BACKEND_PORT'/api/v1 python3 server.py"

wait -n "${PIDS[@]}"
