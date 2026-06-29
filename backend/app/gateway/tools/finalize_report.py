"""finalize_report — unified tool for persisting report artifacts.

All three report generation paths must call this tool at the end:
  Path 1 (generate_report / report_workflow) → built-in, uses _finalize_report
  Path 2 (company-insight-report skill)      → LLM should call this tool
  Path 3 (Lead Agent direct)                 → LLM should call this tool

This ensures all artifacts are stored at:
  {DEER_FLOW_HOME}/users/{user_id}/threads/{conversation_id}/outputs/reports/
and registered in both DB and in-memory for restart-safe access.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.tools import tool

from deerflow.config.paths import get_paths
from deerflow.tools.types import Runtime

logger = logging.getLogger(__name__)


def _get_thread_id(runtime: Runtime) -> str | None:
    thread_id = runtime.context.get("thread_id") if runtime.context else None
    if thread_id:
        return thread_id
    cfg = getattr(runtime, "config", None) or {}
    thread_id = cfg.get("configurable", {}).get("thread_id")
    if thread_id:
        return thread_id
    try:
        from langgraph.config import get_config
        return get_config().get("configurable", {}).get("thread_id")
    except RuntimeError:
        return None


def _get_user_id(runtime: Runtime) -> str:
    if runtime.context:
        uid = runtime.context.get("user_id")
        if uid:
            return uid
    return "anonymous"


def _slugify(text: str) -> str:
    import re
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "_", text)
    return text.strip("_")[:80]


@tool(parse_docstring=True)
async def finalize_report(
    filepath: str,
    runtime: Runtime,
    title: str = "",
    file_format: str = "docx",
) -> str:
    """统一保存最终报告产物，返回可下载的 artifact URL。

    无论通过何种路径生成的报告（Skill、直接写文件、generate_report），
    都必须在**最后一步**调用此工具，将报告文件注册为持久化 artifact。

    调用此工具后，报告会保存到统一存储位置：
      {DEER_FLOW_HOME}/users/.../threads/.../outputs/reports/{slug}_{timestamp}.{format}

    重启后仍可通过返回的 URL 下载。

    Args:
        filepath: 报告文件的路径。可以是沙箱路径（/mnt/user-data/outputs/report.docx）
                 或宿主机绝对路径。
        title: 报告标题，用于生成文件名。默认使用文件名。
        file_format: 文件格式。可选: docx, html。默认为 docx。
    """
    conversation_id = _get_thread_id(runtime)
    user_id = _get_user_id(runtime)

    if not conversation_id:
        return "错误：无法获取当前对话 ID。"

    # ── 1. Resolve actual file path ──────────────────────────────
    actual_path: Path
    if filepath.startswith("/mnt/user-data/"):
        # Sandbox virtual path → resolve to host path
        from deerflow.config.paths import VIRTUAL_PATH_PREFIX

        virtual_path = filepath.lstrip("/")
        stripped_prefix = VIRTUAL_PATH_PREFIX.lstrip("/")
        if virtual_path.startswith(stripped_prefix + "/") or virtual_path == stripped_prefix:
            rel = virtual_path[len(stripped_prefix):].lstrip("/")
            thread_dir = get_paths().thread_dir(conversation_id, user_id=user_id)
            actual_path = thread_dir / "user-data" / rel
        else:
            actual_path = Path(filepath)
    else:
        actual_path = Path(filepath).expanduser().resolve()

    if not actual_path.exists() or not actual_path.is_file():
        return f"错误：找不到文件: {filepath}"

    # ── 2. Read file content ─────────────────────────────────────
    file_content = actual_path.read_bytes()

    # ── 3. Determine filename ─────────────────────────────────────
    slug = _slugify(title or actual_path.stem)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    ext = file_format.lstrip(".")
    filename = f"{slug}_{ts}.{ext}"
    artifact_id = f"art_{uuid.uuid4().hex[:12]}"
    download_url = f"/api/v1/artifacts/{artifact_id}"

    # ── 4. Save to unified location ───────────────────────────────
    base = get_paths().base_dir
    output_dir = base / "users" / user_id / "threads" / conversation_id / "outputs" / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    dest_path = output_dir / filename
    dest_path.write_bytes(file_content)

    logger.info(
        "路径 2/3 [finalize_report]: artifact=%s file=%s -> %s",
        artifact_id, filepath, dest_path,
    )

    # ── 5. Register artifact (DB + memory) ────────────────────────
    from app.gateway.routers.v1.artifacts import register_artifact
    from app.gateway.services_v1.artifact_service import artifact_service

    register_artifact(artifact_id, str(dest_path))

    try:
        await artifact_service.create_artifact(
            conversation_id=conversation_id,
            name=title or actual_path.stem,
            artifact_type="report",
            artifact_id=artifact_id,
            meta_json={"title": title, "format": ext, "source": "finalize_report"},
        )
        await artifact_service.add_artifact_file(
            artifact_id=artifact_id,
            file_format=ext,
            filename=filename,
            file_path=str(dest_path),
            download_url=download_url,
            file_size=len(file_content),
            file_id=artifact_id,
        )
    except Exception as e:
        logger.warning("Failed to persist artifact to DB: %s", e)

    return (
        f"✅ 报告已保存！\n"
        f"   - 下载: {download_url}\n"
        f"   - 格式: {ext.upper()}\n"
        f"   - 文件: {filename}"
    )
