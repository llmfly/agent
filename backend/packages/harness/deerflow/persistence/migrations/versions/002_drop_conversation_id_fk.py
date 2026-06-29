"""Drop FK constraint on conversation_datasource.conversation_id.

The FK referencing threads_meta.thread_id is too restrictive: conversations
(LangGraph threads) may not have a corresponding threads_meta entry when a
data source is attached. conversation_id becomes a plain indexed column.

Uses drop-and-recreate since SQLite batch mode requires know the auto-generated
FK name, which is opaque in SQLite.

Revision ID: 002
Revises: 001
Create Date: 2026-06-29
"""

from __future__ import annotations

from typing import ClassVar

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: str | None = "001"
branch_labels: ClassVar[set[str] | None] = None
depends_on: ClassVar[set[str] | None] = None


def upgrade() -> None:
    # Drop and recreate the table (SQLite cannot ALTER DROP CONSTRAINT).
    # Safe because conversation_datasource is a new table with no production data.
    op.drop_table("conversation_datasource")
    op.create_table(
        "conversation_datasource",
        sa.Column("id", sa.String(64), nullable=False),
        sa.Column("conversation_id", sa.String(64), nullable=False, index=True),
        sa.Column(
            "datasource_id",
            sa.String(64),
            sa.ForeignKey("datasource.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("alias", sa.String(128), nullable=True),
        sa.Column("mount_path", sa.String(256), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("conversation_datasource")
    op.create_table(
        "conversation_datasource",
        sa.Column("id", sa.String(64), nullable=False),
        sa.Column(
            "conversation_id",
            sa.String(64),
            sa.ForeignKey("threads_meta.thread_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "datasource_id",
            sa.String(64),
            sa.ForeignKey("datasource.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("alias", sa.String(128), nullable=True),
        sa.Column("mount_path", sa.String(256), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
