from __future__ import annotations

import json
import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi import Path as FPath
from fastapi.responses import FileResponse, PlainTextResponse, Response

from app.gateway.schemas.v1.artifacts import ArtifactMetadataResponse
from app.gateway.services_v1.artifact_service import (
    ArtifactRecord,
    get_artifact,
    is_artifact_visible_to,
    register_existing_artifact,
    set_artifact_pinned,
)
from app.gateway.services_v1.external_context import ExternalContext, get_optional_context

router = APIRouter(prefix="/artifacts", tags=["v1-artifacts"])

_artifact_registry: dict[str, str] = {}


def register_artifact(artifact_id: str, file_path: str) -> None:
    _artifact_registry[artifact_id] = file_path
    register_existing_artifact(artifact_id, file_path)


def get_artifact_file_path(artifact_id: str) -> str | None:
    record = get_artifact(artifact_id)
    if record is not None:
        return record.file_path
    return _artifact_registry.get(artifact_id)


async def _get_artifact_record_from_db(artifact_id: str, context: ExternalContext) -> ArtifactRecord | None:
    from app.gateway.services_v1.artifact_service import artifact_service
    
    # 1. Try to find as a file_id in DB
    file_row = await artifact_service.get_artifact_file(artifact_id)
    if file_row:
        art_row = await artifact_service.get_artifact(file_row.artifact_id)
        if art_row:
            return ArtifactRecord(
                artifact_id=file_row.file_id,
                file_path=file_row.file_path,
                kind=art_row.artifact_type,
                mime_type="application/octet-stream",
                filename=file_row.filename,
                size_bytes=file_row.file_size or 0,
                app_id=context.app_id,
                external_user_id=context.external_user_id,
            )
            
    # 2. Try to find as an artifact_id in DB
    art_row = await artifact_service.get_artifact(artifact_id)
    if art_row and art_row.files:
        file_row = art_row.files[0]
        return ArtifactRecord(
            artifact_id=art_row.artifact_id,
            file_path=file_row.file_path,
            kind=art_row.artifact_type,
            mime_type="application/octet-stream",
            filename=file_row.filename,
            size_bytes=file_row.file_size or 0,
            app_id=context.app_id,
            external_user_id=context.external_user_id,
        )
    return None


def _get_deerflow_base() -> Path:
    from deerflow.config.paths import get_paths
    return get_paths().base_dir


def _get_visual_asset_record_from_job_store(artifact_id: str, context: ExternalContext, request: Request) -> ArtifactRecord | None:
    base = _get_deerflow_base()
    job_dir = Path(getattr(request.app.state, "v1_visual_asset_job_dir", base / "v1" / "jobs" / "visual-assets"))
    artifact_base_dir = Path(getattr(request.app.state, "v1_artifact_base_dir", base / "v1" / "artifacts"))
    if not job_dir.exists():
        return None

    for path in job_dir.glob("*.json"):
        try:
            job = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        owner = job.get("owner") or {}
        if owner.get("app_id") != context.app_id or owner.get("external_user_id") != context.external_user_id:
            continue

        for asset in job.get("assets") or []:
            if asset.get("artifact_id") != artifact_id:
                continue
            asset_id = asset.get("asset_id")
            if not asset_id:
                return None
            file_path = artifact_base_dir / "visual-assets" / job.get("job_id", "") / f"{asset_id}.png"
            if not file_path.exists():
                return None
            return ArtifactRecord(
                artifact_id=artifact_id,
                file_path=str(file_path),
                kind=asset.get("kind") or "image",
                mime_type=asset.get("mime_type") or mimetypes.guess_type(file_path)[0] or "application/octet-stream",
                filename=file_path.name,
                size_bytes=file_path.stat().st_size,
                app_id=context.app_id,
                external_user_id=context.external_user_id,
                width=asset.get("width"),
                height=asset.get("height"),
                metadata={
                    **((job.get("request") or {}).get("metadata") or {}),
                    "job_id": job.get("job_id"),
                    "asset_id": asset_id,
                    "scene": job.get("scene"),
                },
                created_at=job.get("created_at") or path.stat().st_mtime_ns.__str__(),
            )
    return None


async def _record_or_legacy(artifact_id: str, context: ExternalContext, request: Request):
    # Try DB first
    db_record = await _get_artifact_record_from_db(artifact_id, context)
    if db_record is not None:
        return db_record

    # Fallback to in-memory/legacy
    record = get_artifact(artifact_id)
    if record is not None:
        if not is_artifact_visible_to(record, app_id=context.app_id, external_user_id=context.external_user_id):
            raise HTTPException(status_code=404, detail=f"Artifact {artifact_id} not found")
        return record
    legacy_path = _artifact_registry.get(artifact_id)
    if legacy_path is None:
        visual_asset_record = _get_visual_asset_record_from_job_store(artifact_id, context, request)
        if visual_asset_record is None:
            raise HTTPException(status_code=404, detail=f"Artifact {artifact_id} not found")
        return visual_asset_record
    return register_existing_artifact(artifact_id, legacy_path)


async def _file_response(artifact_id: str, context: ExternalContext, request: Request, *, download: bool) -> Response:
    record = await _record_or_legacy(artifact_id, context, request)
    actual_path = Path(record.file_path)
    if not actual_path.exists() or not actual_path.is_file():
        raise HTTPException(status_code=404, detail=f"Artifact file not found on disk: {artifact_id}")
    mime_type = record.mime_type or mimetypes.guess_type(actual_path)[0]
    if mime_type in {"text/html", "application/xhtml+xml"}:
        headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{record.filename}"}
        return Response(content=actual_path.read_bytes(), media_type=mime_type, headers=headers)
    if download:
        return FileResponse(path=actual_path, filename=record.filename, media_type=mime_type)
    if mime_type and mime_type.startswith("text/"):
        return PlainTextResponse(content=actual_path.read_text(encoding="utf-8"), media_type=mime_type)
    return FileResponse(path=actual_path, filename=record.filename, media_type=mime_type)


def _metadata_response(record) -> ArtifactMetadataResponse:
    return ArtifactMetadataResponse(
        artifact_id=record.artifact_id,
        kind=record.kind,
        mime_type=record.mime_type,
        filename=record.filename,
        size_bytes=record.size_bytes,
        width=record.width,
        height=record.height,
        pinned=record.pinned,
        preview_url=record.preview_url,
        download_url=record.download_url,
        metadata=record.metadata,
        created_at=record.created_at,
    )


@router.get("/{artifact_id}", response_model=ArtifactMetadataResponse)
async def get_artifact_metadata(
    request: Request,
    artifact_id: str = FPath(description="Artifact ID"),
    download: bool = False,
    context: ExternalContext = Depends(get_optional_context),
) -> ArtifactMetadataResponse | Response:
    if download:
        return await _file_response(artifact_id, context, request, download=True)
    record = await _record_or_legacy(artifact_id, context, request)
    return _metadata_response(record)


@router.get("/{artifact_id}/preview")
async def preview_artifact(
    request: Request,
    artifact_id: str = FPath(description="Artifact ID"),
    context: ExternalContext = Depends(get_optional_context),
) -> Response:
    return await _file_response(artifact_id, context, request, download=False)


@router.get("/{artifact_id}/download")
async def download_artifact(
    request: Request,
    artifact_id: str = FPath(description="Artifact ID"),
    context: ExternalContext = Depends(get_optional_context),
) -> Response:
    return await _file_response(artifact_id, context, request, download=True)


@router.post("/{artifact_id}/pin", response_model=ArtifactMetadataResponse)
async def pin_artifact(
    request: Request,
    artifact_id: str = FPath(description="Artifact ID"),
    context: ExternalContext = Depends(get_optional_context),
) -> ArtifactMetadataResponse:
    await _record_or_legacy(artifact_id, context, request)
    record = set_artifact_pinned(artifact_id, pinned=True)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Artifact {artifact_id} not found")
    return _metadata_response(record)


@router.post("/{artifact_id}/unpin", response_model=ArtifactMetadataResponse)
async def unpin_artifact(
    request: Request,
    artifact_id: str = FPath(description="Artifact ID"),
    context: ExternalContext = Depends(get_optional_context),
) -> ArtifactMetadataResponse:
    await _record_or_legacy(artifact_id, context, request)
    record = set_artifact_pinned(artifact_id, pinned=False)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Artifact {artifact_id} not found")
    return _metadata_response(record)
