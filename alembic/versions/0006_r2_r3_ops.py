"""R2/R3: FTA conditions, uploads, audit, notifications, jobs."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0006_r2_r3_ops"
down_revision = "0005_r2_core_entities"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("agreement_eligibility") as batch:
        batch.add_column(
            sa.Column("conditions_json", sa.JSON(), nullable=False, server_default="[]")
        )

    op.create_table(
        "document_uploads",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "shipment_id",
            sa.String(length=36),
            sa.ForeignKey("shipments.id"),
            nullable=False,
        ),
        sa.Column("doc_code", sa.String(length=64), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column(
            "content_type",
            sa.String(length=128),
            nullable=False,
            server_default="application/octet-stream",
        ),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("checksum", sa.String(length=128), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("uploaded_by", sa.String(length=128), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_document_uploads_shipment_id", "document_uploads", ["shipment_id"])
    op.create_index("ix_document_uploads_doc_code", "document_uploads", ["doc_code"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor", sa.String(length=128), nullable=False, server_default="anonymous"),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="viewer"),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=True),
        sa.Column("resource_id", sa.String(length=64), nullable=True),
        sa.Column("detail_json", sa.JSON(), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])

    op.create_table(
        "notifications",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("watchlist_item_id", sa.String(length=36), nullable=True),
        sa.Column("shipment_id", sa.String(length=36), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_notifications_kind", "notifications", ["kind"])
    op.create_index("ix_notifications_shipment_id", "notifications", ["shipment_id"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])

    op.create_table(
        "job_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("job_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="completed"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary_json", sa.JSON(), nullable=False),
    )
    op.create_index("ix_job_runs_job_type", "job_runs", ["job_type"])


def downgrade() -> None:
    op.drop_index("ix_job_runs_job_type", table_name="job_runs")
    op.drop_table("job_runs")
    op.drop_index("ix_notifications_created_at", table_name="notifications")
    op.drop_index("ix_notifications_shipment_id", table_name="notifications")
    op.drop_index("ix_notifications_kind", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_document_uploads_doc_code", table_name="document_uploads")
    op.drop_index("ix_document_uploads_shipment_id", table_name="document_uploads")
    op.drop_table("document_uploads")
    with op.batch_alter_table("agreement_eligibility") as batch:
        batch.drop_column("conditions_json")
