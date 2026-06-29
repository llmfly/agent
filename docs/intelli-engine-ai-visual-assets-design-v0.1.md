# intelli-engine AI Visual Assets Design

版本：v0.1  
日期：2026-06-23  
范围：AI Logo、笔记本图标、笔记本背景、封面图、通用图片生成后端能力设计  
状态：设计讨论稿，暂未实现

## 1. 设计结论

本能力不建议只命名为 `ai-logo`。更准确的定位是：

```text
AI Visual Asset Generation
AI 视觉资产生成能力
```

Logo 是其中一个场景。该能力还应覆盖：

- 笔记本图标生成。
- 笔记本背景生成。
- 封面图生成。
- 通用图片生成。

核心设计原则：

1. **先理解，再生成**：先由 `visual-agent` 将用户自然语言结构化成 `VisualDesignBrief`，再由后端 `PromptBuilder` 生成图片模型 prompt。
2. **异步任务**：图片生成耗时不稳定，接口返回 `job_id`，前端轮询进度到 100%。
3. **稳定产物访问**：图片保存到 intelli-engine 产物存储，外部只拿 `artifact_id`、`preview_url`、`download_url`，不暴露物理路径。
4. **业务系统自绑定**：笔记本系统保存用户选择的 `artifact_id`，intelli-engine 不直接修改笔记本业务表。
5. **首版不承诺准确文字 Logo**：Logo 首版主打图形标志，品牌名进入 brief，但不承诺图片模型能生成准确文字。
6. **配置化 Provider**：图片供应商、尺寸、候选图数量、TTL、限流均通过配置控制。

## 2. 业务场景

### 2.1 Logo 生成

用户输入：

```text
我想做一个面向年轻白领的精品咖啡品牌 logo，名字叫 Mellow Cup，希望简洁、有温度、不要太复杂。
```

系统输出：

- 结构化设计 brief。
- 1-4 张候选 Logo 图片。
- 每张图片对应一个 `artifact_id`。
- 前端展示候选图，由用户选择。

### 2.2 笔记本图标/背景生成

平台场景：

```text
用户创建笔记本，输入笔记本主题和内容摘要。
系统自动生成几张图片，供用户选择并设为笔记本图标或背景。
```

后端边界：

- intelli-engine 负责理解语义、生成候选图片、保存图片、返回 artifact。
- 笔记本业务系统负责创建笔记本、展示候选图片、保存用户选择结果。
- intelli-engine 不直接修改笔记本业务表。

推荐流程：

```text
1. 前端创建笔记本。
2. 前端调用 POST /api/v1/ai/visual-assets/generate。
3. 请求 metadata.notebook_id 传入笔记本 ID。
4. 后端返回 job_id。
5. 前端轮询 GET /api/v1/ai/visual-assets/jobs/{job_id}。
6. progress=100 且 status=succeeded 后展示 assets。
7. 用户选择某个 artifact_id。
8. 笔记本业务系统保存 artifact_id。
9. 可选调用 artifact pin，防止候选图被清理。
```

## 3. 接口设计

### 3.1 推荐首版接口

```http
POST /api/v1/ai/visual-assets/generate
GET  /api/v1/ai/visual-assets/jobs/{job_id}
POST /api/v1/ai/visual-assets/jobs/{job_id}/cancel

GET  /api/v1/artifacts/{artifact_id}
GET  /api/v1/artifacts/{artifact_id}/preview
GET  /api/v1/artifacts/{artifact_id}/download
POST /api/v1/artifacts/{artifact_id}/pin
POST /api/v1/artifacts/{artifact_id}/unpin
```

### 3.2 Logo Wrapper，可选

Logo 可以提供快捷 wrapper：

```http
POST /api/v1/ai/logo/generate
GET  /api/v1/ai/logo/jobs/{job_id}
```

但底层仍复用 `visual-assets` service：

```json
{
  "scene": "logo"
}
```

建议首版优先实现通用 `visual-assets`，Logo wrapper 可同阶段末尾补充。

## 4. Generate Request

```json
{
  "scene": "notebook_icon",
  "input": "这是一个关于 AI 产品设计方法论的笔记本，内容专业、简洁、有科技感",
  "target": {
    "usage": "notebook_icon",
    "aspect_ratio": "1:1",
    "width": 1024,
    "height": 1024,
    "transparent_background": false,
    "output_format": "png"
  },
  "options": {
    "num_images": 4,
    "style": ["minimal", "modern", "tech"],
    "color_preferences": ["deep blue", "silver", "white"],
    "avoid": ["readable text", "busy details"],
    "quality": "standard",
    "seed": null
  },
  "metadata": {
    "notebook_id": "nb_001",
    "project_id": "p_001"
  }
}
```

### 4.1 scene 枚举

```text
logo
notebook_icon
notebook_background
cover_image
general_image
```

### 4.2 参数限制

建议首版限制：

```text
num_images: 1-4
output_format: png
quality: draft | standard | high
width/height: provider 支持尺寸，首版建议 512 / 768 / 1024 / 1536 这类固定尺寸
```

## 5. Generate Response

```json
{
  "job_id": "job_visual_001",
  "status": "queued",
  "stage": "queued",
  "progress": 0,
  "scene": "notebook_icon",
  "message": "任务已创建",
  "created_at": "2026-06-23T10:00:00Z"
}
```

## 6. Job Detail Response

```json
{
  "job_id": "job_visual_001",
  "type": "visual_asset_generation",
  "scene": "notebook_icon",
  "status": "running",
  "stage": "generating",
  "progress": 67,
  "message": "正在生成第 2/4 张候选图",
  "owner": {
    "app_id": "notebook-app",
    "external_user_id": "user_001"
  },
  "request": {
    "input": "这是一个关于 AI 产品设计方法论的笔记本，内容专业、简洁、有科技感",
    "scene": "notebook_icon",
    "target": {
      "usage": "notebook_icon",
      "aspect_ratio": "1:1",
      "width": 1024,
      "height": 1024,
      "transparent_background": false,
      "output_format": "png"
    },
    "options": {
      "num_images": 4,
      "style": ["minimal", "modern", "tech"],
      "color_preferences": ["deep blue", "silver", "white"],
      "avoid": ["readable text", "busy details"],
      "quality": "standard",
      "seed": null
    },
    "metadata": {
      "notebook_id": "nb_001",
      "project_id": "p_001"
    }
  },
  "design_brief": {
    "title": "AI 产品设计方法论笔记图标",
    "intent": "为专业知识笔记本生成简洁、有科技感且易识别的图标",
    "subject": {
      "name": "AI 产品设计方法论",
      "domain": "technology / product design",
      "keywords": ["AI", "产品设计", "方法论", "知识沉淀"]
    },
    "audience": {
      "target_users": ["产品经理", "设计师", "技术团队"],
      "tone": ["professional", "clean", "modern"]
    },
    "visual_direction": {
      "style": ["minimal", "modern", "tech"],
      "symbol_ideas": ["abstract neural node", "notebook outline", "spark of insight"],
      "composition": "single central symbol, clear silhouette, readable at small size",
      "color_palette": ["deep blue", "white", "silver"],
      "background": "simple gradient or solid background"
    },
    "constraints": {
      "aspect_ratio": "1:1",
      "avoid_text": true,
      "transparent_background": false,
      "negative_prompt": [
        "readable text",
        "busy details",
        "photorealistic people",
        "watermark",
        "low contrast"
      ]
    }
  },
  "assets": [
    {
      "asset_id": "asset_001",
      "artifact_id": "art_001",
      "status": "ready",
      "kind": "image",
      "scene": "notebook_icon",
      "usage": "notebook_icon",
      "mime_type": "image/png",
      "width": 1024,
      "height": 1024,
      "preview_url": "/api/v1/artifacts/art_001/preview",
      "download_url": "/api/v1/artifacts/art_001/download",
      "selected": false,
      "review": {
        "status": "not_reviewed",
        "score": null,
        "issues": []
      }
    }
  ],
  "usage": {
    "prompt_tokens": 1200,
    "completion_tokens": 800,
    "total_tokens": 2000,
    "image_count": 4,
    "provider": "configured-image-provider"
  },
  "error": null,
  "attempt": 1,
  "max_attempts": 2,
  "created_at": "2026-06-23T10:00:00Z",
  "updated_at": "2026-06-23T10:00:18Z",
  "completed_at": null
}
```

## 7. 异步任务状态机

### 7.1 status

```text
queued
running
succeeded
failed
cancelled
```

### 7.2 stage

```text
queued
analyzing
prompting
generating
storing
succeeded
failed
cancelled
```

### 7.3 进度规则

```text
queued      0
analyzing   10
prompting   30
generating  50-85
storing     90
succeeded   100
failed      100
cancelled   100
```

如果图片 provider 不返回细粒度进度，`generating` 阶段按候选图完成数量估算：

```text
progress = 50 + generated_count / expected_count * 35
```

前端处理规则：

```text
status = queued/running
  -> 继续轮询

status = succeeded
  -> 停止轮询，展示 assets

status = failed
  -> 停止轮询，展示 error.message
  -> 如果 error.retryable=true，展示重新生成按钮

status = cancelled
  -> 停止轮询，展示已取消
```

## 8. Cancel 接口

```http
POST /api/v1/ai/visual-assets/jobs/{job_id}/cancel
```

请求：

```json
{
  "reason": "user_cancelled"
}
```

响应：

```json
{
  "job_id": "job_visual_001",
  "status": "cancelled",
  "stage": "cancelled",
  "progress": 100,
  "message": "任务已取消"
}
```

取消规则：

| 当前状态 | 行为 |
|---|---|
| queued | 直接 cancelled |
| analyzing | 尝试取消，成功后 cancelled |
| prompting | 尝试取消，成功后 cancelled |
| generating | 标记 cancel_requested；如果 provider 不支持取消，生成结束后不再注册新资产 |
| storing | 不强制中断，完成后可标记 succeeded |
| succeeded | 返回 409，不可取消 |
| failed | 返回 409，不可取消 |
| cancelled | 幂等返回 cancelled |

## 9. 图片存储和 Artifact Registry

### 9.1 存储原则

生成图片保存到 intelli-engine 后端产物区，对外不返回物理路径。

首版本地存储建议：

```text
backend/.deer-flow/users/{user_id}/outputs/visual-assets/{job_id}/{asset_id}.png
```

如果未来依赖会话，也可扩展为：

```text
backend/.deer-flow/users/{user_id}/threads/{conversation_id}/outputs/visual-assets/{job_id}/{asset_id}.png
```

外部只访问：

```text
artifact_id
preview_url
download_url
```

### 9.2 Artifact Metadata

```json
{
  "artifact_id": "art_001",
  "kind": "image",
  "mime_type": "image/png",
  "filename": "asset_001.png",
  "size_bytes": 245123,
  "width": 1024,
  "height": 1024,
  "owner": {
    "app_id": "notebook-app",
    "external_user_id": "user_001"
  },
  "storage": {
    "backend": "local",
    "key": "visual-assets/job_visual_001/asset_001.png"
  },
  "source": {
    "type": "visual_asset_job",
    "job_id": "job_visual_001",
    "asset_id": "asset_001",
    "scene": "notebook_icon",
    "usage": "notebook_icon"
  },
  "lifecycle": {
    "pinned": false,
    "ttl_days": 30,
    "expires_at": "2026-07-23T10:00:00Z"
  },
  "metadata": {
    "notebook_id": "nb_001",
    "project_id": "p_001"
  },
  "created_at": "2026-06-23T10:00:30Z"
}
```

对外查询 artifact metadata 时隐藏 `storage.key`。

### 9.3 前端保存什么

笔记本业务系统建议保存：

```json
{
  "notebook_id": "nb_001",
  "icon_artifact_id": "art_001",
  "icon_preview_url": "/api/v1/artifacts/art_001/preview",
  "icon_download_url": "/api/v1/artifacts/art_001/download"
}
```

优先保存 `artifact_id`，URL 可以缓存但不作为唯一主键。

## 10. VisualDesignBrief 与 Prompt 生成

### 10.1 核心链路

```text
用户输入
  -> visual-agent
  -> VisualDesignBrief
  -> PromptBuilder
  -> ImagePromptSpec
  -> ImageProvider
  -> 候选图片
```

### 10.2 VisualDesignBrief

`VisualDesignBrief` 是设计理解结果，面向业务解释、调试和后续迭代。

```json
{
  "title": "AI 产品设计方法论笔记本图标",
  "scene": "notebook_icon",
  "intent": "为一个专业知识笔记本生成简洁、有科技感且易识别的图标",
  "subject": {
    "name": "AI 产品设计",
    "domain": "technology / product design",
    "keywords": ["AI", "产品设计", "方法论", "知识沉淀"]
  },
  "audience": {
    "target_users": ["产品经理", "设计师", "技术团队"],
    "tone": ["professional", "clean", "modern"]
  },
  "visual_direction": {
    "style": ["minimal", "modern", "tech"],
    "symbol_ideas": ["abstract neural node", "notebook outline", "spark of insight"],
    "composition": "single central symbol, clear silhouette, readable at small size",
    "color_palette": ["deep blue", "white", "silver"],
    "background": "simple gradient or solid background"
  },
  "constraints": {
    "aspect_ratio": "1:1",
    "avoid_text": true,
    "transparent_background": false,
    "negative_prompt": [
      "readable text",
      "busy details",
      "photorealistic people",
      "watermark",
      "low contrast"
    ]
  }
}
```

### 10.3 ImagePromptSpec

`ImagePromptSpec` 是图片 provider 的执行输入。

```json
{
  "prompt": "Create a minimal modern notebook icon for an AI product design methodology notebook. Single central abstract symbol combining a notebook outline and neural nodes, clean silhouette, deep blue and silver palette, high contrast, suitable for small app icon, no readable text, no watermark.",
  "negative_prompt": "readable text, watermark, busy details, photorealistic people, cluttered composition, low contrast",
  "size": {
    "width": 1024,
    "height": 1024
  },
  "num_images": 4,
  "transparent_background": false,
  "output_format": "png"
}
```

### 10.4 PromptBuilder 原则

建议 `PromptBuilder` 为确定性模板，不完全依赖 LLM 直接写最终 prompt。

原因：

- 不同 scene 的约束不同。
- 图标需要小尺寸可识别。
- 背景需要留白，不抢内容。
- Logo 需要可缩放，类似品牌标志。
- prompt 调优不应影响外部 API。

## 11. Scene 策略

### 11.1 notebook_icon

重点：

- 小尺寸可识别。
- 单主体。
- 简洁轮廓。
- 高对比。
- 通常 1:1。

默认约束：

```text
single central symbol
clear silhouette
minimal details
high contrast
no readable text
no watermark
```

### 11.2 notebook_background

重点：

- 不抢内容区域。
- 可以抽象、氛围化。
- 避免明显文字。
- 通常 16:9、4:3 或业务指定尺寸。

默认约束：

```text
abstract background
soft composition
ample empty space
subtle texture
no readable text
no central logo
not too busy
```

### 11.3 logo

重点：

- 品牌识别。
- 可独立使用。
- 支持透明背景。
- 首版默认生成图形标志，不承诺准确文字。

默认约束：

```text
simple brand mark
vector-like
clear shape
scalable
transparent background if requested
avoid complex illustration
```

文字策略：

```text
默认不要求图片模型生成准确文字。
品牌名保留在 design_brief 中。
如需准确文字 Logo，二期通过 SVG/Canvas/Pillow 合成文字。
```

### 11.4 cover_image

重点：

- 视觉主题明确。
- 可作为报告、文章、知识库封面。
- 允许更丰富构图。
- 仍避免水印和乱码文字。

## 12. Job Store

建议新增独立 Job Store。

推荐 DB 表：

```text
v1_visual_asset_jobs
```

字段建议：

```text
job_id              string primary key
type                string
scene               string
status              string
stage               string
progress            int
message             text
app_id              string
external_user_id    string nullable
request_json        json/text
design_brief_json   json/text nullable
assets_json         json/text
error_json          json/text nullable
attempt             int
max_attempts        int
created_at          datetime
updated_at          datetime
completed_at        datetime nullable
```

如果短期不做 DB，也可以首版落文件：

```text
backend/.deer-flow/v1/jobs/visual-assets/{job_id}.json
```

但更推荐 DB，因为 job 查询、权限过滤、重启恢复、清理任务都更稳定。

## 13. Worker 设计

首版可采用同进程 async worker。

```text
POST /generate
  -> 写入 job，status=queued
  -> 返回 job_id

Worker loop
  -> 扫描 queued jobs
  -> claim job
  -> analyzing
  -> prompting
  -> generating
  -> storing
  -> succeeded/failed
```

重启恢复：

- `queued` 任务继续可被 worker 扫描执行。
- `running` 任务如果超过 `running_timeout_seconds` 未更新，标记为 failed 或重新入队。
- `succeeded/failed/cancelled` 保持可查询。

## 14. 配置设计

建议在 `config.yaml` 增加：

```yaml
visual_assets:
  enabled: true

  job:
    backend: database
    max_attempts: 2
    running_timeout_seconds: 600
    cleanup_interval_seconds: 3600

  generation:
    default_num_images: 4
    max_num_images: 4
    default_quality: standard
    default_output_format: png
    allowed_output_formats:
      - png
    allowed_scenes:
      - logo
      - notebook_icon
      - notebook_background
      - cover_image
      - general_image

  retention:
    default_ttl_days: 30
    pinned_ttl_days: 3650
    cleanup_enabled: true

  storage:
    backend: local
    local:
      base_dir: visual-assets

  image_provider:
    type: mock
    model: mock-image
    timeout_seconds: 120

  design_agent:
    provider: default
    model: default
    max_retries: 1

  safety:
    reject_brand_imitation: true
    reject_copyright_character: true
    reject_sensitive_content: true
    allow_text_in_image: false
    log_full_prompt: false

  limits:
    max_input_chars: 4000
    max_metadata_bytes: 8192
    max_concurrent_jobs_per_user: 3
    max_concurrent_jobs_per_app: 20
    max_jobs_per_app_per_minute: 30
```

## 15. Capabilities

建议扩展 `/api/v1/capabilities`：

```json
{
  "visual_assets": {
    "enabled": true,
    "async": true,
    "scenes": [
      "logo",
      "notebook_icon",
      "notebook_background",
      "cover_image",
      "general_image"
    ],
    "max_num_images": 4,
    "artifact_output": true
  },
  "logo": {
    "image_generate": true,
    "via": "visual_assets",
    "accurate_text_supported": false
  }
}
```

## 16. 错误设计

### 16.1 HTTP 层错误

请求未创建成功时返回 HTTP 错误。

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "num_images must be between 1 and 4",
    "request_id": "req_001",
    "details": {
      "field": "options.num_images"
    }
  }
}
```

建议错误码：

```text
UNAUTHORIZED
FORBIDDEN
INVALID_REQUEST
UNSUPPORTED_SCENE
UNSUPPORTED_IMAGE_SIZE
RATE_LIMITED
CONCURRENT_LIMIT_EXCEEDED
JOB_NOT_FOUND
ARTIFACT_NOT_FOUND
```

### 16.2 Job 层错误

任务已创建但执行失败时，`GET job` 返回 HTTP 200，job 内部状态为 failed。

```json
{
  "job_id": "job_visual_001",
  "status": "failed",
  "stage": "generating",
  "progress": 100,
  "message": "图片生成失败",
  "error": {
    "code": "IMAGE_PROVIDER_TIMEOUT",
    "message": "图片生成服务超时，请稍后重试",
    "retryable": true,
    "details": {
      "provider": "openai",
      "timeout_seconds": 120
    }
  },
  "assets": []
}
```

Job 错误码：

```text
DESIGN_AGENT_ERROR
DESIGN_BRIEF_INVALID
PROMPT_BUILD_FAILED
CONTENT_POLICY_REJECTED
IMAGE_PROVIDER_ERROR
IMAGE_PROVIDER_TIMEOUT
IMAGE_PROVIDER_RATE_LIMIT
IMAGE_PROVIDER_INVALID_RESPONSE
IMAGE_DOWNLOAD_FAILED
ARTIFACT_STORAGE_FAILED
ARTIFACT_REGISTER_FAILED
JOB_CANCELLED
JOB_TIMEOUT
UNKNOWN_ERROR
```

### 16.3 部分成功

如果生成 4 张，成功 2 张，建议首版视为 `succeeded`，但带 warning。

```json
{
  "status": "succeeded",
  "progress": 100,
  "message": "已生成 2/4 张候选图",
  "warning": {
    "code": "PARTIAL_GENERATION",
    "message": "部分候选图生成失败",
    "retryable": true
  }
}
```

如果 0 张成功，则 job failed。

## 17. 安全策略

首版必须做：

- 输入长度限制。
- metadata 大小限制。
- scene、size、num_images 校验。
- Logo 场景拒绝品牌仿冒。
- 拒绝版权角色请求。
- 默认避免 readable text。
- 不记录完整 prompt。
- job/artifact 按 `app_id`、`external_user_id` 权限隔离。

典型拒绝场景：

```text
帮我做一个像 Apple 一样的 Logo
生成一个和 Starbucks 很像的咖啡 Logo
做一个 Nike 风格但换个名字
做一个皮卡丘风格的笔记图标
```

拒绝响应：

```json
{
  "error": {
    "code": "BRAND_IMPERSONATION_REJECTED",
    "message": "不能生成模仿真实品牌标识的 Logo，请改用通用风格描述，例如：简洁、科技感、高端、温暖。"
  }
}
```

## 18. 服务端模块拆分

推荐首版文件结构：

```text
backend/app/gateway/routers/v1/
  visual_assets.py
  artifacts.py

backend/app/gateway/schemas/v1/
  visual_assets.py
  artifacts.py

backend/app/gateway/v1_services/
  visual_asset_service.py
  visual_asset_job_store.py
  visual_design_agent.py
  visual_prompt_builder.py
  image_provider.py
  artifact_service.py
  artifact_store.py
```

可选 Logo wrapper：

```text
backend/app/gateway/routers/v1/ai_logo.py
backend/app/gateway/schemas/v1/ai_logo.py
```

依赖关系：

```text
Router
  -> VisualAssetService
      -> VisualAssetJobStore
      -> VisualDesignAgent
      -> VisualPromptBuilder
      -> ImageProvider
      -> ArtifactService
          -> ArtifactStore
          -> StorageBackend
```

## 19. 阶段计划

### Phase A：视觉资产生成最小闭环

目标：让笔记本场景能生成 1-4 张候选图，并通过 artifact 预览/下载。

范围：

- `POST /api/v1/ai/visual-assets/generate`
- `GET /api/v1/ai/visual-assets/jobs/{job_id}`
- `POST /api/v1/ai/visual-assets/jobs/{job_id}/cancel`
- `GET /api/v1/artifacts/{artifact_id}`
- `GET /api/v1/artifacts/{artifact_id}/preview`
- `GET /api/v1/artifacts/{artifact_id}/download`
- 支持 `notebook_icon`、`notebook_background`、`logo`。
- 支持异步 job。
- 支持本地文件存储。
- 支持 artifact registry。
- 支持 mock image provider。
- 支持 capabilities 返回 visual_assets enabled。

不做：

- 不做准确文字 Logo。
- 不做 vision review。
- 不做对象存储。
- 不做 job SSE。
- 不做复杂 retry 接口。
- 不做业务系统绑定。

验收标准：

- 创建 job 返回 `job_id`。
- 查询 job 能看到 progress 从 0 到 100。
- succeeded 后返回 1-4 个 assets。
- 每个 asset 有 `artifact_id`、`preview_url`、`download_url`。
- preview/download 能拿到图片。
- 前端能把 artifact_id 保存为笔记本图标或背景。

### Phase B：质量、安全和生产化

目标：让能力更稳定、可控，适合 dev/prod 环境。

范围：

- 真实 image provider 接入。
- provider timeout/retry。
- 输入安全策略。
- 品牌仿冒拒绝。
- 版权角色拒绝。
- metadata 大小限制。
- app/user 权限隔离。
- artifact pin/unpin。
- TTL 清理任务。
- job stuck 恢复。
- rate limit / concurrent limit。
- OpenAPI security scheme。
- 更完整错误码。

验收标准：

- 违规请求被拒绝。
- 超限返回 429。
- pinned artifact 不被清理。
- job 服务重启后仍可查询。
- 不同 app/user 不能互查 job/artifact。
- provider 失败时返回标准错误码。

### Phase C：设计增强和多轮迭代

目标：从“生成图片”升级为“设计工作流”。

范围：

- `POST /api/v1/ai/visual-assets/jobs/{job_id}/retry`
- `POST /api/v1/ai/visual-assets/jobs/{job_id}/assets/{asset_id}/select`
- 基于上一版生成变体。
- 支持用户反馈继续调整。
- vision review。
- Logo 准确文字合成。
- SVG/透明背景优化。
- 对象存储。
- job events SSE。

验收标准：

- 用户能基于某张候选图继续生成变体。
- selected asset 可被记录。
- Logo 可生成准确品牌文字版本。
- 支持对象存储且 API 不变。

## 20. 与现有 v1 平台的关系

当前 `/api/v1` 已有：

```text
conversations
agents
runs
data_sources
capabilities
```

本设计建议新增：

```text
visual_assets
artifacts
```

并将原计划中的 `ai_logo` 从单一能力提升为 `visual_assets` 的一个 scene。

当前 capabilities 中 `logo.image_generate=false`，待 Phase A 完成后可调整为：

```json
{
  "visual_assets": {
    "enabled": true
  },
  "logo": {
    "image_generate": true,
    "via": "visual_assets",
    "accurate_text_supported": false
  }
}
```

