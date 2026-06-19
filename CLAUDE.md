# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

SmartSack — production-management platform for a paper-sack manufacturing plant (Politécnico Grancolombiano thesis project). Three coupled capabilities share one backend: a real-time **Digital Twin** (operators/supervisors over WebSockets), an **ML delay-prediction** engine + OEE/KPI dashboard, and a **conversational chatbot** that translates natural-language questions into DB queries via the Claude API.

Everything runs through Docker Compose. There is no host-level dev setup — all commands run inside containers.

## Language convention

Code identifiers and comments are **English**; user-facing UI text, API messages, commit messages, and docstrings are **Spanish**. Match this when editing — don't translate existing Spanish strings to English.

## Commands

All commands assume the stack is up (`docker compose up -d --build`). Access everything through Nginx on port 80.

```bash
# Backend tests (require a migrated + seeded DB — see "Test isolation" below)
docker compose exec backend pytest
docker compose exec backend pytest tests/test_orders.py            # single file
docker compose exec backend pytest tests/test_orders.py::test_name # single test
docker compose exec backend pytest -k "events and not websocket"   # by expression

# Frontend (Vitest + ESLint)
docker compose exec frontend npm run test
docker compose exec frontend npm run lint

# Database migrations (Alembic)
docker compose exec backend alembic upgrade head
docker compose exec backend alembic revision --autogenerate -m "mensaje"

# Seed demo data — REQUIRED before tests/first run (8 machines, 6 months history,
# 24 operators). Test users: admin / supervisor1 / op_tub-01_1 — password smartsack123
docker compose exec backend python -m scripts.seed

# ML — only `train` exists (README mentions evaluate/predict_all; they don't)
docker compose exec backend python -m ml.train          # RandomForest + XGBoost grid search
docker compose exec backend python -m ml.train --quick  # reduced grid

# Reset everything (drops the DB volume)
docker compose down -v
```

Useful URLs: SPA `http://localhost`, API `http://localhost/api`, Swagger `http://localhost/docs`, WebSocket `ws://localhost/ws/`.

## Architecture

Five services on `smartsack_net` (see `docker-compose.yml`): `postgres` (16), `redis` (machine-state cache), `backend` (FastAPI), `frontend` (Vite dev server), `nginx`. **Nginx is the single entry point** (`nginx/nginx.conf`): `/api/` → backend (prefix preserved), `/ws/` → backend WebSockets, `/docs` `/redoc` `/openapi.json` → backend, everything else → frontend. The backend mounts every REST router under an `/api` prefix in `app/main.py`, so internal paths and proxied paths match.

### Backend (`backend/app/`)

Layered FastAPI app. Standard request flow: `routers/` (HTTP + auth deps) → `services/` (business logic) → `models/` (SQLAlchemy ORM) ← `schemas/` (Pydantic I/O). `config.py` exposes a single validated `settings` object (Pydantic Settings from `.env`) — never read `os.environ` directly. `database.py` provides the shared engine and the `get_db` per-request session dependency.

Auth is JWT (`middleware/auth.py`): `get_current_user` decodes the Bearer token and reloads the user; `require_roles(*roles)` is the dependency factory for role gating. Three roles: `operario`, `supervisor`, `admin`.

### Two data sources feed the same DB

1. **Batch ETL** (`services/etl_service.py`, `POST /api/etl/upload`): CSVs exported from the ERP (production_orders, confirmations, materials, shipments) parsed with Pandas, validated, inserted with an error log. Sample CSVs live in `backend/samples/`.
2. **Real-time capture**: operators POST events (stops, format changes, incidents, order completion) over REST; these propagate to supervisors via WebSockets.

### Digital Twin WebSocket (`app/websocket/manager.py`)

`ConnectionManager.broadcast` filters by the `machine_id` found *inside* each message payload: supervisors/admins get all plant traffic; an operator receives only messages for their assigned `machine_id`. Messages with no machine target (e.g. initial snapshots) go only to the original requester, not broadcast.

### Chatbot (`services/chat_service.py`, `chat/tools.py`)

Two modes, transparent to the frontend. **LLM mode** (valid `ANTHROPIC_API_KEY`): LangChain + `ChatAnthropic` function-calling — the model picks a tool, the backend runs it against the DB, the model writes the Spanish answer. **Fallback mode** (no key / LLM error): keyword heuristic router mapping the question to a tool with a pre-formatted response — keeps demos working without credentials. Conversation is **stateless**: the frontend sends full `history` each call; tool-calling is capped at `MAX_TOOL_ITERATIONS = 4`. Tools in `chat/tools.py` each take a `Session` + typed args and return JSON-serializable dicts; their `TOOL_SCHEMAS` are shared by both modes.

### Frontend (`frontend/src/`)

React 18 + Vite + Tailwind + Recharts SPA. `App.jsx` defines role-gated routes wrapped in `AuthContext` / `ProtectedRoute` (`/operator` → operario, `/supervisor` → supervisor+admin, `/admin` → admin, `/dashboard` `/chat` → any authenticated). `api/client.js` is the shared axios instance; per-domain modules in `api/` mirror the backend routers. `VITE_API_BASE_URL=/api` and `VITE_WS_BASE_URL=/ws` route through Nginx.

## Test isolation (important)

`backend/tests/conftest.py` does **not** spin up a throwaway DB. Each test opens a real connection to the shared PostgreSQL, wraps the test in a transaction, and **rolls back** at teardown; FastAPI's `get_db` is overridden to use that same transactional session. Consequences:
- The DB **must already be migrated and seeded** — tests assume seed users and the 8-machine catalog exist (`SEED_MACHINE_CODES`).
- Tests assert the seed entities are *present*, not that they're the only rows, so runtime-added data won't break them.
- The `TestClient` hits the app directly (no Nginx), so test URLs are `/api/...`.
