"""0017: clearance portal rounds 6–11 schema."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0017_clearance_r6_r11"
down_revision = "0016_exemption_rules"
branch_labels = None
depends_on = None


def _sqlite_cols(bind, table: str) -> set[str]:
    return {r[1] for r in bind.execute(sa.text(f"PRAGMA table_info({table})")).fetchall()}


def _add_col_sqlite(bind, table: str, ddl: str) -> None:
    cols = _sqlite_cols(bind, table)
    col_name = ddl.split()[0]
    if col_name not in cols:
        op.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        _add_col_sqlite(bind, "organizations", "mfa_required BOOLEAN DEFAULT 0")
        _add_col_sqlite(bind, "organizations", "slack_webhook_url VARCHAR(1024)")
        _add_col_sqlite(bind, "organizations", "settings_json JSON")
        _add_col_sqlite(bind, "users", "notification_prefs JSON")
        _add_col_sqlite(bind, "parties", "organization_id VARCHAR(36)")
        _add_col_sqlite(bind, "shipments", "archived_at DATETIME")
        _add_col_sqlite(bind, "shipments", "assign_reviewer_user_id VARCHAR(36)")
        _add_col_sqlite(bind, "notifications", "user_id VARCHAR(36)")
        _add_col_sqlite(bind, "notifications", "organization_id VARCHAR(36)")
        _add_col_sqlite(bind, "corridors", "operational BOOLEAN DEFAULT 0")
    else:
        op.add_column(
            "organizations",
            sa.Column("mfa_required", sa.Boolean(), nullable=False, server_default="0"),
        )
        op.add_column(
            "organizations",
            sa.Column("slack_webhook_url", sa.String(length=1024), nullable=True),
        )
        op.add_column(
            "organizations",
            sa.Column("settings_json", sa.JSON(), nullable=True),
        )
        op.add_column(
            "users",
            sa.Column("notification_prefs", sa.JSON(), nullable=True),
        )
        op.add_column(
            "parties",
            sa.Column("organization_id", sa.String(length=36), nullable=True),
        )
        op.add_column(
            "shipments",
            sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.add_column(
            "shipments",
            sa.Column("assign_reviewer_user_id", sa.String(length=36), nullable=True),
        )
        op.add_column(
            "notifications",
            sa.Column("user_id", sa.String(length=36), nullable=True),
        )
        op.add_column(
            "notifications",
            sa.Column("organization_id", sa.String(length=36), nullable=True),
        )
        op.add_column(
            "corridors",
            sa.Column("operational", sa.Boolean(), nullable=False, server_default="0"),
        )

    op.create_table(
        "user_invites",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=256), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("invited_by", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "case_comments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("shipment_id", sa.String(length=36), sa.ForeignKey("shipments.id"), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=True),
        sa.Column("author_user_id", sa.String(length=36), nullable=True),
        sa.Column("author_actor", sa.String(length=128), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "product_templates",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("product_text", sa.Text(), nullable=False),
        sa.Column("hs_code", sa.String(length=16), nullable=True),
        sa.Column("origin", sa.String(length=2), nullable=True),
        sa.Column("destination", sa.String(length=2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "share_links",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("token", sa.String(length=64), nullable=False, unique=True),
        sa.Column("shipment_id", sa.String(length=36), sa.ForeignKey("shipments.id"), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )

    # BD→IN is the only operational corridor.
    if bind.dialect.name == "sqlite":
        bind.execute(
            sa.text(
                "UPDATE corridors SET operational = 1 "
                "WHERE origin_country = 'BD' AND destination_country = 'IN'"
            )
        )
        bind.execute(
            sa.text(
                "UPDATE corridors SET operational = 0 "
                "WHERE NOT (origin_country = 'BD' AND destination_country = 'IN')"
            )
        )
    else:
        op.execute(
            sa.text(
                "UPDATE corridors SET operational = TRUE "
                "WHERE origin_country = 'BD' AND destination_country = 'IN'"
            )
        )
        op.execute(
            sa.text(
                "UPDATE corridors SET operational = FALSE "
                "WHERE NOT (origin_country = 'BD' AND destination_country = 'IN')"
            )
        )


def downgrade() -> None:
    op.drop_table("share_links")
    op.drop_table("product_templates")
    op.drop_table("case_comments")
    op.drop_table("user_invites")
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return
    op.drop_column("corridors", "operational")
    op.drop_column("notifications", "organization_id")
    op.drop_column("notifications", "user_id")
    op.drop_column("shipments", "assign_reviewer_user_id")
    op.drop_column("shipments", "archived_at")
    op.drop_column("parties", "organization_id")
    op.drop_column("users", "notification_prefs")
    op.drop_column("organizations", "settings_json")
    op.drop_column("organizations", "slack_webhook_url")
    op.drop_column("organizations", "mfa_required")
