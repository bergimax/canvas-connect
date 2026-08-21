#!/usr/bin/env bash
# Runs backend + frontend together. Ctrl+C stops both.
# First time here? Install deps first:
#   (cd backend && uv sync) && (cd frontend && npm install)
set -euo pipefail

BACKEND_PORT="${BACKEND_PORT:-8000}"
# Frontend runs on :8080 (set by the shared vite config); frontend/.env.local
# points VITE_API_BASE_URL at the backend port above.

cd "$(dirname "${BASH_SOURCE[0]}")"

cleanup() {
  trap - EXIT INT TERM
  kill 0
}
trap cleanup EXIT INT TERM

(cd backend && uv run uvicorn app.main:app --reload --port "$BACKEND_PORT") &
(cd frontend && npm run dev) &

wait
