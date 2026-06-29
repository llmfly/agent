# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DeerFlow is an open-source **super agent harness** by ByteDance that orchestrates sub-agents, memory, and sandboxes — powered by extensible skills. It is a full-stack application: Python backend (LangGraph + FastAPI) + Next.js frontend + nginx reverse proxy.

**For detailed architecture per layer, see:**
- [`backend/CLAUDE.md`](backend/CLAUDE.md) — agent system, middleware chain, sandbox, tools, MCP, memory, config, Gateway API, channels
- [`frontend/CLAUDE.md`](frontend/CLAUDE.md) — Next.js components, thread hooks, streaming, artifacts

## Commands

All commands run from the **repository root** unless specified otherwise.

### Setup & Install

```bash
make setup           # Interactive setup wizard (generates config.yaml + .env)
make doctor          # Check configuration and system requirements
make check           # Verify required tools (node, pnpm, uv, nginx)
make install         # Install all dependencies (backend + frontend + pre-commit hooks)
make config          # Generate config files (aborts if config.yaml already exists)
make config-upgrade  # Merge new fields from config.example.yaml into config.yaml
```

### Development

```bash
make dev             # Start all services locally (hot-reload, http://localhost:2026)
make dev-daemon      # Start dev services in background
make start           # Start in production mode (optimized, no hot-reload)
make start-daemon    # Start prod services in background
make stop            # Stop all running services
make clean           # Stop + remove temp files
```

### Docker

```bash
make docker-init     # Pull sandbox image and prepare Docker prerequisites
make docker-start    # Start Docker services (mode-aware per config.yaml sandbox.use)
make docker-stop     # Stop Docker services
make up              # Production Docker (build + start)
make down            # Stop production Docker
```

### Backend (from `backend/`)

```bash
cd backend
make install         # uv sync
make dev             # Gateway API with reload (port 8001)
make gateway         # Gateway API without reload (port 8001)
make lint            # ruff check + format check
make format          # ruff auto-fix + format
make test            # Run all tests
make test-blocking-io # Strict blocking-IO runtime gate tests
```

### Frontend (from `frontend/`)

```bash
cd frontend
pnpm dev             # Dev server with Turbopack (port 3000)
pnpm lint            # ESLint
pnpm lint:fix        # ESLint with auto-fix
pnpm typecheck       # tsc --noEmit
pnpm test            # Unit tests (Vitest)
pnpm test:e2e        # E2E tests (Playwright, Chromium)
pnpm build           # Production build (set BETTER_AUTH_SECRET first)
```

### Pre-Checkin Validation

Run before submitting changes:
```bash
cd backend && make lint && make test
cd frontend && pnpm lint && pnpm typecheck
```

## High-Level Architecture

```
Browser ──▶ nginx (:2026) ──▶ Frontend Next.js (:3000)
                    │
                    └──▶ Gateway FastAPI (:8001)
                              │
                              ├──▶ LangGraph Agent Runtime (in-process)
                              │       ├── Lead Agent (make_lead_agent)
                              │       ├── Subagents (general-purpose, bash)
                              │       ├── Sandbox (local or Docker)
                              │       ├── Tools (built-in, MCP, community)
                              │       ├── Skills (public/ + custom/)
                              │       └── Memory (per-user, LLM-extracted)
                              │
                              ├──▶ REST API (/api/models, /api/mcp, /api/skills, ...)
                              │
                              └──▶ IM Channels (Feishu, Slack, Telegram, DingTalk)
```

### Harness / App Split (backend)

The backend enforces a strict dependency direction:

- **Harness** (`backend/packages/harness/deerflow/`): Publishable framework package `deerflow-harness` imported as `deerflow.*`. Contains all agent logic, tools, sandbox, models, MCP, skills, config.
- **App** (`backend/app/`): Application layer imported as `app.*`. Contains the FastAPI Gateway and IM channel integrations.

**Rule**: `app` imports `deerflow`, but `deerflow` never imports `app`. Enforced by `backend/tests/test_harness_boundary.py` in CI.

### Configuration

- **`config.yaml`** (root): Models, tools, sandbox, memory, channels (copied from `config.example.yaml`)
- **`.env`** (root): API keys and secrets referenced via `$VAR` in config.yaml
- **`extensions_config.json`** (root): MCP server and skill configurations

Configuration priority for both files: explicit path arg → `DEER_FLOW_CONFIG_PATH` env var → `./config.yaml` (backend dir) → `../config.yaml` (project root, recommended).

Hot-reload: per-run config fields (models, tools, summarization, memory params) reload on config.yaml mtime change. Infrastructure fields (database, sandbox provider, channels) are restart-required.

### Nginx Routing (local dev)

- `/api/langgraph/*` → Gateway embedded runtime (:8001), rewritten to `/api/*`
- `/api/*` (other) → Gateway REST API (:8001)
- Everything else → Frontend (:3000)

Local services: LangGraph (2024), Gateway (8001), Frontend (3000), nginx (2026).

## Key Non-Obvious Details

- **`make dev`** starts four services. If interrupted, run `make stop` to ensure cleanup.
- **`make config`** is non-idempotent — it aborts if `config.yaml` exists. Use `make config-upgrade` to merge new fields.
- **Frontend build** requires `BETTER_AUTH_SECRET` env var (or `SKIP_ENV_VALIDATION=1`).
- **Proxy env vars** (`HTTP_PROXY`, etc.) can break `pnpm install` — unset them if frontend installation fails.
- **`pnpm check`** may fail due to `next lint` incompatibility — run `pnpm lint` and `pnpm typecheck` separately instead.
- **Python 3.12+** and **Node.js 22+** are required. Package managers: `uv` (Python) and `pnpm@10.26.2` (frontend).
- **Line length**: 240 chars for backend Python (ruff config).
- **`is_local_sandbox()`** matches both `sandbox_id == "local"` (legacy singleton) and `sandbox_id.startswith("local:")` (per-thread).

## Repo Layout (key paths)

```
deer-flow/
├── Makefile                       # Root commands
├── config.example.yaml            # Full config template (copy to config.yaml)
├── extensions_config.example.json # MCP + skills template
├── backend/
│   ├── Makefile                   # Backend commands
│   ├── pyproject.toml             # Python deps, uv workspace
│   ├── langgraph.json             # Graph entry: deerflow.agents:make_lead_agent
│   ├── ruff.toml                  # Lint/format config
│   ├── packages/harness/deerflow/ # Core agent framework (deerflow-harness)
│   ├── app/gateway/               # FastAPI Gateway
│   ├── app/channels/              # IM platform integrations
│   └── tests/                     # Backend test suite
├── frontend/
│   ├── Makefile                   # Frontend commands
│   ├── src/app/                   # Next.js App Router
│   ├── src/core/                  # Business logic (threads, API, artifacts, skills, mcp)
│   ├── src/components/            # React components
│   └── tests/                     # unit/ and e2e/ test directories
├── docker/                        # Docker Compose configs + nginx config
├── skills/                        # Agent skills (public/ committed, custom/ gitignored)
├── scripts/                       # Setup, serve, deploy, doctor, etc.
└── docs/                          # Feature documentation
```

## CI

Key workflows in `.github/workflows/`:
- **backend-unit-tests.yml** — runs `make lint` + `make test` on PRs, Python 3.12
- **backend-blocking-io-tests.yml** — strict Blockbuster gate, hard-fail
- **frontend-unit-tests.yml** — frontend lint + typecheck + unit tests
- **e2e-tests.yml** — Playwright E2E tests (Chromium)
