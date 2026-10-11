"""0016: structured exemption / notification Sl. No. catalog."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0016_exemption_rules"
down_revision = "0015_shipment_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exemption_rules",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("notification_id", sa.String(length=128), nullable=False),
        sa.Column("notification_year", sa.Integer(), nullable=True),
        sa.Column("serial_no", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=512), nullable=False),
        sa.Column("hs_match", sa.String(length=16), nullable=False),
        sa.Column("origin", sa.String(length=8), nullable=False),
        sa.Column("destination", sa.String(length=2), nullable=False),
        sa.Column("condition_code", sa.String(length=64), nullable=False),
        sa.Column("condition_detail", sa.Text(), nullable=False),
        sa.Column("effect_json", sa.JSON(), nullable=False),
        sa.Column(
            "source_document_id",
            sa.String(length=64),
            sa.ForeignKey("source_documents.id"),
            nullable=True,
        ),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("data_quality", sa.String(length=32), nullable=False),
        sa.UniqueConstraint(
            "notification_id",
            "serial_no",
            "hs_match",
            "origin",
            "destination",
            name="uq_exemption_notn_sl_hs_corridor",
        ),
    )
    op.create_index("ix_exemption_rules_notification_id", "exemption_rules", ["notification_id"])
    op.create_index("ix_exemption_rules_serial_no", "exemption_rules", ["serial_no"])
    op.create_index("ix_exemption_rules_hs_match", "exemption_rules", ["hs_match"])
    op.create_index("ix_exemption_rules_origin", "exemption_rules", ["origin"])
    op.create_index("ix_exemption_rules_destination", "exemption_rules", ["destination"])
    op.create_index("ix_exemption_rules_effective_from", "exemption_rules", ["effective_from"])
    op.create_index("ix_exemption_rules_status", "exemption_rules", ["status"])


def downgrade() -> None:
    op.drop_table("exemption_rules")
