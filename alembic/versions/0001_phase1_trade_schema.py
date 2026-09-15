"""Phase 1 initial trade schema."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_phase1_trade_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dataset_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("fingerprint", sa.String(length=128), nullable=False, unique=True),
        sa.Column("record_counts", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "source_documents",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("publisher", sa.String(length=256), nullable=False),
        sa.Column("url", sa.String(length=1024), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("file_path", sa.String(length=1024), nullable=True),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_table(
        "hs_codes",
        sa.Column("code", sa.String(length=16), primary_key=True),
        sa.Column("description", sa.String(length=1024), nullable=False),
        sa.Column("chapter", sa.String(length=4), nullable=False),
        sa.Column("parent_code", sa.String(length=16), nullable=True),
    )
    op.create_index("ix_hs_codes_chapter", "hs_codes", ["chapter"])
    op.create_table(
        "tariff_rates",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("hs_code", sa.String(length=16), sa.ForeignKey("hs_codes.code"), nullable=False),
        sa.Column("origin", sa.String(length=2), nullable=False),
        sa.Column("destination", sa.String(length=2), nullable=False),
        sa.Column("rate", sa.Numeric(8, 4), nullable=False),
        sa.Column("rate_type", sa.String(length=32), nullable=False),
        sa.Column("duty_components", sa.JSON(), nullable=False),
        sa.Column("agreement_id", sa.String(length=64), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column(
            "source_document_id",
            sa.String(length=64),
            sa.ForeignKey("source_documents.id"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("data_quality", sa.String(length=32), nullable=False),
        sa.Column("superseded_by", sa.String(length=36), nullable=True),
        sa.UniqueConstraint(
            "hs_code",
            "origin",
            "destination",
            "version",
            name="uq_tariff_hs_corridor_version",
        ),
    )
    op.create_index("ix_tariff_rates_hs_code", "tariff_rates", ["hs_code"])
    op.create_index("ix_tariff_rates_origin", "tariff_rates", ["origin"])
    op.create_index("ix_tariff_rates_destination", "tariff_rates", ["destination"])
    op.create_index("ix_tariff_rates_effective_from", "tariff_rates", ["effective_from"])
    op.create_index("ix_tariff_rates_status", "tariff_rates", ["status"])
    op.create_table(
        "document_requirements",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("origin", sa.String(length=2), nullable=False),
        sa.Column("destination", sa.String(length=2), nullable=False),
        sa.Column("hs_code", sa.String(length=16), nullable=True),
        sa.Column("agreement_id", sa.String(length=64), nullable=True),
        sa.Column("doc_code", sa.String(length=64), nullable=False),
        sa.Column("doc_label", sa.String(length=256), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_document_requirements_origin", "document_requirements", ["origin"])
    op.create_index(
        "ix_document_requirements_destination", "document_requirements", ["destination"]
    )
    op.create_index("ix_document_requirements_hs_code", "document_requirements", ["hs_code"])
    op.create_table(
        "shipments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("product_text", sa.Text(), nullable=False),
        sa.Column("origin", sa.String(length=2), nullable=False),
        sa.Column("destination", sa.String(length=2), nullable=False),
        sa.Column("hs_code_working", sa.String(length=16), nullable=True),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("incoterm", sa.String(length=16), nullable=False),
        sa.Column("invoice_value", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("qty", sa.Numeric(14, 2), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "shipment_calculations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("shipment_id", sa.String(length=36), sa.ForeignKey("shipments.id"), nullable=False),
        sa.Column("inputs_json", sa.JSON(), nullable=False),
        sa.Column("outputs_json", sa.JSON(), nullable=False),
        sa.Column("tariff_rate_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_shipment_calculations_shipment_id", "shipment_calculations", ["shipment_id"]
    )
    op.create_table(
        "shipment_checklists",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("shipment_id", sa.String(length=36), sa.ForeignKey("shipments.id"), nullable=False),
        sa.Column("items_json", sa.JSON(), nullable=False),
        sa.Column("progress", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_shipment_checklists_shipment_id", "shipment_checklists", ["shipment_id"])
    op.create_table(
        "ask_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("shipment_id", sa.String(length=36), nullable=True),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("route", sa.String(length=64), nullable=False),
        sa.Column("plan_json", sa.JSON(), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=False),
        sa.Column("tokens_out", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ask_runs_shipment_id", "ask_runs", ["shipment_id"])


def downgrade() -> None:
    op.drop_table("ask_runs")
    op.drop_table("shipment_checklists")
    op.drop_table("shipment_calculations")
    op.drop_table("shipments")
    op.drop_table("document_requirements")
    op.drop_table("tariff_rates")
    op.drop_table("hs_codes")
    op.drop_table("source_documents")
    op.drop_table("dataset_runs")
