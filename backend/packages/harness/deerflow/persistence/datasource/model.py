"""ORM models for Data Source Management.

See ``docs/design/data-source-management.md`` for the full design document.

Three-layer architecture:
  User
   │ owns
   ▼
  DataSource                    ← data asset, owned by user
   │ referenced by
   ▼
  ConversationDataSource        ← reference, belongs to conversation
   │
   ▼
  Conversation (threads_meta)
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from deerflow.persistence.base import Base


class DataSourceRow(Base):
    """Data asset owned by a user.

    Supports structured (MySQL, PostgreSQL, ES), object storage (MinIO, S3),
    and file types (PDF, DOCX, TXT, XLSX, CSV). Configuration is stored in
    ``config_json`` as JSONB.
    """

    __tablename__ = "datasource"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True, default="")

    # Type: mysql / postgresql / clickhouse / es / minio / s3 /
    #       pdf / docx / txt / markdown / xlsx / csv / ppt
    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    # Status: uploading / parsing / embedding / ready / error / connected
    status: Mapped[str] = mapped_column(String(20), default="ready")

    icon: Mapped[str | None] = mapped_column(String(64), nullable=True, default="")

    # Config stored as JSON — dialect-agnostic using String for SQLite compat
    config_json: Mapped[dict | None] = mapped_column(JSONB().with_variant(String, "sqlite"), nullable=True, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)


class ConversationDataSourceRow(Base):
    """Reference from a conversation to a data source.

    Supports alias renaming so the Agent sees a friendly name
    (e.g. "订单库" instead of "mysql_prod").
    """

    __tablename__ = "conversation_datasource"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("threads_meta.thread_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    datasource_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("datasource.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    # Alias shown to the Agent (e.g. "订单库" instead of "mysql_prod")
    alias: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Mount path for file-type data sources
    mount_path: Mapped[str | None] = mapped_column(String(256), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    # ORM relationships
    datasource = relationship("DataSourceRow", lazy="joined")
