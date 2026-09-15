"""Phase 4: ingestion batches, proposals, data versions."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_phase4_ingestion"
down_revision = "0002_phase2_fta_watchlist"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "data_versions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("label", sa.String(length=128), nullable=False),
        sa.Column("fingerprint", sa.String(length=128), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("batch_id", sa.String(length=36), nullable=True),
        sa.Column("record_counts", sa.JSON(), nullable=False),
    )
    op.create_index("ix_data_versions_fingerprint", "data_versions", ["fingerprint"])

    op.create_table(
        "ingestion_batches",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("source_key", sa.String(length=128), nullable=False),
        sa.Column("archive_path", sa.String(length=1024), nullable=False),
        sa.Column("checksum", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("publisher", sa.String(length=256), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("validation_summary", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("published_source_id", sa.String(length=64), nullable=True),
        sa.Column("data_version_id", sa.String(length=36), nullable=True),
    )
    op.create_index("ix_ingestion_batches_source_key", "ingestion_batches", ["source_key"])
    op.create_index("ix_ingestion_batches_status", "ingestion_batches", ["status"])
    op.create_index("ix_ingestion_batches_checksum", "ingestion_batches", ["checksum"])

    op.create_table(
        "ingestion_proposals",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "batch_id",
            sa.String(length=36),
            sa.ForeignKey("ingestion_batches.id"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("validation_status", sa.String(length=16), nullable=False),
        sa.Column("validation_errors", sa.JSON(), nullable=False),
        sa.Column("publish_status", sa.String(length=16), nullable=False),
    )
    op.create_index("ix_ingestion_proposals_batch_id", "ingestion_proposals", ["batch_id"])


def downgrade() -> None:
    op.drop_table("ingestion_proposals")
    op.drop_index("ix_ingestion_batches_checksum", table_name="ingestion_batches")
    op.drop_index("ix_ingestion_batches_status", table_name="ingestion_batches")
    op.drop_index("ix_ingestion_batches_source_key", table_name="ingestion_batches")
    op.drop_table("ingestion_batches")
    op.drop_index("ix_data_versions_fingerprint", table_name="data_versions")
    op.drop_table("data_versions")
