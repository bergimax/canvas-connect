BACKEND_PORT ?= 8000
FRONTEND_PORT ?= 8080

.DEFAULT_GOAL := help
.PHONY: help install backend-install frontend-install dev backend frontend test lint stop

help:
	@echo "make install   - install backend (uv) and frontend (npm) dependencies"
	@echo "make dev       - run backend + frontend together (Ctrl+C stops both)"
	@echo "make backend   - run just the backend on :$(BACKEND_PORT)"
	@echo "make frontend  - run just the frontend on :$(FRONTEND_PORT)"
	@echo "make test      - run backend pytest suite"
	@echo "make lint      - typecheck + lint the frontend"
	@echo "make stop      - kill any backend/frontend dev servers left running"

install: backend-install frontend-install

backend-install:
	cd backend && uv sync

frontend-install:
	cd frontend && npm install

# Backend on :$(BACKEND_PORT), frontend on :$(FRONTEND_PORT); frontend/.env.local
# points VITE_API_BASE_URL at the backend, and the backend's FRONTEND_BASE_URL
# (used for guest links) defaults to the frontend port, so the defaults line up.
dev:
	@trap 'kill 0' EXIT INT TERM; \
	$(MAKE) --no-print-directory backend & \
	$(MAKE) --no-print-directory frontend & \
	wait

backend:
	cd backend && uv run uvicorn app.main:app --reload --port $(BACKEND_PORT)

frontend:
	cd frontend && npm run dev

test:
	cd backend && uv run pytest -q

lint:
	cd frontend && npx tsc --noEmit && npm run lint

stop:
	-pkill -f "uvicorn app.main:app" 2>/dev/null
	-pkill -f "vite dev" 2>/dev/null
	@true
