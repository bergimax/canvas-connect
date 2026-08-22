#!/usr/bin/env sh
# Starts the built frontend's Node server as an internal-only process, then
# runs the backend in the foreground — the only port exposed by the
# container. FastAPI serves /v1/* itself and reverse-proxies everything else
# to the frontend (see app/frontend_proxy.py).
set -eu

FRONTEND_SERVER_ENTRY="${FRONTEND_SERVER_ENTRY:-/app/frontend/server/index.mjs}"
export NITRO_PORT="${NITRO_PORT:-3000}"
export NITRO_HOST="${NITRO_HOST:-127.0.0.1}"
export FRONTEND_ORIGIN="${FRONTEND_ORIGIN:-http://${NITRO_HOST}:${NITRO_PORT}}"

node "$FRONTEND_SERVER_ENTRY" &
frontend_pid=$!
trap 'kill "$frontend_pid" 2>/dev/null' EXIT INT TERM

python3 -c "
import socket, sys, time
for _ in range(100):
    try:
        socket.create_connection(('${NITRO_HOST}', ${NITRO_PORT}), timeout=0.2).close()
        sys.exit(0)
    except OSError:
        time.sleep(0.1)
sys.exit(1)
" || { echo 'frontend server failed to start' >&2; exit 1; }

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
