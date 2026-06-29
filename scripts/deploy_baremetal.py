#!/usr/bin/env python3
"""Deploy intelli-engine to a bare-metal host over SSH.

The script is intentionally self-contained so it can run from a Windows
workstation without sshpass/plink. It reads .deploy.conf, uploads a sanitized
source archive, builds the backend/frontend on the host, writes systemd units,
and verifies the public endpoint.
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import posixpath
import shlex
import sys
import tarfile
import time
import tempfile
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_EXCLUDES = (
    ".git",
    ".deploy.conf",
    ".deploy-*.conf",
    ".env",
    "config.yaml",
    "extensions_config.json",
    ".deer-flow",
    "node_modules",
    ".next",
    ".venv",
    "__pycache__",
    "*.pyc",
    "*.pyo",
    ".pytest_cache",
    ".ruff_cache",
    "coverage",
    "logs",
    "log",
    ".deer-flow",
    ".tmp",
    ".worktrees",
    "frontend/test-results",
    "frontend/playwright-report",
    "sandbox_image_cache.tar",
)


@dataclass(frozen=True)
class DeployConfig:
    host: str
    user: str
    password: str
    deploy_dir: str
    log_dir: str
    service_name: str
    service_port: int
    gateway_workers: int
    kill_port_conflicts: bool
    visual_asset_env: dict[str, str]

    @property
    def public_url(self) -> str:
        return f"http://{self.host}:{self.service_port}"


def parse_kv_config(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        for existing_key, existing_value in values.items():
            value = value.replace("${" + existing_key + "}", existing_value)
        values[key] = value
    return values


def load_config(path: Path) -> DeployConfig:
    raw = parse_kv_config(path)
    missing = [key for key in ("DEPLOY_HOST", "SSH_USER", "SSH_PASSWORD", "DEPLOY_DIR") if not raw.get(key)]
    if missing:
        raise SystemExit(f"{path} is missing required keys: {', '.join(missing)}")
    return DeployConfig(
        host=raw["DEPLOY_HOST"],
        user=raw["SSH_USER"],
        password=raw["SSH_PASSWORD"],
        deploy_dir=raw["DEPLOY_DIR"].rstrip("/"),
        log_dir=raw.get("DEPLOY_LOG_DIR", "/data/log/intelli/engine").rstrip("/"),
        service_name=raw.get("SERVICE_NAME", "intelli-engine"),
        service_port=int(raw.get("SERVICE_PORT", "2026")),
        gateway_workers=int(raw.get("GATEWAY_WORKERS", "4")),
        kill_port_conflicts=raw.get("KILL_PORT_CONFLICTS", "true").lower() in {"1", "true", "yes", "on"},
        visual_asset_env={
            key: value
            for key, value in raw.items()
            if key.startswith("VISUAL_ASSET_") and value
        },
    )


def resolve_config_path(config: str | None, env_name: str | None) -> Path:
    if config and env_name:
        raise SystemExit("Use either --config or --env, not both.")
    if env_name:
        candidates = (
            REPO_ROOT / "deploy" / "envs" / f"{env_name}.conf",
            REPO_ROOT / "deploy" / "envs" / f"{env_name}.baremetal.conf",
            REPO_ROOT / f".deploy-{env_name}.conf",
        )
        for candidate in candidates:
            if candidate.exists():
                return candidate.resolve()
        searched = "\n  ".join(str(path) for path in candidates)
        raise SystemExit(f"Deployment env not found: {env_name}\nSearched:\n  {searched}")
    return (REPO_ROOT / (config or ".deploy.conf")).resolve()


def should_exclude(path: Path, root: Path, excludes: tuple[str, ...]) -> bool:
    rel = path.relative_to(root).as_posix()
    parts = rel.split("/")
    for pattern in excludes:
        normalized = pattern.strip("/")
        if not normalized:
            continue
        if fnmatch.fnmatch(rel, normalized) or fnmatch.fnmatch(path.name, normalized):
            return True
        if normalized in parts:
            return True
        if rel.startswith(normalized + "/"):
            return True
    return False


def create_archive(root: Path, excludes: tuple[str, ...]) -> Path:
    fd, archive_name = tempfile.mkstemp(prefix="intelli-engine-", suffix=".tar.gz")
    os.close(fd)
    archive_path = Path(archive_name)
    with tarfile.open(archive_path, "w:gz") as archive:
        for current_root, dirnames, filenames in os.walk(root):
            current_path = Path(current_root)
            dirnames[:] = [
                dirname
                for dirname in dirnames
                if not should_exclude(current_path / dirname, root, excludes)
            ]
            for filename in filenames:
                item = current_path / filename
                if should_exclude(item, root, excludes):
                    continue
                archive.add(item, arcname=item.relative_to(root).as_posix(), recursive=False)
    return archive_path


def q(value: str | int) -> str:
    return shlex.quote(str(value))


def remote_script(config: DeployConfig, remote_archive: str, skip_runtime_install: bool) -> str:
    deploy_dir = q(config.deploy_dir)
    log_dir = q(config.log_dir)
    service_name = q(config.service_name)
    service_port = q(config.service_port)
    gateway_workers = q(config.gateway_workers)
    kill_port_conflicts = "true" if config.kill_port_conflicts else "false"
    remote_archive_q = q(remote_archive)
    gateway_port = 8005
    frontend_port = 3001
    python_version = "3.12.11"
    node_version = "22.20.0"
    runtime_install = "false" if skip_runtime_install else "true"
    visual_asset_env_lines = "\n".join(
        f"  set_line .env {key} {q(value)}"
        for key, value in sorted(config.visual_asset_env.items())
    )

    return f"""#!/usr/bin/env bash
set -euo pipefail

DEPLOY_DIR={deploy_dir}
LOG_DIR={log_dir}
SERVICE_NAME={service_name}
SERVICE_PORT={service_port}
GATEWAY_WORKERS={gateway_workers}
KILL_PORT_CONFLICTS={kill_port_conflicts}
GATEWAY_PORT={gateway_port}
FRONTEND_PORT={frontend_port}
ARCHIVE={remote_archive_q}
PYTHON_VERSION={q(python_version)}
NODE_VERSION={q(node_version)}
INSTALL_RUNTIME={runtime_install}

GATEWAY_SERVICE="${{SERVICE_NAME}}-gateway"
FRONTEND_SERVICE="${{SERVICE_NAME}}-frontend"
NGINX_SERVICE="${{SERVICE_NAME}}-nginx"
PYTHON_BIN="/opt/python-3.12/bin/python3.12"
NODE_BIN="/opt/node22/bin/node"
PNPM_BIN="/opt/node22/bin/pnpm"
UV_BIN="/root/.local/bin/uv"
TIKTOKEN_CACHE_DIR="$DEPLOY_DIR/.deer-flow/tiktoken-cache"
CL100K_CACHE_KEY="9b5ad71b2ce5302211f9c61530b329a4922fc6a4"
CL100K_BUNDLE="$DEPLOY_DIR/scripts/deploy_resources/tiktoken/cl100k_base.tiktoken"
CL100K_URL="https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken"

log() {{
  printf '\\n[%s] %s\\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}}

require_safe_path() {{
  case "$DEPLOY_DIR" in
    /data/*/*) ;;
    *) echo "Refusing unsafe DEPLOY_DIR: $DEPLOY_DIR" >&2; exit 2 ;;
  esac
}}

ensure_line() {{
  local file="$1" key="$2" value="$3"
  touch "$file"
  chmod 600 "$file"
  if ! grep -qE "^${{key}}=" "$file"; then
    printf '%s=%s\\n' "$key" "$value" >> "$file"
  fi
}}

set_line() {{
  local file="$1" key="$2" value="$3"
  touch "$file"
  chmod 600 "$file"
  if grep -qE "^${{key}}=" "$file"; then
    sed -i "s|^${{key}}=.*|${{key}}=${{value}}|" "$file"
  else
    printf '%s=%s\\n' "$key" "$value" >> "$file"
  fi
}}

stop_listeners_on_port() {{
  local port="$1"
  local pids
  pids="$(ss -ltnp 2>/dev/null | sed -n "s/.*:${{port}} .*pid=\\([0-9][0-9]*\\).*/\\1/p" | sort -u | tr '\\n' ' ')"
  if [ -z "$pids" ]; then
    return
  fi
  log "Stopping existing listeners on port $port: $pids"
  kill $pids 2>/dev/null || true
  sleep 2
  pids="$(ss -ltnp 2>/dev/null | sed -n "s/.*:${{port}} .*pid=\\([0-9][0-9]*\\).*/\\1/p" | sort -u | tr '\\n' ' ')"
  if [ -n "$pids" ]; then
    log "Force stopping listeners on port $port: $pids"
    kill -9 $pids 2>/dev/null || true
  fi
}}

export_runtime_env() {{
  set -a
  [ -f "$DEPLOY_DIR/.env" ] && . "$DEPLOY_DIR/.env"
  [ -f /etc/intelli-engine/gateway.env ] && . /etc/intelli-engine/gateway.env
  set +a
  export PATH="/opt/python-3.12/bin:/root/.local/bin:/opt/node22/bin:$PATH"
  export PYTHONPATH="$DEPLOY_DIR/backend:$DEPLOY_DIR/backend/packages/harness"
  export DEER_FLOW_CONFIG_PATH="$DEPLOY_DIR/config.yaml"
  export DEER_FLOW_EXTENSIONS_CONFIG_PATH="$DEPLOY_DIR/extensions_config.json"
  export DEER_FLOW_HOME="$DEPLOY_DIR/.deer-flow"
  export TIKTOKEN_CACHE_DIR="$TIKTOKEN_CACHE_DIR"
}}

generate_secret() {{
  if command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    "$PYTHON_BIN" - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
  elif command -v python3 >/dev/null 2>&1; then
    python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
  else
    openssl rand -hex 48
  fi
}}

install_base_packages() {{
  log "Installing base OS packages"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update || true
  apt-get install -y curl ca-certificates build-essential pkg-config libssl-dev zlib1g-dev \\
    libbz2-dev libreadline-dev libsqlite3-dev libffi-dev liblzma-dev uuid-dev \\
    tar xz-utils git nginx openssl
}}

ensure_python() {{
  if [ -x "$PYTHON_BIN" ]; then
    log "Python already installed: $("$PYTHON_BIN" --version)"
    return
  fi
  log "Installing Python $PYTHON_VERSION under /opt/python-3.12"
  cd /tmp
  curl -fL "https://mirrors.tuna.tsinghua.edu.cn/python/${{PYTHON_VERSION}}/Python-${{PYTHON_VERSION}}.tgz" -o "Python-${{PYTHON_VERSION}}.tgz"
  rm -rf "Python-${{PYTHON_VERSION}}"
  tar -xzf "Python-${{PYTHON_VERSION}}.tgz"
  cd "Python-${{PYTHON_VERSION}}"
  ./configure --prefix=/opt/python-3.12 --enable-optimizations --with-ensurepip=install
  make -j"$(nproc)"
  make install
}}

ensure_node() {{
  if [ -x "$NODE_BIN" ] && "$NODE_BIN" -v | grep -q "^v22\\." && [ -x "$PNPM_BIN" ]; then
    log "Node already installed: $("$NODE_BIN" -v), pnpm: $("$PNPM_BIN" --version)"
    return
  fi
  if ! [ -x "$NODE_BIN" ] || ! "$NODE_BIN" -v | grep -q "^v22\\."; then
    log "Installing Node v$NODE_VERSION under /opt/node22"
    cd /tmp
    local arch
    arch="$(uname -m)"
    case "$arch" in
      x86_64) arch="x64" ;;
      aarch64|arm64) arch="arm64" ;;
      *) echo "Unsupported CPU architecture for Node: $arch" >&2; exit 3 ;;
    esac
    curl -fL "https://npmmirror.com/mirrors/node/v${{NODE_VERSION}}/node-v${{NODE_VERSION}}-linux-${{arch}}.tar.xz" -o node22.tar.xz
    rm -rf /opt/node22
    mkdir -p /opt/node22
    tar -xJf node22.tar.xz -C /opt/node22 --strip-components=1
  fi
  log "Preparing pnpm 10.26.2"
  export PATH="/opt/node22/bin:$PATH"
  export COREPACK_NPM_REGISTRY="https://registry.npmmirror.com"
  /opt/node22/bin/corepack enable
  /opt/node22/bin/corepack prepare pnpm@10.26.2 --activate || /opt/node22/bin/npm install -g pnpm@10.26.2 --registry=https://registry.npmmirror.com
  [ -x "$PNPM_BIN" ] || /opt/node22/bin/npm install -g pnpm@10.26.2 --registry=https://registry.npmmirror.com
  [ -x "$PNPM_BIN" ] || ln -sf "$(command -v pnpm)" "$PNPM_BIN"
}}

ensure_uv() {{
  if [ -x "$UV_BIN" ]; then
    log "uv already installed: $("$UV_BIN" --version)"
    return
  fi
  log "Installing uv"
  curl -LsSf --connect-timeout 15 https://astral.sh/uv/install.sh | sh || "$PYTHON_BIN" -m pip install --user -i https://pypi.tuna.tsinghua.edu.cn/simple uv
}}

deploy_source() {{
  require_safe_path
  log "Stopping existing intelli-engine services"
  systemctl stop "$NGINX_SERVICE" "$FRONTEND_SERVICE" "$GATEWAY_SERVICE" 2>/dev/null || true
  if [ "$KILL_PORT_CONFLICTS" = "true" ]; then
    stop_listeners_on_port "$SERVICE_PORT"
    stop_listeners_on_port "$GATEWAY_PORT"
    stop_listeners_on_port "$FRONTEND_PORT"
  fi

  log "Preparing deploy directories"
  mkdir -p "$DEPLOY_DIR" "$LOG_DIR" "$DEPLOY_DIR/.deer-flow/data" "$DEPLOY_DIR/.deer-flow/backups"
  # Older bare-metal deployments resolved the relative sqlite_dir from the
  # backend working directory, which put the live DB under backend/.deer-flow.
  # Preserve that misplaced DB before backend/ is replaced.
  local misplaced_db="$DEPLOY_DIR/backend/.deer-flow/data/deerflow.db"
  local persistent_db="$DEPLOY_DIR/.deer-flow/data/deerflow.db"
  if [ -f "$misplaced_db" ]; then
    local stamp
    stamp="$(date '+%Y%m%d%H%M%S')"
    cp -a "$misplaced_db" "$DEPLOY_DIR/.deer-flow/backups/deerflow.backend-misplaced.$stamp.db"
    if [ ! -f "$persistent_db" ]; then
      log "Recovering misplaced sqlite DB to persistent .deer-flow"
      cp -a "$misplaced_db" "$persistent_db"
    fi
  fi
  if [ -d "$DEPLOY_DIR" ]; then
    find "$DEPLOY_DIR" -mindepth 1 -maxdepth 1 \\
      ! -name '.env' \\
      ! -name 'config.yaml' \\
      ! -name 'extensions_config.json' \\
      ! -name '.deer-flow' \\
      -exec rm -rf {{}} +
  fi
  tar -xzf "$ARCHIVE" -C "$DEPLOY_DIR"
}}

seed_runtime_config() {{
  log "Ensuring runtime config files"
  cd "$DEPLOY_DIR"
  [ -f config.yaml ] || cp config.example.yaml config.yaml
  [ -f extensions_config.json ] || cp extensions_config.example.json extensions_config.json
  [ -f .env ] || cp .env.example .env
  ensure_line .env BETTER_AUTH_SECRET "$(generate_secret)"
  ensure_line .env DEER_FLOW_INTERNAL_AUTH_TOKEN "$(generate_secret)"
  set_line .env DEER_FLOW_INTERNAL_GATEWAY_BASE_URL "http://127.0.0.1:${{GATEWAY_PORT}}"
  set_line .env DEER_FLOW_TRUSTED_ORIGINS "http://127.0.0.1:${{FRONTEND_PORT}},http://127.0.0.1:${{SERVICE_PORT}},http://localhost:${{SERVICE_PORT}}"
{visual_asset_env_lines}
  normalize_sqlite_config
  remove_legacy_deepseek_proxy_config
  mkdir -p /etc/intelli-engine
  touch /etc/intelli-engine/gateway.env
  chmod 600 /etc/intelli-engine/gateway.env
}}

normalize_sqlite_config() {{
  mkdir -p "$DEPLOY_DIR/.deer-flow/data"
  DEPLOY_DIR="$DEPLOY_DIR" python3 - <<'PY'
import os
from pathlib import Path

deploy_dir = os.environ["DEPLOY_DIR"]
config_path = Path(deploy_dir) / "config.yaml"
sqlite_dir = str(Path(deploy_dir) / ".deer-flow" / "data")
lines = config_path.read_text(encoding="utf-8").splitlines()
out = []
in_database = False
seen_database = False
sqlite_dir_set = False

for line in lines:
    stripped = line.strip()
    if line.startswith("database:"):
        in_database = True
        seen_database = True
        out.append(line)
        continue
    if in_database and line and not line.startswith((" ", "\t")):
        if not sqlite_dir_set:
            out.append("  sqlite_dir: " + sqlite_dir)
            sqlite_dir_set = True
        in_database = False
    if in_database and stripped.startswith("sqlite_dir:"):
        out.append("  sqlite_dir: " + sqlite_dir)
        sqlite_dir_set = True
    else:
        out.append(line)

if in_database and not sqlite_dir_set:
    out.append("  sqlite_dir: " + sqlite_dir)
    sqlite_dir_set = True
if not seen_database:
    out.extend(["", "database:", "  backend: sqlite", "  sqlite_dir: " + sqlite_dir])

config_path.write_text("\\n".join(out) + "\\n", encoding="utf-8")
PY
}}

remove_legacy_deepseek_proxy_config() {{
  DEPLOY_DIR="$DEPLOY_DIR" python3 - <<'PY'
import os
from pathlib import Path

config_path = Path(os.environ["DEPLOY_DIR"]) / "config.yaml"
text = config_path.read_text(encoding="utf-8")
updated = text.replace(
    "api_base: http://127.0.0.1:18080/v1",
    "api_base: https://api.deepseek.com/v1",
)
if updated != text:
    config_path.write_text(updated, encoding="utf-8")
PY
}}

seed_tiktoken_cache() {{
  log "Ensuring tiktoken cl100k_base cache"
  mkdir -p "$TIKTOKEN_CACHE_DIR"
  if [ -s "$TIKTOKEN_CACHE_DIR/$CL100K_CACHE_KEY" ]; then
    log "tiktoken cache already present"
    return
  fi
  if [ -s "$CL100K_BUNDLE" ]; then
    cp "$CL100K_BUNDLE" "$TIKTOKEN_CACHE_DIR/$CL100K_CACHE_KEY"
  else
    curl --connect-timeout 10 --max-time 60 -fL "$CL100K_URL" -o "$TIKTOKEN_CACHE_DIR/$CL100K_CACHE_KEY"
  fi
  test -s "$TIKTOKEN_CACHE_DIR/$CL100K_CACHE_KEY"
}}

build_backend() {{
  log "Installing backend dependencies"
  cd "$DEPLOY_DIR/backend"
  export PATH="/opt/python-3.12/bin:/root/.local/bin:/opt/node22/bin:$PATH"
  export UV_PYTHON="$PYTHON_BIN"
  export UV_DEFAULT_INDEX="https://pypi.tuna.tsinghua.edu.cn/simple"
  export UV_INDEX_URL="https://pypi.tuna.tsinghua.edu.cn/simple"
  "$UV_BIN" sync --all-packages
}}

validate_backend_runtime() {{
  log "Validating backend runtime config and offline tokenizer"
  cd "$DEPLOY_DIR/backend"
  export_runtime_env
  "$DEPLOY_DIR/backend/.venv/bin/python" - <<'PY'
from deerflow.config.app_config import get_app_config

config = get_app_config()
if not config.models:
    raise SystemExit("config.yaml has no active models. Do not deploy config.example.yaml unchanged.")
print("models:", ",".join(model.name for model in config.models))

import tiktoken

encoding = tiktoken.get_encoding("cl100k_base")
print("tiktoken:", encoding.name, "tokens_for_smoke=", len(encoding.encode("smoke")))
PY
}}

build_frontend() {{
  log "Installing and building frontend"
  cd "$DEPLOY_DIR/frontend"
  export PATH="/opt/node22/bin:$PATH"
  "$PNPM_BIN" config set registry https://registry.npmmirror.com
  "$PNPM_BIN" install --frozen-lockfile
  export BETTER_AUTH_SECRET
  BETTER_AUTH_SECRET="$(grep -E '^BETTER_AUTH_SECRET=' "$DEPLOY_DIR/.env" | tail -n1 | cut -d= -f2-)"
  "$PNPM_BIN" build
}}

write_nginx_config() {{
  log "Writing nginx config"
  cat > "$DEPLOY_DIR/nginx.baremetal.conf" <<EOF
worker_processes auto;
error_log $LOG_DIR/nginx-error.log warn;
pid $LOG_DIR/nginx.pid;

events {{
    worker_connections 1024;
}}

http {{
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    access_log $LOG_DIR/nginx-access.log;
    sendfile on;
    keepalive_timeout 65;

    map \\$http_upgrade \\$connection_upgrade {{
        default upgrade;
        '' close;
    }}

    server {{
        listen $SERVICE_PORT;
        server_name _;
        client_max_body_size 100M;

        location /api/langgraph/ {{
            rewrite ^/api/langgraph/(.*)$ /api/\\$1 break;
            proxy_pass http://127.0.0.1:$GATEWAY_PORT;
            proxy_http_version 1.1;
            proxy_read_timeout 600s;
            proxy_send_timeout 600s;
            proxy_set_header Host \\$http_host;
            proxy_set_header X-Real-IP \\$remote_addr;
            proxy_set_header X-Forwarded-For \\$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \\$scheme;
            proxy_set_header Upgrade \\$http_upgrade;
            proxy_set_header Connection \\$connection_upgrade;
            proxy_buffering off;
        }}

        location /api/ {{
            proxy_pass http://127.0.0.1:$GATEWAY_PORT;
            proxy_http_version 1.1;
            proxy_read_timeout 600s;
            proxy_send_timeout 600s;
            proxy_set_header Host \\$http_host;
            proxy_set_header X-Real-IP \\$remote_addr;
            proxy_set_header X-Forwarded-For \\$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \\$scheme;
            proxy_set_header Upgrade \\$http_upgrade;
            proxy_set_header Connection \\$connection_upgrade;
            proxy_buffering off;
        }}

        location /health {{
            proxy_pass http://127.0.0.1:$GATEWAY_PORT/health;
            proxy_set_header Host \\$http_host;
            proxy_set_header X-Real-IP \\$remote_addr;
            proxy_set_header X-Forwarded-For \\$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \\$scheme;
        }}

        location /docs {{
            proxy_pass http://127.0.0.1:$GATEWAY_PORT;
            proxy_http_version 1.1;
            proxy_set_header Host \\$http_host;
            proxy_set_header X-Real-IP \\$remote_addr;
            proxy_set_header X-Forwarded-For \\$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \\$scheme;
        }}

        location /redoc {{
            proxy_pass http://127.0.0.1:$GATEWAY_PORT;
            proxy_http_version 1.1;
            proxy_set_header Host \\$http_host;
            proxy_set_header X-Real-IP \\$remote_addr;
            proxy_set_header X-Forwarded-For \\$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \\$scheme;
        }}

        location /openapi.json {{
            proxy_pass http://127.0.0.1:$GATEWAY_PORT;
            proxy_http_version 1.1;
            proxy_set_header Host \\$http_host;
            proxy_set_header X-Real-IP \\$remote_addr;
            proxy_set_header X-Forwarded-For \\$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \\$scheme;
        }}

        location / {{
            proxy_pass http://127.0.0.1:$FRONTEND_PORT;
            proxy_http_version 1.1;
            proxy_set_header Host \\$http_host;
            proxy_set_header X-Real-IP \\$remote_addr;
            proxy_set_header X-Forwarded-For \\$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \\$scheme;
            proxy_set_header Upgrade \\$http_upgrade;
            proxy_set_header Connection \\$connection_upgrade;
        }}
    }}
}}
EOF
}}

write_systemd_units() {{
  log "Writing systemd units"
  cat > "/etc/systemd/system/${{GATEWAY_SERVICE}}.service" <<EOF
[Unit]
Description=Intelli Engine Gateway
After=network.target

[Service]
Type=simple
WorkingDirectory=$DEPLOY_DIR/backend
Environment=PATH=/opt/python-3.12/bin:/root/.local/bin:/opt/node22/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
Environment=PYTHONPATH=$DEPLOY_DIR/backend:$DEPLOY_DIR/backend/packages/harness
Environment=DEER_FLOW_CONFIG_PATH=$DEPLOY_DIR/config.yaml
Environment=DEER_FLOW_EXTENSIONS_CONFIG_PATH=$DEPLOY_DIR/extensions_config.json
Environment=DEER_FLOW_HOME=$DEPLOY_DIR/.deer-flow
Environment=TIKTOKEN_CACHE_DIR=$TIKTOKEN_CACHE_DIR
Environment=MODEL_LOG_PATH=$LOG_DIR/model.log
Environment=MODEL_LOG_LEVEL=INFO
Environment=MODEL_LOG_LOGGERS=app,deerflow,langgraph,langchain,openai,httpx,httpcore,uvicorn
Environment=MODEL_LOG_MAX_BYTES=104857600
Environment=MODEL_LOG_BACKUP_COUNT=5
EnvironmentFile=$DEPLOY_DIR/.env
EnvironmentFile=-/etc/intelli-engine/gateway.env
ExecStart=$DEPLOY_DIR/backend/.venv/bin/uvicorn app.gateway.app:app --host 0.0.0.0 --port $GATEWAY_PORT --workers $GATEWAY_WORKERS
Restart=always
RestartSec=5
TimeoutStopSec=15
KillSignal=SIGINT
KillMode=mixed
StandardOutput=append:$LOG_DIR/gateway.log
StandardError=append:$LOG_DIR/gateway-error.log

[Install]
WantedBy=multi-user.target
EOF

  cat > "/etc/systemd/system/${{FRONTEND_SERVICE}}.service" <<EOF
[Unit]
Description=Intelli Engine Frontend
After=network.target ${{GATEWAY_SERVICE}}.service
Wants=${{GATEWAY_SERVICE}}.service

[Service]
Type=simple
WorkingDirectory=$DEPLOY_DIR/frontend
Environment=PATH=/opt/node22/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
Environment=PORT=$FRONTEND_PORT
Environment=HOSTNAME=0.0.0.0
Environment=DEER_FLOW_INTERNAL_GATEWAY_BASE_URL=http://127.0.0.1:$GATEWAY_PORT
EnvironmentFile=$DEPLOY_DIR/.env
ExecStart=/opt/node22/bin/pnpm exec next start -p $FRONTEND_PORT -H 0.0.0.0
Restart=always
RestartSec=5
StandardOutput=append:$LOG_DIR/frontend.log
StandardError=append:$LOG_DIR/frontend-error.log

[Install]
WantedBy=multi-user.target
EOF

  cat > "/etc/systemd/system/${{NGINX_SERVICE}}.service" <<EOF
[Unit]
Description=Intelli Engine Nginx Reverse Proxy
After=network.target ${{GATEWAY_SERVICE}}.service ${{FRONTEND_SERVICE}}.service
Wants=${{GATEWAY_SERVICE}}.service ${{FRONTEND_SERVICE}}.service

[Service]
Type=simple
ExecStart=/usr/sbin/nginx -c $DEPLOY_DIR/nginx.baremetal.conf -g 'daemon off;'
ExecReload=/usr/sbin/nginx -c $DEPLOY_DIR/nginx.baremetal.conf -s reload
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable "$GATEWAY_SERVICE" "$FRONTEND_SERVICE" "$NGINX_SERVICE"
}}

wait_for_http() {{
  local name="$1" url="$2"
  local attempt
  for attempt in $(seq 1 60); do
    if curl -fsS "$url" >/tmp/intelli-engine-health.out 2>/tmp/intelli-engine-health.err; then
      cat /tmp/intelli-engine-health.out
      echo
      return 0
    fi
    if [ "$attempt" = "60" ]; then
      echo "Timed out waiting for $name at $url" >&2
      cat /tmp/intelli-engine-health.err >&2 || true
      return 1
    fi
    sleep 1
  done
}}

start_and_verify() {{
  log "Starting intelli-engine services"
  systemctl restart "$GATEWAY_SERVICE"
  systemctl restart "$FRONTEND_SERVICE"
  systemctl restart "$NGINX_SERVICE"
  sleep 3

  systemctl --no-pager --full status "$GATEWAY_SERVICE" "$FRONTEND_SERVICE" "$NGINX_SERVICE" | sed -n '1,90p' || true

  log "Verifying health endpoints"
  wait_for_http gateway "http://127.0.0.1:${{GATEWAY_PORT}}/health"
  wait_for_http nginx "http://127.0.0.1:${{SERVICE_PORT}}/health"

  log "Verifying OpenAPI docs endpoint"
  wait_for_http openapi "http://127.0.0.1:${{SERVICE_PORT}}/openapi.json" >/tmp/intelli-openapi.out
  grep -q '"/api/v1/conversations"' /tmp/intelli-openapi.out
}}

main() {{
  log "Bare-metal deploy started"
  if [ "$INSTALL_RUNTIME" = "true" ]; then
    install_base_packages
    ensure_python
    ensure_node
    ensure_uv
  fi
  deploy_source
  seed_runtime_config
  seed_tiktoken_cache
  build_backend
  validate_backend_runtime
  build_frontend
  write_nginx_config
  write_systemd_units
  start_and_verify
  log "Bare-metal deploy finished: http://$(hostname -I | awk '{{print $1}}'):${{SERVICE_PORT}}"
}}

main "$@"
"""


class SSHSession:
    def __init__(self, config: DeployConfig) -> None:
        try:
            import paramiko
        except ImportError as exc:  # pragma: no cover - exercised by operators.
            raise SystemExit("Missing dependency: install paramiko with `python -m pip install paramiko`.") from exc

        self.config = config
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    def __enter__(self) -> "SSHSession":
        self.client.connect(
            hostname=self.config.host,
            username=self.config.user,
            password=self.config.password,
            timeout=20,
            banner_timeout=20,
            auth_timeout=20,
        )
        return self

    def __exit__(self, *args: object) -> None:
        self.client.close()

    def upload(self, local_path: Path, remote_path: str) -> None:
        with self.client.open_sftp() as sftp:
            sftp.put(str(local_path), remote_path)

    def run(self, command: str, *, stdin_data: str | None = None) -> int:
        stdin, stdout, stderr = self.client.exec_command(command, get_pty=False)
        if stdin_data is not None:
            stdin.write(stdin_data)
            stdin.channel.shutdown_write()

        streams = (stdout.channel,)
        while not stdout.channel.exit_status_ready():
            if stdout.channel.recv_ready():
                sys.stdout.buffer.write(stdout.channel.recv(4096))
                sys.stdout.buffer.flush()
            if stdout.channel.recv_stderr_ready():
                sys.stderr.buffer.write(stdout.channel.recv_stderr(4096))
                sys.stderr.buffer.flush()
            time.sleep(0.1)
        del streams

        remaining = stdout.read()
        errors = stderr.read()
        if remaining:
            sys.stdout.buffer.write(remaining)
        if errors:
            sys.stderr.buffer.write(errors)
        return stdout.channel.recv_exit_status()


def print_summary(config: DeployConfig, archive_path: Path | None, dry_run: bool) -> None:
    print("Bare-metal deployment")
    print(f"  Host:        {config.user}@{config.host}")
    print(f"  Deploy dir:  {config.deploy_dir}")
    print(f"  Log dir:     {config.log_dir}")
    print(f"  Public URL:  {config.public_url}")
    print(f"  Service:     {config.service_name}")
    print(f"  Kill ports:  {config.kill_port_conflicts}")
    print("  Password:    ******")
    if archive_path:
        print(f"  Archive:     {archive_path} ({archive_path.stat().st_size / 1024 / 1024:.1f} MiB)")
    if dry_run:
        print("  Mode:        dry-run; no SSH connection or upload will be performed")


def main() -> int:
    parser = argparse.ArgumentParser(description="Deploy intelli-engine to a bare-metal server with systemd.")
    parser.add_argument("--config", default=None, help="Path to deployment config. Default: .deploy.conf when --env is omitted.")
    parser.add_argument("--env", help="Environment name. Resolves deploy/envs/<env>.conf, deploy/envs/<env>.baremetal.conf, or .deploy-<env>.conf.")
    parser.add_argument("--dry-run", action="store_true", help="Validate config and show what would be deployed.")
    parser.add_argument("--skip-runtime-install", action="store_true", help="Skip OS/Node/Python/uv installation checks on the remote host.")
    args = parser.parse_args()

    config_path = resolve_config_path(args.config, args.env)
    if not config_path.exists():
        raise SystemExit(f"Deployment config not found: {config_path}")
    config = load_config(config_path)

    if args.dry_run:
        print_summary(config, None, dry_run=True)
        return 0

    archive_path = create_archive(REPO_ROOT, DEFAULT_EXCLUDES)
    remote_archive = posixpath.join("/tmp", archive_path.name)
    print_summary(config, archive_path, dry_run=False)

    try:
        with SSHSession(config) as ssh:
            print(f"\nUploading archive to {config.host}:{remote_archive}")
            ssh.upload(archive_path, remote_archive)
            script = remote_script(config, remote_archive, args.skip_runtime_install)
            print("\nRunning remote deployment")
            exit_code = ssh.run("bash -s", stdin_data=script)
            if exit_code != 0:
                raise SystemExit(exit_code)
    finally:
        archive_path.unlink(missing_ok=True)

    print(f"\nDeployment complete: {config.public_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
