"""Organizations, users, watchlist tenancy, IdP config hooks (IF-10)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009_org_watchlist_idp"
down_revision = "0008_corridors_coverage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=True),
        sa.Column("tax_identifier", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column("email", sa.String(length=256), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="viewer"),
        sa.Column("idp_subject", sa.String(length=256), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_organization_id", "users", ["organization_id"])
    op.create_index("ix_users_idp_subject", "users", ["idp_subject"])

    with op.batch_alter_table("watchlist_items") as batch:
        batch.add_column(
            sa.Column("organization_id", sa.String(length=36), nullable=True)
        )
        batch.add_column(sa.Column("created_by_user_id", sa.String(length=36), nullable=True))

    # Demo org seed
    op.execute(
        sa.text(
            "INSERT INTO organizations (id, name, country, tax_identifier, created_at) "
            "VALUES ('org_demo', 'TradeGraph Demo Org', 'IN', NULL, CURRENT_TIMESTAMP)"
        )
    )
    op.execute(
        sa.text(
            "INSERT INTO users (id, organization_id, email, name, role, idp_subject, created_at) "
            "VALUES ("
            "'user_demo_admin', 'org_demo', 'admin@demo.tradegraph.local', "
            "'Demo Admin', 'admin', 'demo-admin', CURRENT_TIMESTAMP)"
        )
    )
    op.execute(sa.text("UPDATE watchlist_items SET organization_id = 'org_demo'"))


def downgrade() -> None:
    with op.batch_alter_table("watchlist_items") as batch:
        batch.drop_column("created_by_user_id")
        batch.drop_column("organization_id")
    op.drop_index("ix_users_idp_subject", table_name="users")
    op.drop_index("ix_users_organization_id", table_name="users")
    op.drop_table("users")
    op.drop_table("organizations")
