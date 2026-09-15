"""R2 S5: Party, LineItem, Evidence, richer Source/TariffRule, CalculationSnapshot."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0005_r2_core_entities"
down_revision = "0004_v11_watchlist_shipment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "parties",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=True),
        sa.Column("address_text", sa.Text(), nullable=True),
        sa.Column("tax_id", sa.String(length=64), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_parties_role", "parties", ["role"])

    with op.batch_alter_table("source_documents") as batch:
        batch.add_column(sa.Column("archive_path", sa.String(length=1024), nullable=True))
        batch.add_column(sa.Column("content_type", sa.String(length=128), nullable=True))
        batch.add_column(
            sa.Column(
                "source_kind",
                sa.String(length=64),
                nullable=False,
                server_default="curated_dataset",
            )
        )
        batch.add_column(
            sa.Column("live_claim", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch.add_column(sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("parsed_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("superseded_by", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("review_notes", sa.Text(), nullable=True))
        batch.create_index("ix_source_documents_status", ["status"])

    with op.batch_alter_table("tariff_rates") as batch:
        batch.add_column(
            sa.Column("regime", sa.String(length=32), nullable=False, server_default="mfn")
        )
        batch.add_column(sa.Column("rule_label", sa.String(length=256), nullable=True))
        batch.add_column(sa.Column("notes", sa.Text(), nullable=True))

    with op.batch_alter_table("shipments") as batch:
        batch.add_column(sa.Column("exporter_party_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("importer_party_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("consignee_party_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key(
            "fk_shipments_exporter_party_id", "parties", ["exporter_party_id"], ["id"]
        )
        batch.create_foreign_key(
            "fk_shipments_importer_party_id", "parties", ["importer_party_id"], ["id"]
        )
        batch.create_foreign_key(
            "fk_shipments_consignee_party_id", "parties", ["consignee_party_id"], ["id"]
        )

    op.create_table(
        "line_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "shipment_id",
            sa.String(length=36),
            sa.ForeignKey("shipments.id"),
            nullable=False,
        ),
        sa.Column("line_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("hs_code", sa.String(length=16), nullable=True),
        sa.Column("qty", sa.Numeric(14, 2), nullable=False, server_default="1"),
        sa.Column("unit_value", sa.Numeric(14, 2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column("origin", sa.String(length=2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_line_items_shipment_id", "line_items", ["shipment_id"])
    op.create_index("ix_line_items_hs_code", "line_items", ["hs_code"])

    op.create_table(
        "evidence",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "shipment_id",
            sa.String(length=36),
            sa.ForeignKey("shipments.id"),
            nullable=True,
        ),
        sa.Column("kind", sa.String(length=64), nullable=False, server_default="citation"),
        sa.Column("label", sa.String(length=256), nullable=False),
        sa.Column(
            "source_document_id",
            sa.String(length=64),
            sa.ForeignKey("source_documents.id"),
            nullable=True,
        ),
        sa.Column("tariff_rate_id", sa.String(length=36), nullable=True),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.Column("uri", sa.String(length=1024), nullable=True),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="recorded"),
        sa.Column("meta_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_evidence_shipment_id", "evidence", ["shipment_id"])

    op.create_table(
        "calculation_snapshots",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "shipment_id",
            sa.String(length=36),
            sa.ForeignKey("shipments.id"),
            nullable=True,
        ),
        sa.Column("calculation_mode", sa.String(length=16), nullable=False),
        sa.Column("requested_mode", sa.String(length=16), nullable=True),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("inputs_json", sa.JSON(), nullable=False),
        sa.Column("outputs_json", sa.JSON(), nullable=False),
        sa.Column("tariff_rate_id", sa.String(length=36), nullable=True),
        sa.Column("source_document_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_calculation_snapshots_shipment_id",
        "calculation_snapshots",
        ["shipment_id"],
    )
    op.create_index(
        "ix_calculation_snapshots_mode",
        "calculation_snapshots",
        ["calculation_mode"],
    )

    # Normalize legacy source status "active" → published semantics in place.
    op.execute(
        "UPDATE source_documents SET status = 'published' WHERE status = 'active'"
    )


def downgrade() -> None:
    op.drop_index("ix_calculation_snapshots_mode", table_name="calculation_snapshots")
    op.drop_index("ix_calculation_snapshots_shipment_id", table_name="calculation_snapshots")
    op.drop_table("calculation_snapshots")
    op.drop_index("ix_evidence_shipment_id", table_name="evidence")
    op.drop_table("evidence")
    op.drop_index("ix_line_items_hs_code", table_name="line_items")
    op.drop_index("ix_line_items_shipment_id", table_name="line_items")
    op.drop_table("line_items")

    with op.batch_alter_table("shipments") as batch:
        batch.drop_constraint("fk_shipments_consignee_party_id", type_="foreignkey")
        batch.drop_constraint("fk_shipments_importer_party_id", type_="foreignkey")
        batch.drop_constraint("fk_shipments_exporter_party_id", type_="foreignkey")
        batch.drop_column("consignee_party_id")
        batch.drop_column("importer_party_id")
        batch.drop_column("exporter_party_id")

    with op.batch_alter_table("tariff_rates") as batch:
        batch.drop_column("notes")
        batch.drop_column("rule_label")
        batch.drop_column("regime")

    with op.batch_alter_table("source_documents") as batch:
        batch.drop_index("ix_source_documents_status")
        batch.drop_column("review_notes")
        batch.drop_column("superseded_by")
        batch.drop_column("published_at")
        batch.drop_column("reviewed_at")
        batch.drop_column("parsed_at")
        batch.drop_column("fetched_at")
        batch.drop_column("live_claim")
        batch.drop_column("source_kind")
        batch.drop_column("content_type")
        batch.drop_column("archive_path")

    op.drop_index("ix_parties_role", table_name="parties")
    op.drop_table("parties")
