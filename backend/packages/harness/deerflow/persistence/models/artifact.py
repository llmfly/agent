"""ORM models for V1 artifacts."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from deerflow.persistence.base import Base


class ArtifactRow(Base):
    """Artifact record table - compatible with reports, APIs, apps, images, etc."""

    __tablename__ = "v1_artifacts"

    artifact_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("threads_meta.thread_id", ondelete="CASCADE"),
        index=True,
    )
    run_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)

    # Artifact type: "report", "api", "app", "image", etc.
    artifact_type: Mapped[str] = mapped_column(String(20), index=True)

    name: Mapped[str] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(20), default="processing")  # queued, processing, success, failed
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    meta_json: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    files = relationship(
        "ArtifactFileRow",
        back_populates="artifact",
        cascade="all, delete-orphan",
    )


class ArtifactFileRow(Base):
    """Physical file table associated with an artifact (e.g. report files, images)."""

    __tablename__ = "v1_artifact_files"

    file_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    artifact_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("v1_artifacts.artifact_id", ondelete="CASCADE"),
        index=True,
    )

    file_format: Mapped[str] = mapped_column(String(10))  # docx, html, pdf, png, etc.
    filename: Mapped[str] = mapped_column(String(256))
    file_path: Mapped[str] = mapped_column(String(512))
    download_url: Mapped[str] = mapped_column(String(512))
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    # Relationships
    artifact = relationship("ArtifactRow", back_populates="files")
