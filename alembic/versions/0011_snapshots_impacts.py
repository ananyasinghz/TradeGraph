"""IF-11d/e: snapshot enrichment + scenario impacts."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0011_snapshots_impacts"
down_revision = "0010_scenario_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("calculation_snapshots") as batch:
        batch.add_column(
            sa.Column(
                "calculation_engine_version",
                sa.String(length=32),
                nullable=False,
                server_default="in_duty.v1",
            )
        )
        batch.add_column(sa.Column("source_checksum", sa.String(length=128), nullable=True))
        batch.add_column(sa.Column("tariff_version", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("data_quality", sa.String(length=32), nullable=True))

    op.create_table(
        "scenario_impacts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("shipment_id", sa.String(length=36), sa.ForeignKey("shipments.id"), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=True),
        sa.Column("hs_code", sa.String(length=16), nullable=False),
        sa.Column("origin", sa.String(length=2), nullable=False),
        sa.Column("destination", sa.String(length=2), nullable=False),
        sa.Column("old_rate", sa.Numeric(8, 4), nullable=False),
        sa.Column("new_rate", sa.Numeric(8, 4), nullable=False),
        sa.Column("old_landed_cost", sa.Numeric(14, 2), nullable=True),
        sa.Column("new_landed_cost", sa.Numeric(14, 2), nullable=True),
        sa.Column("duty_delta", sa.Numeric(14, 2), nullable=True),
        sa.Column("landed_delta", sa.Numeric(14, 2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column("old_tariff_rate_id", sa.String(length=36), nullable=True),
        sa.Column("new_tariff_rate_id", sa.String(length=36), nullable=True),
        sa.Column("old_snapshot_id", sa.String(length=36), nullable=True),
        sa.Column("new_snapshot_id", sa.String(length=36), nullable=True),
        sa.Column("recommended_action", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_scenario_impacts_shipment_id", "scenario_impacts", ["shipment_id"])
    op.create_index("ix_scenario_impacts_hs_code", "scenario_impacts", ["hs_code"])


def downgrade() -> None:
    op.drop_index("ix_scenario_impacts_hs_code", table_name="scenario_impacts")
    op.drop_index("ix_scenario_impacts_shipment_id", table_name="scenario_impacts")
    op.drop_table("scenario_impacts")
    with op.batch_alter_table("calculation_snapshots") as batch:
        batch.drop_column("data_quality")
        batch.drop_column("tariff_version")
        batch.drop_column("source_checksum")
        batch.drop_column("calculation_engine_version")
