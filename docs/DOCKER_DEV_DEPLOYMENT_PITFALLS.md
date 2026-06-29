# Docker Dev Deployment Pitfalls

本文记录 `172.16.0.160` dev 环境从裸金属部署切换到 Docker 部署时遇到的问题、原因和处理方式，方便后续部署人员避坑。

## 部署基线

- 目标环境：`172.16.0.160`
- 对外端口：`2026`
- 部署目录：`/data/intelli/engine`
- Docker Compose project：`deer-flow`
- 对外入口：`deer-flow-nginx`
- 后端容器：`deer-flow-gateway`
- 前端容器：`deer-flow-frontend`
- 配置文件：本地 `.deploy.conf` 仅用于部署读取，不允许提交仓库。
- API key：不要写入项目 `.env`；dev 机使用 `/etc/intelli-engine/gateway.env` 挂载给 gateway。
- Visual asset 外部图片生成接口：`http://10.8.5.222:8010/generate`

## 必须从干净的 `origin/dev-v0.1` 部署

本地工作区可能存在开发人员未提交改动、冲突文件或未跟踪文件，不能直接把当前目录打包上传。

推荐方式：

```bash
git fetch origin dev-v0.1 master --prune
git archive --format=tar.gz -o /tmp/intelli-engine-<rev>.tar.gz origin/dev-v0.1
```

这样可以确保部署包只包含远端 `dev-v0.1` 的干净代码，不会混入本地开发态文件。

## 需要保留远端运行配置

替换代码时不要删除这些远端文件或目录：

- `/data/intelli/engine/.env`
- `/data/intelli/engine/config.yaml`
- `/data/intelli/engine/extensions_config.json`
- `/data/intelli/engine/.deer-flow`
- `/data/intelli/engine/docker/docker-compose.remote.yaml`
- `/etc/intelli-engine/gateway.env`

这些文件包含运行时配置、密钥、模型配置和本机 override。部署代码时应先备份，再解压新包，再恢复。

## `frontend/.env` 缺失会导致 compose 启动失败

现象：

```text
env file /data/intelli/engine/frontend/.env not found
```

原因：新版 `docker/docker-compose.yaml` 中 frontend 服务声明了：

```yaml
env_file:
  - ../frontend/.env
```

处理方式：在远端部署目录创建 `/data/intelli/engine/frontend/.env`。

推荐内容：

```env
DEER_FLOW_INTERNAL_GATEWAY_BASE_URL=http://192.168.208.3:8001
DEER_FLOW_TRUSTED_ORIGINS=http://172.16.0.160:2026,http://localhost:2026,http://127.0.0.1:2026
```

## 容器内服务名解析不稳定

现象：frontend SSR 或内部 API 请求无法解析 `gateway`，页面显示：

```text
Service temporarily unavailable.
The backend may be restarting. Please wait a moment and try again.
```

frontend 日志中可见：

```text
[SSR auth] Failed to reach gateway: TypeError: fetch failed
Error: getaddrinfo EAI_AGAIN gateway
```

原因：目标机 Docker daemon 环境存在类似 K8s 的 DNS search/ndots 影响，短服务名解析不稳定。

本次实际验证中，frontend 容器内的 `/etc/resolv.conf` 带有：

```text
search default.svc.cluster.local svc.cluster.local
options ndots:2 timeout:2 attempts:2
```

因此 `gateway` 会先被解析成 `gateway.default.svc.cluster.local` / `gateway.svc.cluster.local`，外部 DNS 返回 `SERVFAIL` 后 Docker 内置 DNS 没有稳定回落到 compose service alias。验证命令：

```bash
docker exec deer-flow-frontend nslookup gateway
docker exec deer-flow-frontend nslookup gateway.
docker exec deer-flow-frontend node -e "fetch('http://gateway.:8001/health').then(async r => console.log(r.status, await r.text()))"
```

处理方式优先级：

1. 推荐在 compose 中把 frontend 内部网关地址写成绝对 DNS 名称，避免 search domain 干扰。

```yaml
services:
  frontend:
    environment:
      - DEER_FLOW_INTERNAL_GATEWAY_BASE_URL=http://gateway.:8001
```

2. 如果目标机仍不稳定，再使用 compose override 固定容器 IP，并让 frontend 访问 gateway 固定 IP。

`docker/docker-compose.remote.yaml` 推荐内容：

```yaml
services:
  gateway:
    env_file:
      - ../.env
      - /etc/intelli-engine/gateway.env
    networks:
      deer-flow-network:
        ipv4_address: 192.168.208.3
  frontend:
    environment:
      PORT: 3000
      DEER_FLOW_INTERNAL_GATEWAY_BASE_URL: http://192.168.208.3:8001
    networks:
      deer-flow-network:
        ipv4_address: 192.168.208.2
  nginx:
    networks:
      deer-flow-network:
        ipv4_address: 192.168.208.4
networks:
  deer-flow-network:
    ipam:
      config:
        - subnet: 192.168.208.0/24
```

## Docker Hub 拉取镜像可能 EOF

现象：

```text
nginx Error Get "https://registry-1.docker.io/v2/": EOF
```

原因：目标机访问 Docker Hub 不稳定。

处理方式：提前从镜像源拉取并打成本地 compose/build 需要的原始 tag。

```bash
docker pull docker.m.daocloud.io/nginx:alpine
docker tag docker.m.daocloud.io/nginx:alpine nginx:alpine

docker pull docker.m.daocloud.io/node:22-alpine
docker tag docker.m.daocloud.io/node:22-alpine node:22-alpine

docker pull docker.m.daocloud.io/python:3.12-slim-bookworm
docker tag docker.m.daocloud.io/python:3.12-slim-bookworm python:3.12-slim-bookworm

docker pull docker.m.daocloud.io/docker:cli
docker tag docker.m.daocloud.io/docker:cli docker:cli

docker pull ghcr.nju.edu.cn/astral-sh/uv:0.7.20
docker tag ghcr.nju.edu.cn/astral-sh/uv:0.7.20 ghcr.io/astral-sh/uv:0.7.20
```

注意：只拉取镜像源 tag 不够，必须 `docker tag` 成 compose/Dockerfile 使用的原始名称，例如 `nginx:alpine`。

## Corepack / pnpm 下载可能失败

现象：frontend 镜像构建阶段失败：

```text
Internal Error: Error when performing the request to https://registry.npmjs.org/pnpm/-/pnpm-10.26.2.tgz
corepack install -g pnpm@10.26.2 did not complete successfully
```

原因：目标机访问 npm 官方 registry 不稳定。

处理方式：在远端 `/data/intelli/engine/.env` 中设置镜像源，并在执行 `scripts/deploy.sh` 前加载 `.env`，确保 compose build args 生效。

```env
NPM_REGISTRY=https://registry.npmmirror.com
UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
UV_IMAGE=ghcr.nju.edu.cn/astral-sh/uv:0.7.20
NODE_DIST_URL=https://npmmirror.com/mirrors/node
APT_MIRROR=mirrors.tuna.tsinghua.edu.cn
```

```bash
cd /data/intelli/engine
set -a
. ./.env
set +a
PORT=2026 COMPOSE_PROGRESS=plain DOCKER_BUILDKIT=1 bash scripts/deploy.sh
```

## 远端多行脚本不要塞进 `bash -lc`

现象：

```text
bash: -c: 行 1: 寻找匹配的 `'` 时遇到了未预期的 EOF
bash: 第 1 行： set: -#: 无效的选项
```

原因：通过 SSH 执行多行脚本时，PowerShell、Python `repr`、远端 shell 多层引号和换行转义容易互相干扰。

处理方式：把脚本上传到 `/tmp/*.sh`，`chmod +x` 后执行。

```bash
chmod +x /tmp/intelli-engine-deploy.sh
/tmp/intelli-engine-deploy.sh
```

## Windows 控制台编码可能中断部署脚本

现象：构建输出包含特殊字符时，本地 Python/PowerShell 报错：

```text
UnicodeEncodeError: 'gbk' codec can't encode character
```

处理方式：

```powershell
$env:PYTHONIOENCODING='utf-8'
```

或者让远端命令输出落盘，只回传末尾日志：

```bash
docker compose up --build -d > /tmp/intelli-compose-up.log 2>&1
tail -n 200 /tmp/intelli-compose-up.log
```

## `.env` 和 API Key 的处理

`.env` 会留在服务器部署目录，适合放非敏感运行参数和随机生成的服务 secret，但不建议放第三方模型 API key。

推荐：

- `/data/intelli/engine/.env`：端口、镜像源、路径、内部 token 等运行参数。
- `/etc/intelli-engine/gateway.env`：`DEEPSEEK_API_KEY` 等模型密钥。
- compose override 中 gateway 同时加载 `../.env` 和 `/etc/intelli-engine/gateway.env`。

如果当前 compose 文件没有直接加载 `/etc/intelli-engine/gateway.env`，必须在部署时把该文件中的 key 合入 `/data/intelli/engine/.env`，否则 gateway 启动会失败：

```text
RuntimeError: Failed to load configuration during gateway startup: Environment variable DEEPSEEK_API_KEY not found for config value $DEEPSEEK_API_KEY
```

合入时不要打印密钥值：

```bash
cd /data/intelli/engine
python3 - <<'PY'
from pathlib import Path

src = Path("/etc/intelli-engine/gateway.env")
dst = Path(".env")
keys = {}
for raw in src.read_text().splitlines():
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    keys[key] = value

lines = dst.read_text().splitlines() if dst.exists() else []
out = []
seen = set()
for raw in lines:
    stripped = raw.strip()
    if stripped and not stripped.startswith("#") and "=" in stripped:
        key = raw.split("=", 1)[0]
        if key in keys:
            out.append(f"{key}={keys[key]}")
            seen.add(key)
        else:
            out.append(raw)
    else:
        out.append(raw)
for key, value in keys.items():
    if key not in seen:
        out.append(f"{key}={value}")
dst.write_text("\n".join(out) + "\n")
print("merged_keys=" + ",".join(sorted(keys)))
PY
```

如果曾经使用 `systemctl set-environment` 注入环境变量，可这样移除：

```bash
systemctl unset-environment DEEPSEEK_API_KEY
systemctl show-environment | grep DEEPSEEK_API_KEY
```

## Visual asset 外部图片生成配置

现象：视觉图片生成部署后仍走默认 OpenAI-compatible provider，或启动后调用失败。

原因：`VISUAL_ASSET_IMAGE_PROVIDER` 等配置如果写在注释行、没有写入远端 `.env`、或 gateway 容器没有重建，就不会生效。

dev 环境当前通过外部接口生成图片，远端 `/data/intelli/engine/.env` 需要包含：

```env
VISUAL_ASSET_IMAGE_PROVIDER=external-generate
VISUAL_ASSET_EXTERNAL_IMAGE_URL=http://10.8.5.222:8010/generate
VISUAL_ASSET_IMAGE_TIMEOUT_SECONDS=180
```

容器内验证：

```bash
docker exec deer-flow-gateway sh -lc 'env | sort | grep ^VISUAL_ASSET_'
```

真实 smoke test 会产生一个图片 artifact，适合在部署完成后执行一次：

```bash
python3 - <<'PY'
import json
import time
import urllib.request

base = "http://127.0.0.1:2026/api/v1/ai/visual-assets"
headers = {
    "Content-Type": "application/json",
    "X-App-Id": "notebook-app",
    "X-API-Key": "dev-key",
    "X-User-Id": "smoke-user",
    "X-Request-Id": "smoke-visual-asset",
}
body = {
    "scene": "notebook_icon",
    "input": "A fluffy golden retriever puppy, happy",
    "target": {"width": 256, "height": 256, "output_format": "png"},
    "options": {"num_images": 1, "seed": 7, "style": ["friendly", "clean"]},
}
req = urllib.request.Request(base + "/generate", data=json.dumps(body).encode(), headers=headers, method="POST")
with urllib.request.urlopen(req, timeout=30) as resp:
    job_id = json.loads(resp.read().decode())["job_id"]

for _ in range(45):
    time.sleep(4)
    req = urllib.request.Request(base + "/jobs/" + job_id, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        job = json.loads(resp.read().decode())
    print(job["status"], job["stage"], job["progress"])
    if job["status"] in {"succeeded", "failed", "cancelled"}:
        print("provider=", job.get("usage", {}).get("provider"))
        print("asset_count=", len(job.get("assets") or []))
        raise SystemExit(0 if job["status"] == "succeeded" else 1)
raise SystemExit("visual asset smoke test timed out")
PY
```

## 推荐启动命令

```bash
cd /data/intelli/engine

docker compose \
  --env-file .env \
  -p deer-flow \
  -f docker/docker-compose.yaml \
  -f docker/docker-compose.remote.yaml \
  down --remove-orphans

docker compose \
  --env-file .env \
  -p deer-flow \
  -f docker/docker-compose.yaml \
  -f docker/docker-compose.remote.yaml \
  up --build -d --remove-orphans frontend gateway nginx
```

## 验证清单

```bash
docker compose --env-file .env -p deer-flow \
  -f docker/docker-compose.yaml \
  -f docker/docker-compose.remote.yaml ps

curl -fsS http://127.0.0.1:2026/health
curl -sS -o /tmp/workspace.check -w 'workspace_http=%{http_code} redirect=%{redirect_url}\n' http://127.0.0.1:2026/workspace
curl -sS -o /tmp/docs.check -w 'docs_http=%{http_code}\n' http://127.0.0.1:2026/docs
curl -sS -o /tmp/openapi.check -w 'openapi_http=%{http_code}\n' http://127.0.0.1:2026/openapi.json
```

期望结果：

- `/health` 返回 `{"status":"healthy","service":"deer-flow-gateway"}`
- `/workspace` 返回 `307` 并跳转 `/login`，或登录后正常访问工作台。
- `/docs` 返回 `200`
- `/openapi.json` 返回 `200`

外部访问地址：

- `http://172.16.0.160:2026/workspace`
- `http://172.16.0.160:2026/docs`
- `http://172.16.0.160:2026/redoc`
- `http://172.16.0.160:2026/openapi.json`

## 快速排障命令

```bash
docker ps -a --filter name=deer-flow
docker logs --tail 200 deer-flow-gateway
docker logs --tail 200 deer-flow-frontend
docker logs --tail 200 deer-flow-nginx
docker image inspect nginx:alpine node:22-alpine python:3.12-slim-bookworm docker:cli ghcr.io/astral-sh/uv:0.7.20
cat /data/intelli/engine/.deployed-revision
docker exec deer-flow-frontend node -e "fetch(process.env.DEER_FLOW_INTERNAL_GATEWAY_BASE_URL + '/health').then(async r => console.log(r.status, await r.text()))"
docker exec deer-flow-gateway sh -lc 'env | sort | grep ^VISUAL_ASSET_'
```

如果容器处于 `Created` 而不是 `Up`，通常表示 `docker compose up` 构建或启动过程中被中断，需要查看 `/tmp/intelli-compose-up.log` 或重新执行启动命令。
