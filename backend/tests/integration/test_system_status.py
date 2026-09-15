"""PRODUCT_USABILITY_PLAN S1: system status / product mode."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from backend.app.data.models import DataVersion, TariffRate
from backend.tests.helpers.db import make_client, make_settings


def test_system_status_defaults_to_demonstration() -> None:
    client = make_client()
    response = client.get("/api/v1/system/status")
    assert response.status_code == 200
    body = response.json()
    assert body["product_mode"] == "demonstration"
    assert body["requested_product_mode"] == "demonstration"
    assert body["mode_forced"] is False
    assert body["origin"] == "BD"
    assert body["destination"] == "IN"
    assert body["hs_chapter"] == "61"
    assert "61" in body["hs_chapters"]
    assert body["active_tariff_rule_count"] >= 1
    assert "Configured" in body["official_source_connection"]
    assert body["live_government_feed"] is False
    assert body["source_connection_kind"] in {"curated_mirror", "none"}
    assert body["customs_mode_available"] is False
    assert any("Demo data" in n for n in body["notices"])
    assert "official customs" in body["disclaimer"].lower()
    assert body["enabled_source_connection_count"] >= 1

def test_operational_request_forced_without_approved_corpus() -> None:
    client = make_client(product_mode="operational")
    body = client.get("/api/v1/system/status").json()
    assert body["requested_product_mode"] == "operational"
    assert body["product_mode"] == "demonstration"
    assert body["mode_forced"] is True
    assert body["mode_lock_reason"]


def test_operational_allowed_with_published_approved_rates() -> None:
    client = make_client(product_mode="operational")
    factory = client.app.state.session_factory
    with factory() as session:
        session.add(
            DataVersion(
                label="test-approved-corpus",
                fingerprint="test-fp-s1",
                notes="fixture",
                published_at=datetime.now(UTC),
                batch_id=None,
                record_counts={"tariff_rates": 1},
            )
        )
        rate = session.scalars(select(TariffRate).limit(1)).first()
        assert rate is not None
        rate.data_quality = "demo_verified"
        rate.status = "active"
        session.commit()

    body = client.get("/api/v1/system/status").json()
    assert body["requested_product_mode"] == "operational"
    assert body["product_mode"] == "operational"
    assert body["mode_forced"] is False
    assert body["approved_tariff_rule_count"] >= 1
    assert any("Operational mode" in n for n in body["notices"])


def test_settings_product_mode_default() -> None:
    settings = make_settings()
    assert settings.product_mode == "demonstration"


def test_if12a_status_and_dashboard_agree_on_illustrative() -> None:
    client = make_client()
    status = client.get("/api/v1/system/status").json()
    dash = client.get("/api/v1/dashboard").json()["data_status"]
    assert status["effective_product_status"] == "illustrative"
    assert dash["effective_product_status"] == "illustrative"
    assert status["active_rules"]["approved"] == dash["active_rules"]["approved"]
    assert status["active_rules"]["illustrative"] == dash["active_rules"]["illustrative"]
    assert "Approved verified" not in dash["dataset_type"]
    assert "Sample" in dash["dataset_type"] or "sample" in dash["dataset_type"].lower()


def test_if12a_data_version_alone_does_not_claim_verified_corpus() -> None:
    """Approved DataVersion without demo_verified active rates must stay illustrative."""
    client = make_client()
    factory = client.app.state.session_factory
    with factory() as session:
        session.add(
            DataVersion(
                label="ingest:orphan-batch",
                fingerprint="orphan-fp",
                notes="version without verified rates",
                published_at=datetime.now(UTC),
                batch_id=None,
                record_counts={},
            )
        )
        session.commit()

    status = client.get("/api/v1/system/status").json()
    dash = client.get("/api/v1/dashboard").json()["data_status"]
    assert status["approved_tariff_rule_count"] == 0
    assert status["effective_product_status"] == "illustrative"
    assert dash["effective_product_status"] == "illustrative"
    assert "Approved verified" not in dash["dataset_type"]
    assert status["last_approved_at"] is None
    assert dash["last_approved_at"] is None
    assert status["latest_source_batch"] is not None
    assert status["latest_source_batch"]["label"] == "ingest:orphan-batch"
    assert status["trust_notice"] or dash["trust_notice"]
