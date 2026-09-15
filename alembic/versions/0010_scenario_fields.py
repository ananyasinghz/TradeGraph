"""IF-11c: persist TradeScenario fields on shipments."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010_scenario_fields"
down_revision = "0009_org_watchlist_idp"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("shipments") as batch:
        batch.add_column(sa.Column("freight", sa.Numeric(14, 2), nullable=True))
        batch.add_column(sa.Column("insurance", sa.Numeric(14, 2), nullable=True))
        batch.add_column(
            sa.Column("regime", sa.String(length=32), nullable=False, server_default="mfn")
        )
        batch.add_column(sa.Column("agreement_code", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("organization_id", sa.String(length=36), nullable=True))
        batch.add_column(
            sa.Column("assumptions_json", sa.JSON(), nullable=False, server_default="{}")
        )
        batch.add_column(
            sa.Column("hs_confirmed_at", sa.DateTime(timezone=True), nullable=True)
        )
    op.create_index("ix_shipments_organization_id", "shipments", ["organization_id"])
    op.execute(sa.text("UPDATE shipments SET organization_id = 'org_demo' WHERE organization_id IS NULL"))


def downgrade() -> None:
    op.drop_index("ix_shipments_organization_id", table_name="shipments")
    with op.batch_alter_table("shipments") as batch:
        batch.drop_column("hs_confirmed_at")
        batch.drop_column("assumptions_json")
        batch.drop_column("organization_id")
        batch.drop_column("agreement_code")
        batch.drop_column("regime")
        batch.drop_column("insurance")
        batch.drop_column("freight")
