"""Countries, corridors, source coverage, field mappings (IF-3)."""

from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

revision = "0008_corridors_coverage"
down_revision = "0007_source_connections"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "countries",
        sa.Column("code", sa.String(length=2), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    op.create_table(
        "corridors",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("origin_country", sa.String(length=2), nullable=False),
        sa.Column("destination_country", sa.String(length=2), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="demonstration"),
        sa.Column("supported_hs_chapters", sa.JSON(), nullable=False),
        sa.Column("supported_regimes", sa.JSON(), nullable=False),
        sa.Column("tariff_source_codes", sa.JSON(), nullable=False),
        sa.Column("agreement_source_codes", sa.JSON(), nullable=False),
        sa.Column("regulation_source_codes", sa.JSON(), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint(
            "origin_country",
            "destination_country",
            name="uq_corridors_origin_destination",
        ),
    )
    op.create_index("ix_corridors_status", "corridors", ["status"])

    op.create_table(
        "source_coverage",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "source_connection_id",
            sa.String(length=36),
            sa.ForeignKey("source_connections.id"),
            nullable=True,
        ),
        sa.Column("source_code", sa.String(length=128), nullable=False),
        sa.Column(
            "corridor_id",
            sa.String(length=36),
            sa.ForeignKey("corridors.id"),
            nullable=False,
        ),
        sa.Column("hs_chapter", sa.String(length=4), nullable=False),
        sa.Column("capability", sa.String(length=64), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_source_coverage_lookup",
        "source_coverage",
        ["corridor_id", "capability", "hs_chapter"],
    )

    op.create_table(
        "field_mappings",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("source_code", sa.String(length=128), nullable=False),
        sa.Column("format", sa.String(length=32), nullable=False),
        sa.Column("mapping_json", sa.JSON(), nullable=False),
        sa.Column("parser_version", sa.String(length=32), nullable=False, server_default="1"),
        sa.UniqueConstraint("source_code", "format", name="uq_field_mappings_source_format"),
    )

    # Enrich source_connections for capability-based registry
    with op.batch_alter_table("source_connections") as batch:
        batch.add_column(sa.Column("authority", sa.String(length=128), nullable=True))
        batch.add_column(
            sa.Column("source_type", sa.String(length=64), nullable=True)
        )
        batch.add_column(
            sa.Column("access_method", sa.String(length=32), nullable=True)
        )
        batch.add_column(sa.Column("requires_auth", sa.Boolean(), nullable=True))
        batch.add_column(sa.Column("capabilities_json", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("schedule", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("connector_type", sa.String(length=64), nullable=True))

    # Seed BD / IN + BD→IN corridor (idempotent inserts)
    op.execute(
        sa.text(
            "INSERT INTO countries (code, name, active) VALUES "
            "('BD', 'Bangladesh', 1), ('IN', 'India', 1)"
        )
    )
    corridor_id = "corr_bd_in"
    chapters = json.dumps(["61"])
    regimes = json.dumps(["MFN", "SAFTA"])
    tariff_sources = json.dumps(["CBIC_NOTIFICATION_2026_Q3", "CURATED_MIRROR_CBIC_Q3"])
    agreement_sources = json.dumps(["SAFTA_ILLUSTRATIVE"])
    regulation_sources = json.dumps(["CBIC_NOTIFICATION_2026_Q3"])
    op.execute(
        sa.text(
            "INSERT INTO corridors ("
            "id, origin_country, destination_country, status, "
            "supported_hs_chapters, supported_regimes, "
            "tariff_source_codes, agreement_source_codes, regulation_source_codes, notes"
            ") VALUES ("
            f"'{corridor_id}', 'BD', 'IN', 'demonstration', "
            f"'{chapters}', '{regimes}', "
            f"'{tariff_sources}', '{agreement_sources}', '{regulation_sources}', "
            "'Prototype BD→IN chapter 61 corridor')"
        )
    )
    mapping = json.dumps(
        {
            "hs_code": "hs_code",
            "description": "notes",
            "duty_rate": "rate",
            "effective_from": "effective_from",
            "origin": "origin",
            "destination": "destination",
        }
    )
    op.execute(
        sa.text(
            "INSERT INTO field_mappings (id, source_code, format, mapping_json, parser_version) "
            f"VALUES ('fmap_cbic_json', 'CBIC_NOTIFICATION_2026_Q3', 'json', '{mapping}', '1')"
        )
    )
    for cap in ("tariff_lookup", "tariff_documents", "regulations"):
        op.execute(
            sa.text(
                "INSERT INTO source_coverage ("
                "id, source_connection_id, source_code, corridor_id, hs_chapter, capability"
                ") VALUES ("
                f"'cov_cbic_{cap}', NULL, 'CBIC_NOTIFICATION_2026_Q3', "
                f"'{corridor_id}', '61', '{cap}')"
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("source_connections") as batch:
        batch.drop_column("connector_type")
        batch.drop_column("schedule")
        batch.drop_column("capabilities_json")
        batch.drop_column("requires_auth")
        batch.drop_column("access_method")
        batch.drop_column("source_type")
        batch.drop_column("authority")
    op.drop_table("field_mappings")
    op.drop_index("ix_source_coverage_lookup", table_name="source_coverage")
    op.drop_table("source_coverage")
    op.drop_index("ix_corridors_status", table_name="corridors")
    op.drop_table("corridors")
    op.drop_table("countries")
