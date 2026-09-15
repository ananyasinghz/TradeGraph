"""0014: user last_login_at for Firebase provisioning."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0014_user_last_login"
down_revision = "0013_full_hs_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        cols = {
            r[1]
            for r in bind.execute(sa.text("PRAGMA table_info(users)")).fetchall()
        }
        if "last_login_at" not in cols:
            op.execute("ALTER TABLE users ADD COLUMN last_login_at DATETIME")
    else:
        op.add_column(
            "users",
            sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        # SQLite cannot drop column easily pre-3.35; leave nullable column.
        return
    op.drop_column("users", "last_login_at")
