"""Full HS nomenclature catalog: hs_codes columns + hs_synonyms + FTS5."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0013_full_hs_catalog"
down_revision = "0012_if12_alerts_timeline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    # Clean up failed batch-alter leftovers from earlier attempts.
    if bind.dialect.name == "sqlite":
        op.execute("DROP TABLE IF EXISTS _alembic_tmp_hs_codes")
        # SQLite: ADD COLUMN is safe without table recreate.
        cols = {
            r[1]
            for r in bind.execute(sa.text("PRAGMA table_info(hs_codes)")).fetchall()
        }
        if "source_pack" not in cols:
            op.execute("ALTER TABLE hs_codes ADD COLUMN source_pack VARCHAR(128)")
        if "heading" not in cols:
            op.execute("ALTER TABLE hs_codes ADD COLUMN heading VARCHAR(8)")
        if "updated_at" not in cols:
            op.execute("ALTER TABLE hs_codes ADD COLUMN updated_at DATETIME")
    else:
        with op.batch_alter_table("hs_codes") as batch:
            batch.add_column(sa.Column("source_pack", sa.String(length=128), nullable=True))
            batch.add_column(sa.Column("heading", sa.String(length=8), nullable=True))
            batch.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "hs_synonyms",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("hs_code", sa.String(length=16), sa.ForeignKey("hs_codes.code"), nullable=False),
        sa.Column("term", sa.String(length=128), nullable=False),
        sa.Column("weight", sa.Numeric(8, 4), nullable=False, server_default="1.0"),
        sa.UniqueConstraint("hs_code", "term", name="uq_hs_synonym_code_term"),
    )
    op.create_index("ix_hs_synonyms_hs_code", "hs_synonyms", ["hs_code"])
    op.create_index("ix_hs_synonyms_term", "hs_synonyms", ["term"])

    if bind.dialect.name == "sqlite":
        op.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS hs_codes_fts USING fts5(
                code UNINDEXED,
                description,
                synonyms,
                tokenize = 'porter'
            )
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.execute("DROP TABLE IF EXISTS hs_codes_fts")
    op.drop_index("ix_hs_synonyms_term", table_name="hs_synonyms")
    op.drop_index("ix_hs_synonyms_hs_code", table_name="hs_synonyms")
    op.drop_table("hs_synonyms")
