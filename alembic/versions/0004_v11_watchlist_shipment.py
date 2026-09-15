"""V1.1g: optional shipment_id on watchlist items."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_v11_watchlist_shipment"
down_revision = "0003_phase4_ingestion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("watchlist_items") as batch:
        batch.drop_constraint("uq_watchlist_hs_corridor", type_="unique")
        batch.add_column(sa.Column("shipment_id", sa.String(length=36), nullable=True))
        batch.create_index("ix_watchlist_items_shipment_id", ["shipment_id"])
        batch.create_foreign_key(
            "fk_watchlist_items_shipment_id",
            "shipments",
            ["shipment_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("watchlist_items") as batch:
        batch.drop_constraint("fk_watchlist_items_shipment_id", type_="foreignkey")
        batch.drop_index("ix_watchlist_items_shipment_id")
        batch.drop_column("shipment_id")
        batch.create_unique_constraint(
            "uq_watchlist_hs_corridor",
            ["hs_code", "origin", "destination"],
        )
