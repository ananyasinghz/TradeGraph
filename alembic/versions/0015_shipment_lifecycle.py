"""0015: shipment lifecycle status helpers (open/closed/discarded)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0015_shipment_lifecycle"
down_revision = "0014_user_last_login"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Normalize legacy draft statuses to open; closed_at optional column."""
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        cols = {
            r[1]
            for r in bind.execute(sa.text("PRAGMA table_info(shipments)")).fetchall()
        }
        if "closed_at" not in cols:
            op.execute("ALTER TABLE shipments ADD COLUMN closed_at DATETIME")
        bind.execute(
            sa.text(
                "UPDATE shipments SET status = 'open' "
                "WHERE status IS NULL OR status IN ('draft', 'in_progress', 'active')"
            )
        )
    else:
        op.add_column(
            "shipments",
            sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.execute(
            sa.text(
                "UPDATE shipments SET status = 'open' "
                "WHERE status IS NULL OR status IN ('draft', 'in_progress', 'active')"
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return
    op.drop_column("shipments", "closed_at")
