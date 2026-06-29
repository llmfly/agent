# Intelli Engine 部署手册

本文档沉淀 Intelli Engine 的容器化部署和裸机部署流程，以及 2026-06 部署排障中确认过的坑位。目标是后续按环境名执行部署，而不是每次重新摸索。

## 部署入口

### 裸机部署

推荐入口：

```bash
python scripts/deploy_intelli.py --env dev --mode baremetal
```

也可以直接调用底层脚本：

```bash
python scripts/deploy_baremetal.py --env dev
python scripts/deploy_baremetal.py --config deploy/envs/dev.conf
```

环境配置解析顺序：

1. `deploy/envs/<env>.conf`
2. `deploy/envs/<env>.baremetal.conf`
3. `.deploy-<env>.conf`

真实配置文件包含 SSH 密码、内部 URL 等敏感信息，已通过 `.gitignore` 忽略。模板见 `deploy/envs/dev.example.conf`。

### 容器化部署

生产容器化入口：

```bash
bash scripts/deploy.sh
```

常用命令：

```bash
bash scripts/deploy.sh build
bash scripts/deploy.sh start
bash scripts/deploy.sh down
```

开发容器化入口仍使用：

```bash
make docker-init
make docker-start
make docker-stop
```

## 裸机部署流程

`scripts/deploy_baremetal.py` 会自动执行：

1. 读取目标环境配置。
2. 打包源码，排除 `.git`、`.env`、`config.yaml`、`extensions_config.json`、本地部署配置、venv、node_modules、日志等。
3. 上传到目标服务器。
4. 停止 systemd 服务。
5. 默认清理目标端口旧监听：公网端口、gateway `8005`、frontend `3001`。
6. 保留远端 `.env`、`config.yaml`、`extensions_config.json`、`.deer-flow`，替换代码。
7. 安装或复用 Python 3.12、Node 22、pnpm、uv。
8. 预置 tiktoken `cl100k_base` cache。
9. `uv sync --all-packages` 安装后端依赖。
10. 加载真实 `AppConfig` 校验 active models。
11. 离线加载 `tiktoken.get_encoding("cl100k_base")`，确保不会运行时下载 tokenizer。
12. 安装并构建前端。
13. 生成 nginx bare-metal 配置，包含 `/docs`、`/redoc`、`/openapi.json`。
14. 写入 systemd units。
15. 启动 gateway、frontend、nginx。
16. 验证 gateway health、nginx health、OpenAPI 文档。

## 容器化部署流程

`scripts/deploy.sh` 会自动：

1. 准备 `DEER_FLOW_HOME`。
2. 把 `scripts/deploy_resources/tiktoken/cl100k_base.tiktoken` 复制到 `${DEER_FLOW_HOME}/tiktoken-cache/<sha1>`。
3. 生成或复用 `BETTER_AUTH_SECRET`。
4. 生成或复用 `DEER_FLOW_INTERNAL_AUTH_TOKEN`。
5. 检测 sandbox 模式。
6. 调用 `docker compose` 构建或启动服务。

`docker/docker-compose.yaml` 中 gateway 容器固定设置：

```yaml
TIKTOKEN_CACHE_DIR=/app/backend/.deer-flow/tiktoken-cache
```

因为 `${DEER_FLOW_HOME}` 会挂载到 `/app/backend/.deer-flow`，所以容器内也会使用启动前预置的 tokenizer cache。

## 必须规避的坑

### 1. `/api/v1/` 路径下 JWT cookie auth 不生效

现象：

- 新加的 `/api/v1/workspace/data-sources` 返回 401，但其他 v1 接口正常。
- 浏览器已登录且有 `access_token` cookie，请求仍被拒绝。

根因：

- `AuthMiddleware` 将 `/api/v1/` 前缀标记为公开路径（`_PUBLIC_PATH_PREFIXES`），因此**跳过** JWT cookie 校验，也不会往 `ContextVar` 写入用户身份。
- 路由 handler 若通过 `get_current_user()` 从 `ContextVar` 读取用户，必然返回 `None` → 401。

修复方法：

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

然后在路由 handler 中用 `user_id: str = Depends(_require_user)` 注入依赖，不要调用 `get_current_user()`。

检查清单：

- 新增 v1 路由是否从 cookie 而不是 `ContextVar` 解析用户？
- 是否与 `get_external_context`（基于 header）的认证路径一致？

### 2. tiktoken 首次下载导致 stream 卡住

现象：

- SSE 停在 middleware 前后，只看到用户消息、`ThreadDataMiddleware`、`UploadsMiddleware`、`SandboxMiddleware`。
- run 长时间 running。
- 进程可能卡在连接外网 IP。

根因：

- `DynamicContextMiddleware -> memory prompt -> tiktoken.get_encoding("cl100k_base")`。
- tiktoken 首次加载会访问 `https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken`。
- 网络不可达或解析到慢 IP 时，会阻塞 agent 进入模型调用。

脚本规避：

- 裸机：部署阶段预置 cache，并给 gateway systemd 写入 `TIKTOKEN_CACHE_DIR`。
- 容器：启动前把 cache 放入 `DEER_FLOW_HOME/tiktoken-cache`，容器内设置 `TIKTOKEN_CACHE_DIR`。
- 裸机部署会运行离线 tokenizer 校验，失败则部署失败。

### 3. 不要把 DeepSeek DNS pin 当根因修复

确认结果：

- 之前看到的 `57.150.192.193` 最终确认来自 tokenizer 下载链路，不是 DeepSeek endpoint 本身。
- `/etc/hosts` 不应固定 `api.deepseek.com`。
- nginx 不应默认生成 DeepSeek 内部反代。

当前策略：

- `config.yaml` 保持正常 `api_base: https://api.deepseek.com/v1`。
- 通过 tokenizer cache 解决 run 卡死根因。
- DeepSeek 网络慢属于模型访问稳定性问题，可单独优化，不混入默认部署。
- 裸机部署会把旧残留的 `api_base: http://127.0.0.1:18080/v1` 自动归一为 `https://api.deepseek.com/v1`，避免模型调用打到不存在的本机反代后报 `APIConnectionError: Connection refused`。

### 4. 旧目录或旧手工进程占用 2026

现象：

- 新目录服务已启动，但浏览器仍访问旧目录前端。
- `ss -ltnp` 显示 `2026` 被旧 nginx 进程占用。

脚本规避：

- 裸机默认 `KILL_PORT_CONFLICTS=true`。
- 部署时清理公网端口、gateway 端口、frontend 端口上的旧监听。

### 5. 示例 config.yaml 不能直接部署

现象：

- gateway 启动失败：

```text
models
  Input should be a valid list
```

原因：

- `config.example.yaml` 中 `models:` 下都是注释，等价于 `models: null`。

脚本规避：

- 裸机部署会在后端依赖安装后加载 `AppConfig`，没有 active models 直接失败。
- 首次部署前必须在远端 `config.yaml` 中配置真实模型，或保留已有可用 `config.yaml`。

### 6. uv、pnpm、Node 下载不稳定

脚本规避：

- Node 使用 `npmmirror.com`。
- pnpm 使用 `COREPACK_NPM_REGISTRY=https://registry.npmmirror.com`，corepack 失败时 fallback 到 npm 全局安装。
- uv 安装脚本失败时 fallback 到清华 PyPI 源 `pip install --user uv`。
- 后端依赖使用清华 PyPI 源。

### 7. Swagger/OpenAPI 404

脚本规避：

- 裸机 nginx 配置显式转发：
  - `/docs`
  - `/redoc`
  - `/openapi.json`
- 部署后验证 `/openapi.json` 中包含 `/api/v1/conversations`。

### 8. VISUAL_ASSET 配置遗漏

脚本规避：

- 裸机部署配置中所有 `VISUAL_ASSET_*` 会写入远端 `.env`。
- `deploy/envs/dev.example.conf` 已包含 visual asset 示例字段。

### 9. SQLite 相对路径导致账号和对话数据在部署后丢失

现象：

- 每次重新部署后需要重新创建管理员账号。
- 历史对话、runs、checkpoint 看起来被清空。
- 远端同时出现两个数据库：
  - `/data/intelli/engine/.deer-flow/data/deerflow.db`
  - `/data/intelli/engine/backend/.deer-flow/data/deerflow.db`

根因：

- `config.yaml` 中 `database.sqlite_dir: .deer-flow/data` 是相对路径。
- gateway systemd 的 `WorkingDirectory` 是 `/data/intelli/engine/backend`。
- 因此运行时 SQLite 被解析到 `/data/intelli/engine/backend/.deer-flow/data/deerflow.db`。
- 裸机部署会替换整个 `backend/` 目录，所以这个误置数据库会在下次部署时丢失。

脚本规避：

- 裸机部署现在会在替换 `backend/` 前备份误置数据库到 `/data/intelli/engine/.deer-flow/backups/`。
- 如果持久化库不存在，会自动从误置库恢复到 `/data/intelli/engine/.deer-flow/data/deerflow.db`。
- 每次部署都会把 `config.yaml` 的 `database.sqlite_dir` 归一为绝对路径：`/data/intelli/engine/.deer-flow/data`。
- 部署后必须验证 `backend/.deer-flow/data/deerflow.db` 不存在或不再增长，且数据计数来自 `/data/intelli/engine/.deer-flow/data/deerflow.db`。

### 10. Radix UI Select.Item 空字符串 value 报错

现象：

- 浏览器控制台报错：`A <Select.Item /> must have a value prop that is not an empty string.`
- 数据资产页面白屏或筛选器无法使用。

根因：

- Radix UI 的 `<SelectItem>` 不允许 `value=""`（空字符串被保留用于清除选择）。
- `<SelectItem value="">全部</SelectItem>` 直接触发 Radix 内部断言错误。

修复方法：

```tsx
// ❌ 错误
<SelectItem value="">{t.dataAssets.filterAll}</SelectItem>

// ✅ 正确
<SelectItem value="all">{t.dataAssets.filterAll}</SelectItem>
```

同时调整 state 和过滤逻辑：

```tsx
const [typeFilter, setTypeFilter] = useState<string>("all");
// ...
// 发送请求时把 "all" 转回 undefined
type: typeFilter === "all" ? undefined : typeFilter,
```

### 11. SQLite config_json 写入 dict 导致 Error binding parameter

现象：

- 创建数据源时后端报错：`sqlalchemy.exc.ProgrammingError: (sqlite3.ProgrammingError) Error binding parameter 8: type 'dict' is not supported`
- SQL：`INSERT INTO datasource (...) config_json VALUES (...)`
- parameters 中 `config_json` 值为 Python dict。

根因：

- `DataSourceRow.config_json` 字段类型为 `JSONB().with_variant(String, "sqlite")`。
- SQLite 下实际存储为 `String`，ORM 不会自动将 dict 序列化为 JSON。
- Postgres 下 `JSONB` 原生接受 dict，所以本地开发（Postgres）正常，只有 SQLite 部署才暴露。

修复方法 — 写路径：

```python
# 检测 SQLite 后端后手动序列化
raw_config = request.config or {}
config_value: dict | str = raw_config
if _is_sqlite():
    config_value = json.dumps(raw_config, ensure_ascii=False)
```

修复方法 — 读路径：

```python
def _ensure_config_dict(raw: Any) -> dict[str, Any]:
    """Normalize config_json to dict regardless of storage backend."""
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw       # Postgres JSONB → native dict
    if isinstance(raw, str):
        try:
            return json.loads(raw)  # SQLite String → parsed dict
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}
```

检查清单：

- 配置字段是否在不同数据库后端下类型一致？
- 带有 `with_variant` 的 ORM 字段，是否在每种 variant 下都测试过读写？
- 新增表字段时，是否检查了 SQLite 下 `String` variant 的行为？

## 部署前检查

本地：

```bash
git status --short
python -m py_compile scripts/deploy_baremetal.py scripts/deploy_intelli.py
```

目标配置：

```bash
python scripts/deploy_intelli.py --env dev --mode baremetal --dry-run
```

远端必须已经有真实运行配置：

- `/data/intelli/engine/.env`
- `/data/intelli/engine/config.yaml`
- `/data/intelli/engine/extensions_config.json`

首次部署如果这些文件不存在，脚本会从 example 生成，但 `config.yaml` 仍需要人工补 active models。

## 部署后验证

基础验证：

```bash
curl -fsS http://<host>:2026/health
curl -fsS http://<host>:2026/openapi.json
```

SQLite 持久化验证：

```bash
grep -A3 '^database:' /data/intelli/engine/config.yaml
test ! -f /data/intelli/engine/backend/.deer-flow/data/deerflow.db
python3 - <<'PY'
import sqlite3
db = "/data/intelli/engine/.deer-flow/data/deerflow.db"
conn = sqlite3.connect(db)
cur = conn.cursor()
for table in ("users", "threads_meta", "runs", "checkpoints"):
    print(table, cur.execute(f"select count(*) from {table}").fetchone()[0])
conn.close()
PY
```

端口和进程：

```bash
ss -ltnp | grep -E ':2026|:8005|:3001'
```

预期：

- `2026`：nginx，配置来自目标 `DEPLOY_DIR/nginx.baremetal.conf`
- `8005`：gateway
- `3001`：frontend
- 不应有 `18080` DeepSeek 反代监听

gateway 环境：

```bash
tr '\0' '\n' < /proc/<gateway_pid>/environ | grep -E 'DEER_FLOW|TIKTOKEN|PYTHONPATH'
```

预期包含：

```text
DEER_FLOW_CONFIG_PATH=/data/intelli/engine/config.yaml
DEER_FLOW_EXTENSIONS_CONFIG_PATH=/data/intelli/engine/extensions_config.json
DEER_FLOW_HOME=/data/intelli/engine/.deer-flow
TIKTOKEN_CACHE_DIR=/data/intelli/engine/.deer-flow/tiktoken-cache
```

## 日志位置

裸机默认：

- gateway stdout：`/data/log/intelli/engine/gateway.log`
- gateway stderr：`/data/log/intelli/engine/gateway-error.log`
- frontend stdout：`/data/log/intelli/engine/frontend.log`
- frontend stderr：`/data/log/intelli/engine/frontend-error.log`
- nginx access：`/data/log/intelli/engine/nginx-access.log`
- nginx error：`/data/log/intelli/engine/nginx-error.log`

容器化：

```bash
docker compose -p deer-flow -f docker/docker-compose.yaml logs -f gateway
docker compose -p deer-flow -f docker/docker-compose.yaml logs -f frontend
docker compose -p deer-flow -f docker/docker-compose.yaml logs -f nginx
```

## 后续 Codex 操作约定

当用户说：

```text
部署到 dev 环境，裸部署
```

执行：

```bash
python scripts/deploy_intelli.py --env dev --mode baremetal
```

当用户说：

```text
部署到 dev 环境，裸部署，跳过运行时安装
```

执行：

```bash
python scripts/deploy_intelli.py --env dev --mode baremetal --skip-runtime-install
```

当用户说：

```text
容器化部署
```

执行：

```bash
python scripts/deploy_intelli.py --env dev --mode docker
```

部署完成后必须报告：

- 目标环境和目录
- 是否预置 tokenizer cache
- health 结果
- OpenAPI 结果
- 端口归属
- 是否发现旧目录或旧进程
