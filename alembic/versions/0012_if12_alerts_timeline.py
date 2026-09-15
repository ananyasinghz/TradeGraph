"""IF-12c/d: impact acknowledgement + scenario timeline events."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0012_if12_alerts_timeline"
down_revision = "0011_snapshots_impacts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("scenario_impacts") as batch:
        batch.add_column(sa.Column("dedupe_key", sa.String(length=256), nullable=True))
        batch.add_column(sa.Column("source_document_id", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("effective_from", sa.Date(), nullable=True))
        batch.add_column(sa.Column("data_version_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("acknowledged_by", sa.String(length=128), nullable=True))
        batch.create_index("ix_scenario_impacts_dedupe_key", ["dedupe_key"])

    op.create_table(
        "scenario_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "scenario_id",
            sa.String(length=36),
            sa.ForeignKey("shipments.id"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.String(length=36), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("snapshot_id", sa.String(length=36), nullable=True),
        sa.Column("tariff_rate_id", sa.String(length=36), nullable=True),
        sa.Column("impact_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_scenario_events_scenario_id", "scenario_events", ["scenario_id"])
    op.create_index("ix_scenario_events_event_type", "scenario_events", ["event_type"])
    op.create_index("ix_scenario_events_created_at", "scenario_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_scenario_events_created_at", table_name="scenario_events")
    op.drop_index("ix_scenario_events_event_type", table_name="scenario_events")
    op.drop_index("ix_scenario_events_scenario_id", table_name="scenario_events")
    op.drop_table("scenario_events")
    with op.batch_alter_table("scenario_impacts") as batch:
        batch.drop_index("ix_scenario_impacts_dedupe_key")
        batch.drop_column("acknowledged_by")
        batch.drop_column("acknowledged_at")
        batch.drop_column("data_version_id")
        batch.drop_column("effective_from")
        batch.drop_column("source_document_id")
        batch.drop_column("dedupe_key")
