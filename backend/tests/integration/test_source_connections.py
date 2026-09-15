"""Official source connections + live-feed honesty (Phase A/B/C + IF-11a)."""

from __future__ import annotations

from backend.tests.helpers.db import make_client


def test_source_connections_seed_and_status_fields() -> None:
    client = make_client()
    listed = client.get("/api/v1/source-connections")
    assert listed.status_code == 200
    rows = listed.json()
    assert len(rows) >= 1
    assert rows[0]["key"] == "cbic_notification_2026_q3"
    assert rows[0]["fetch_mode"] == "curated_mirror"

    status = client.get("/api/v1/system/status").json()
    assert "Configured" in status["official_source_connection"]
    assert status["enabled_source_connection_count"] >= 1
    assert status["live_government_feed"] is False
    assert status["live_feed_reason"]
    assert status["source_connection_kind"] in {"curated_mirror", "none"}
    assert "never fetched" in status["official_source_connection"].lower() or (
        status["last_source_fetch_at"] is None
    )


def test_fetch_curated_mirror_updates_feed_status() -> None:
    client = make_client()
    response = client.post(
        "/api/v1/source-connections/cbic_notification_2026_q3/fetch"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["checksum"]
    assert body["source_document_id"]
    assert "curated" in body["resolved_from"] or body["resolved_from"].endswith(".json")

    feed = client.get("/api/v1/source-connections/feed-status").json()
    assert feed["configured"] is True
    assert feed["last_successful_fetch_at"] is not None
    assert feed["live_government_feed"] is False
    assert feed["live_feed_enabled_setting"] is False
    assert feed["source_connection_kind"] == "curated_mirror"
    assert feed["source_connection_label"] == "Curated demonstration source"

    status = client.get("/api/v1/system/status").json()
    assert status["last_source_fetch_at"] is not None
    assert status["live_government_feed"] is False
    assert status["source_connection_label"] == "Curated demonstration source"


def test_live_flag_stays_false_for_curated_even_when_setting_on() -> None:
    """IF-11a: curated mirrors never claim live_government_feed=true."""
    client = make_client(live_feed_enabled=True)
    assert client.get("/api/v1/system/status").json()["live_government_feed"] is False

    fetch = client.post("/api/v1/source-connections/cbic_notification_2026_q3/fetch")
    assert fetch.status_code == 200

    status = client.get("/api/v1/system/status").json()
    assert status["live_government_feed"] is False
    assert status["source_connection_kind"] == "curated_mirror"
    assert "curated" in (status["live_feed_reason"] or "").lower()


def test_system_status_defaults_show_configured_not_live() -> None:
    client = make_client()
    body = client.get("/api/v1/system/status").json()
    assert body["product_mode"] == "demonstration"
    assert body["official_source_connection"] != "Not configured"
    assert body["live_government_feed"] is False
    assert body["source_connection_kind"] != "live_monitored"
    assert any(
        "Curated" in n or "not connected" in n.lower() or "Verified" in n or "Demo data" in n
        for n in body["notices"]
    )
