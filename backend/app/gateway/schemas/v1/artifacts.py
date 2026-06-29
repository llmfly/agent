from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ArtifactMetadataResponse(BaseModel):
    artifact_id: str
    kind: str
    mime_type: str
    filename: str
    size_bytes: int
    width: int | None = None
    height: int | None = None
    pinned: bool = False
    preview_url: str
    download_url: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
