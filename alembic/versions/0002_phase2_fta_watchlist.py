"""Phase 2: agreements, eligibility, regulatory chunks, watchlist."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_phase2_fta_watchlist"
down_revision = "0001_phase1_trade_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trade_agreements",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_table(
        "agreement_eligibility",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "agreement_id",
            sa.String(length=64),
            sa.ForeignKey("trade_agreements.id"),
            nullable=False,
        ),
        sa.Column("hs_code", sa.String(length=16), nullable=False),
        sa.Column("origin", sa.String(length=2), nullable=False),
        sa.Column("destination", sa.String(length=2), nullable=False),
        sa.Column("preferential_rate_pct", sa.Numeric(8, 4), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("certificate_doc_code", sa.String(length=64), nullable=True),
        sa.Column("roo_summary", sa.Text(), nullable=True),
        sa.Column(
            "source_document_id",
            sa.String(length=64),
            sa.ForeignKey("source_documents.id"),
            nullable=False,
        ),
        sa.Column("data_quality", sa.String(length=32), nullable=False),
    )
    op.create_index("ix_agreement_eligibility_agreement_id", "agreement_eligibility", ["agreement_id"])
    op.create_index("ix_agreement_eligibility_hs_code", "agreement_eligibility", ["hs_code"])
    op.create_index("ix_agreement_eligibility_origin", "agreement_eligibility", ["origin"])
    op.create_index(
        "ix_agreement_eligibility_destination", "agreement_eligibility", ["destination"]
    )
    op.create_table(
        "regulatory_chunks",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column(
            "source_document_id",
            sa.String(length=64),
            sa.ForeignKey("source_documents.id"),
            nullable=False,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("hs_code", sa.String(length=16), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False),
    )
    op.create_index(
        "ix_regulatory_chunks_source_document_id", "regulatory_chunks", ["source_document_id"]
    )
    op.create_index("ix_regulatory_chunks_hs_code", "regulatory_chunks", ["hs_code"])
    op.create_table(
        "watchlist_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("hs_code", sa.String(length=16), nullable=False),
        sa.Column("origin", sa.String(length=2), nullable=False),
        sa.Column("destination", sa.String(length=2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_rate_id", sa.String(length=36), nullable=True),
        sa.UniqueConstraint("hs_code", "origin", "destination", name="uq_watchlist_hs_corridor"),
    )
    op.create_index("ix_watchlist_items_hs_code", "watchlist_items", ["hs_code"])


def downgrade() -> None:
    op.drop_table("watchlist_items")
    op.drop_table("regulatory_chunks")
    op.drop_table("agreement_eligibility")
    op.drop_table("trade_agreements")
