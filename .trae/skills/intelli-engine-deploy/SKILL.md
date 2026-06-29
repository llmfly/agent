---
name: "intelli-engine-deploy"
description: "Deploys Intelli Engine to pre/dev bare-metal servers via SSH. Covers full deployment flow, common failures (apt sources, config sync, port conflicts) and fixes. Invoke when user asks to deploy, redeploy, or push to pre/dev environment."
---

# Intelli Engine Deploy

Deploy Intelli Engine to bare-metal servers using the scripted deployment pipeline.

## Environments

| Environment | Host | Config File | Public URL |
|-------------|------|-------------|------------|
| pre (242) | `172.16.0.242` | `deploy/envs/pre.conf` | `http://172.16.0.242:10305` |
| dev | `172.16.18.70` | `deploy/envs/.deploy.conf` | `http://172.16.18.70:2026` |

## Prerequisites

- Python 3.12+ with `paramiko` installed (`pip install paramiko`)
- SSH password access to target host (configured in env config)
- Git branch with committed changes ready to deploy

Branch governance: always branch from `origin/dev-v0.1`, never from `master`.

## Quick Start

### Full deployment (recommended)

```bash
# Deploy to pre (242) environment with runtime install checks
python scripts/deploy_intelli.py --env pre --mode baremetal

# Skip runtime install checks (Python/Node/uv already present)
python scripts/deploy_intelli.py --env pre --mode baremetal --skip-runtime-install

# Dry run — validate config without deploying
python scripts/deploy_intelli.py --env pre --mode baremetal --dry-run

# Deploy to dev environment
python scripts/deploy_intelli.py --env dev --mode baremetal
```

### Containerized deployment

```bash
# For environments with Docker
python scripts/deploy_intelli.py --env pre --mode docker
```

## Config File Resolution

The deploy script resolves configuration in this order:

1. `deploy/envs/<env>.conf`
2. `deploy/envs/<env>.baremetal.conf`
3. `.deploy-<env>.conf`

Example config (`deploy/envs/pre.conf`):

```
DEPLOY_HOST=172.16.0.242
SSH_USER=root
SSH_PASSWORD=admin@001
DEPLOY_DIR=/data/intelli/engine
DEPLOY_LOG_DIR=/data/log/intelli/engine
SERVICE_NAME=intelli-engine
SERVICE_PORT=10305
GATEWAY_WORKERS=4
KILL_PORT_CONFLICTS=true

# Visual asset image generation
VISUAL_ASSET_IMAGE_PROVIDER=external-generate
VISUAL_ASSET_EXTERNAL_IMAGE_URL=http://10.8.5.222:8010/generate
VISUAL_ASSET_IMAGE_TIMEOUT_SECONDS=180

# Starfish data-source sync
STARFISH_API_URL=http://172.16.0.160:25019/dip/data-sources/ai/list/{conversation_id}
```

Config files contain SSH passwords and internal service URLs — they are gitignored and must not be committed.

## Deployment Flow

1. **Archive & upload** — Creates a `.tar.gz` archive of the repo (excluding `node_modules`, `.venv`, `.git`, etc.) and uploads it to `/tmp/` on the target host via SFTP.
2. **Extract** — Extracts the archive to `DEPLOY_DIR`.
3. **Ensure config files** — Copies `config.example.yaml` → `config.yaml`, `.env.example` → `.env` if not present. **Does NOT overwrite existing configs.**
4. **Install backend deps** — Runs `uv sync` in `backend/`.
5. **Build frontend** — Runs `pnpm install && pnpm build` in `frontend/`.
6. **Setup systemd** — Writes/updates systemd service units (`intelli-engine.service`, `intelli-engine-nginx.service`).
7. **Start services** — Restarts systemd services and verifies health endpoints.

## Verification

After deployment, the script checks:

- Gateway health: `GET /api/health` — expects `{"status": "healthy", "service": "deer-flow-gateway"}`
- OpenAPI docs: `GET /api/docs` — expects 200

## Common Failures & Fixes

### 1. Port conflicts

If old nginx or gateway is still listening on the target port, set `KILL_PORT_CONFLICTS=true` in the env config. The script kills listeners on `SERVICE_PORT`, `8005`, and `3001` before starting systemd.

### 2. Missing runtime dependencies

The `--skip-runtime-install` flag skips Python/Node/uv version checks. Use this when the server already has the correct runtimes installed. Without it, the script may fail if it can't detect the runtime versions.

### 3. SSH host key verification

The script uses `paramiko.AutoAddPolicy()` so it automatically accepts unknown host keys.

### 4. Network connectivity

- Ensure the local machine can reach the target host on port 22 (SSH).
- If behind a proxy, unset `HTTP_PROXY`/`HTTPS_PROXY` env vars before running the deploy script.

### 5. Actual systemd unit names differ from config

The `SERVICE_NAME` config (`intelli-engine`) does **not** match the actual systemd unit names created on the remote host. The deploy script creates three separate units:

```
intelli-engine-gateway.service   # The FastAPI gateway
intelli-engine-frontend.service  # The Next.js frontend
intelli-engine-nginx.service     # The nginx reverse proxy
```

When debugging on the remote host, use these exact unit names, not `intelli-engine`:

```bash
systemctl status intelli-engine-gateway
journalctl -u intelli-engine-gateway -n 100 -f
systemctl restart intelli-engine-gateway
```

### 6. `/api/v1/` paths bypass AuthMiddleware — cookie auth doesn't work automatically

**Root cause**: `AuthMiddleware` treats all `/api/v1/` paths as public (`_PUBLIC_PATH_PREFIXES`), so it skips JWT cookie validation and never writes the user into the `ContextVar`. Route handlers calling `get_current_user()` get `None` → 401.

**Fix**: Add a FastAPI `Depends` that reads the JWT cookie directly:

```python
async def _require_user(request: Request) -> AsyncIterator[str]:
    """Resolve the authenticated user from the JWT cookie."""
    from app.gateway.deps import get_current_user_from_request

    user = await get_current_user_from_request(request)
    token = set_current_user(user)
    try:
        yield str(user.id)
    finally:
        reset_current_user(token)
```

Then inject via `user_id: str = Depends(_require_user)` in every route handler. Do **not** call `get_current_user()` from the `ContextVar`.

**Checklist for new v1 routes**:
- Does the route resolve the user from the JWT cookie, not the `ContextVar`?
- Does it follow the same pattern as `get_external_context` (header-based auth for external callers)?

### 7. SQLite `config_json` — dict binding error on create

**Root cause**: `DataSourceRow.config_json` is typed as `JSONB().with_variant(String, "sqlite")`. Under SQLite, the column is a plain `String`, and the ORM does not automatically serialize dicts. Passing a Python dict causes:

```
sqlalchemy.exc.ProgrammingError: Error binding parameter 8: type 'dict' is not supported
```

**Fix — write path**: Detect SQLite and serialize manually:

```python
raw_config = request.config or {}
config_value: dict | str = raw_config
if _is_sqlite():
    config_value = json.dumps(raw_config, ensure_ascii=False)
```

**Fix — read path**: Normalize regardless of storage backend:

```python
def _ensure_config_dict(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw       # Postgres JSONB
    if isinstance(raw, str):
        try:
            return json.loads(raw)  # SQLite String
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}
```

**Checklist for new SQLite-compatible fields**:
- Is any column using `with_variant(String, "sqlite")`? If yes, test both read and write paths under SQLite.
- Does the local dev environment use Postgres while production uses SQLite? The bug only surfaces in production.

### 8. Frontend field names must match backend API response exactly

**Root cause**: The backend `DataSourceResponse` returns `config` and `datasources`, but the frontend expected `config_json` and `data_sources`. This caused:

- `Object.entries(ds.config_json)` → `Cannot convert undefined or null to object` → page crash
- `json.data_sources` → always `undefined` → list page showed empty state

**Fix**: Align frontend types with backend:

| Scope | Backend field | Frontend field (before) | Frontend field (after) |
|-------|--------------|------------------------|----------------------|
| Config | `config` | `config_json` | `config` |
| List key | `datasources` | `data_sources` | `datasources` |

Also add null-safe fallback: `Object.entries(ds.config ?? {})`

**Checklist for new API integrations**:
- Are frontend field names verified against the actual API response (read the Pydantic schema)?
- Is the field in camelCase or snake_case? Backend Pydantic uses snake_case.
- Are `Object.entries()` calls protected with `?? {}`?

## Service Management

SSH into the target host for manual service management:

```bash
ssh root@172.16.0.242

# View service status (note: unit name is intelli-engine-gateway, NOT intelli-engine)
systemctl status intelli-engine-gateway
systemctl status intelli-engine-frontend
systemctl status intelli-engine-nginx

# View logs
journalctl -u intelli-engine-gateway -n 100 -f
journalctl -u intelli-engine-frontend -n 100 -f
journalctl -u intelli-engine-nginx -n 100 -f

# Restart services
systemctl restart intelli-engine-gateway
systemctl restart intelli-engine-frontend
systemctl restart intelli-engine-nginx
```
