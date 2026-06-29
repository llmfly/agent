# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

DeerFlow is an open-source **super agent harness** by ByteDance that orchestrates sub-agents, memory, and sandboxes — powered by extensible skills. It is a full-stack application: Python backend (LangGraph + FastAPI) + Next.js frontend + nginx reverse proxy.

**For detailed architecture per layer, see:**
- [`backend/AGENTS.md`](backend/AGENTS.md) — agent system, middleware chain, sandbox, tools, MCP, memory, config, Gateway API, channels
- [`frontend/AGENTS.md`](frontend/AGENTS.md) — Next.js components, thread hooks, streaming, artifacts

## Global Branch Governance

This repository has two long-lived remote branches: `master` and `dev-v0.1`.

**Hard rule**: all development work must branch from `dev-v0.1`. Developers and agents must never create task branches from `master`, and must never use `master` as the base branch for feature, fix, deployment, or experiment work.

Before any code edit, commit, push, deployment package, or PR work:

1. Fetch remote branch metadata: `git fetch origin dev-v0.1 master`.
2. Confirm the current branch is not `master`.
3. Confirm the task branch fork point is `origin/dev-v0.1`, not `origin/master`.
4. If no task branch exists yet, create it from `origin/dev-v0.1` only, for example: `git switch -c <developer>/<task-name> origin/dev-v0.1`.
5. If the current branch was created from `master`, stop work and recreate/rebase it onto `dev-v0.1` before making changes.

Suggested gate commands:

```bash
git fetch origin dev-v0.1 master
test "$(git branch --show-current)" != "master"
git merge-base --is-ancestor origin/dev-v0.1 HEAD
```

PRs and reviews must target `dev-v0.1` unless the repository owner explicitly authorizes a release operation. Direct development on `master` is forbidden.

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

### Deployment Runbook

Before any deployment task, read [`docs/DEPLOYMENT_RUNBOOK.md`](docs/DEPLOYMENT_RUNBOOK.md) and use the scripted deployment entrypoints instead of ad hoc SSH commands.

When the user says "deploy to `<env>` with bare-metal deployment" or "部署到 `<env>` 环境，裸部署", default to:

```bash
python scripts/deploy_intelli.py --env <env> --mode baremetal
```

When the user asks for bare-metal deployment and explicitly says to skip runtime installation checks, use:

```bash
python scripts/deploy_intelli.py --env <env> --mode baremetal --skip-runtime-install
```

When the user asks for containerized deployment, use:

```bash
python scripts/deploy_intelli.py --env <env> --mode docker
```

Deployment configs are resolved from `deploy/envs/<env>.conf`, `deploy/envs/<env>.baremetal.conf`, or `.deploy-<env>.conf`. These real config files are intentionally gitignored because they may contain SSH passwords and internal service URLs; only `deploy/envs/*.example.conf` should be committed.

Do not reintroduce the old DeepSeek nginx proxy or `/etc/hosts` pin for `api.deepseek.com` as a default deployment fix. The confirmed stream/running-run root cause was runtime `tiktoken` downloading `cl100k_base`; deployments must rely on the bundled tokenizer cache and `TIKTOKEN_CACHE_DIR` instead.

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
