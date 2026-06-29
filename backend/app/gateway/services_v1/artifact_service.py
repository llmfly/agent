"""Artifact service - manages the database persistence for V1 artifacts."""

from __future__ import annotations

import logging
import uuid
import mimetypes
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from deerflow.persistence.engine import get_session_factory
from deerflow.persistence.models.artifact import ArtifactRow, ArtifactFileRow

logger = logging.getLogger(__name__)


# ── Legacy / In-Memory Artifacts (Used by Visual Assets) ────────────────────

@dataclass
class ArtifactRecord:
    artifact_id: str
    file_path: str
    kind: str
    mime_type: str
    filename: str
    size_bytes: int
    app_id: str
    external_user_id: str | None
    width: int | None = None
    height: int | None = None
    pinned: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    @property
    def preview_url(self) -> str:
        return f"/api/v1/artifacts/{self.artifact_id}/preview"

    @property
    def download_url(self) -> str:
        return f"/api/v1/artifacts/{self.artifact_id}/download"


_artifacts: dict[str, ArtifactRecord] = {}


def register_existing_artifact(
    artifact_id: str,
    file_path: str,
    *,
    app_id: str = "legacy",
    external_user_id: str | None = None,
) -> ArtifactRecord:
    path = Path(file_path)
    record = ArtifactRecord(
        artifact_id=artifact_id,
        file_path=str(path),
        kind="file",
        mime_type="application/octet-stream",
        filename=path.name,
        size_bytes=path.stat().st_size if path.exists() else 0,
        app_id=app_id,
        external_user_id=external_user_id,
    )
    _artifacts[artifact_id] = record
    return record


def get_artifact(artifact_id: str) -> ArtifactRecord | None:
    return _artifacts.get(artifact_id)


def is_artifact_visible_to(
    record: ArtifactRecord,
    *,
    app_id: str,
    external_user_id: str | None,
) -> bool:
    if record.app_id == "legacy":
        return True
    return record.app_id == app_id and record.external_user_id == external_user_id


def set_artifact_pinned(artifact_id: str, *, pinned: bool) -> ArtifactRecord | None:
    record = get_artifact(artifact_id)
    if record is None:
        return None
    record.pinned = pinned
    return record


def create_image_artifact(
    *,
    base_dir: Path,
    app_id: str,
    external_user_id: str | None,
    job_id: str,
    asset_id: str,
    image_bytes: bytes,
    mime_type: str,
    width: int,
    height: int,
    metadata: dict[str, Any],
) -> ArtifactRecord:
    artifact_id = f"art_{uuid.uuid4().hex[:12]}"
    target_dir = base_dir / "visual-assets" / job_id
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{asset_id}.png"
    file_path = target_dir / filename
    file_path.write_bytes(image_bytes)
    record = ArtifactRecord(
        artifact_id=artifact_id,
        file_path=str(file_path),
        kind="image",
        mime_type=mime_type,
        filename=filename,
        size_bytes=len(image_bytes),
        app_id=app_id,
        external_user_id=external_user_id,
        width=width,
        height=height,
        metadata=metadata,
    )
    _artifacts[artifact_id] = record
    return record


# ── DB-backed Artifacts (Option B - Used by Reports and Multi-format Files) ──

class ArtifactService:
    """Manages the creation, status updates, and queries of V1 artifacts."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession] | None = None) -> None:
        self._session_factory = session_factory

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession] | None:
        if self._session_factory is None:
            self._session_factory = get_session_factory()
        return self._session_factory

    async def create_artifact(
        self,
        conversation_id: str,
        name: str,
        artifact_type: str,
        run_id: str | None = None,
        meta_json: dict | None = None,
        artifact_id: str | None = None,
    ) -> str:
        """Create a new artifact record (status defaults to processing)."""
        if artifact_id is None:
            artifact_id = f"art_{uuid.uuid4().hex[:12]}"
        
        sf = self.session_factory
        if sf is None:
            logger.warning("No database session factory initialized. Artifact will not be persisted.")
            return artifact_id

        async with sf() as session:
            async with session.begin():
                row = ArtifactRow(
                    artifact_id=artifact_id,
                    conversation_id=conversation_id,
                    run_id=run_id,
                    artifact_type=artifact_type,
                    name=name,
                    status="processing",
                    meta_json=meta_json or {},
                )
                session.add(row)
        logger.info("Created artifact record: %s (type=%s, conversation_id=%s)", artifact_id, artifact_type, conversation_id)
        return artifact_id

    async def add_artifact_file(
        self,
        artifact_id: str,
        file_format: str,
        filename: str,
        file_path: str,
        download_url: str,
        file_size: int | None = None,
        file_id: str | None = None,
    ) -> str:
        """Add a file to an existing artifact."""
        if file_id is None:
            file_id = f"art_file_{uuid.uuid4().hex[:12]}"
        sf = self.session_factory
        if sf is None:
            return file_id

        async with sf() as session:
            async with session.begin():
                file_row = ArtifactFileRow(
                    file_id=file_id,
                    artifact_id=artifact_id,
                    file_format=file_format,
                    filename=filename,
                    file_path=file_path,
                    download_url=download_url,
                    file_size=file_size,
                )
                session.add(file_row)
        logger.info("Added file %s to artifact %s (format=%s)", file_id, artifact_id, file_format)
        return file_id

    async def update_artifact_status(
        self,
        artifact_id: str,
        status: str,
        error_message: str | None = None,
        meta_json: dict | None = None,
    ) -> None:
        """Update artifact status (processing -> success/failed)."""
        sf = self.session_factory
        if sf is None:
            return

        async with sf() as session:
            async with session.begin():
                stmt = select(ArtifactRow).where(ArtifactRow.artifact_id == artifact_id)
                row = (await session.execute(stmt)).scalar_one_or_none()
                if row:
                    row.status = status
                    if error_message is not None:
                        row.error_message = error_message
                    if meta_json is not None:
                        row.meta_json = {**row.meta_json, **meta_json}
        logger.info("Updated artifact status: %s -> %s", artifact_id, status)

    async def get_artifact(self, artifact_id: str) -> ArtifactRow | None:
        """Fetch artifact record with its files preloaded."""
        sf = self.session_factory
        if sf is None:
            return None

        from sqlalchemy.orm import selectinload
        async with sf() as session:
            stmt = (
                select(ArtifactRow)
                .where(ArtifactRow.artifact_id == artifact_id)
                .options(selectinload(ArtifactRow.files))
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_artifact_file(self, file_id: str) -> ArtifactFileRow | None:
        """Fetch artifact file details by file ID."""
        sf = self.session_factory
        if sf is None:
            return None

        async with sf() as session:
            stmt = select(ArtifactFileRow).where(ArtifactFileRow.file_id == file_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def list_conversation_artifacts(self, conversation_id: str) -> list[ArtifactRow]:
        """List all artifacts for a given conversation, preloading files."""
        sf = self.session_factory
        if sf is None:
            return []

        from sqlalchemy.orm import selectinload
        async with sf() as session:
            stmt = (
                select(ArtifactRow)
                .where(ArtifactRow.conversation_id == conversation_id)
                .options(selectinload(ArtifactRow.files))
                .order_by(ArtifactRow.created_at.desc())
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())


# Singleton
artifact_service = ArtifactService()
