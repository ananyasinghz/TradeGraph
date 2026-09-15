"""Source connection registry, scheduled fetch, live-feed honesty flags."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_source_connections"
down_revision = "0006_r2_r3_ops"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source_connections",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("publisher", sa.String(length=256), nullable=False),
        sa.Column(
            "fetch_mode",
            sa.String(length=32),
            nullable=False,
            server_default="curated_mirror",
        ),
        sa.Column("source_url", sa.String(length=1024), nullable=True),
        sa.Column("local_path", sa.String(length=1024), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("origin", sa.String(length=2), nullable=False, server_default="BD"),
        sa.Column("destination", sa.String(length=2), nullable=False, server_default="IN"),
        sa.Column("hs_chapter", sa.String(length=4), nullable=False, server_default="61"),
        sa.Column(
            "adapter",
            sa.String(length=64),
            nullable=False,
            server_default="curated_json_mirror",
        ),
        sa.Column(
            "honesty_label",
            sa.String(length=128),
            nullable=False,
            server_default="Official-source-backed curated mirror",
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_checksum", sa.String(length=128), nullable=True),
        sa.Column("last_archive_path", sa.String(length=1024), nullable=True),
        sa.Column("last_source_document_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_source_connections_key", "source_connections", ["key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_source_connections_key", table_name="source_connections")
    op.drop_table("source_connections")
