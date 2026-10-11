"""Admin Sources honesty: verified CBIC lane, auth publish, freshness, coverage."""

from __future__ import annotations

from backend.app.services.source_connection_service import VERIFIED_CBIC_CH61_KEY
from backend.tests.helpers.db import make_client


def test_verified_cbic_connection_seeded_without_env() -> None:
    client = make_client()
    rows = client.get("/api/v1/source-connections").json()
    keys = {r["key"] for r in rows}
    assert VERIFIED_CBIC_CH61_KEY in keys
    assert "cbic_notification_2026_q3" in keys
    verified = next(r for r in rows if r["key"] == VERIFIED_CBIC_CH61_KEY)
    assert verified["lane"] == "live_official"
    assert verified["document_url"]
    assert "courier.cbic.gov.in" in (verified["source_url"] or "")
    assert verified["refresh_mode"] == "manual_only"
    fixture = next(r for r in rows if r["key"] == "cbic_notification_2026_q3")
    assert fixture["lane"] == "demo_fixture"


def test_feed_status_manual_refresh_mode() -> None:
    client = make_client(source_fetch_scheduler_enabled=False)
    feed = client.get("/api/v1/source-connections/feed-status").json()
    assert feed["refresh_mode"] == "manual_only"
    assert feed["scheduler_enabled"] is False
    assert feed["next_attempt_at"] is None
    assert feed["published_rates_usable"] is True


def test_anonymous_publish_blocked_without_flag() -> None:
    client = make_client(allow_anonymous_publish=False, auth_enabled=False)
    batches = client.get("/api/v1/ingest/batches")
    assert batches.status_code == 200
    # Promote requires publisher (authenticated or demo flag)
    promote = client.post("/api/v1/ingest/promote-cbic", json={"notes": "should fail"})
    assert promote.status_code == 401
    assert promote.json()["error"]["code"] == "AUTH_REQUIRED"


def test_viewer_cannot_approve_when_auth_on() -> None:
    client = make_client(auth_enabled=True, allow_anonymous_publish=False)
    # Seed a pending batch via anonymous-blocked path won't work; use fixture with auth token
    run = client.post(
        "/api/v1/ingest/run",
        headers={"Authorization": "Bearer demo-admin"},
        json={"source_key": "cbic_notification_2026_q3", "force": True},
    )
    assert run.status_code == 200, run.text
    batch_id = run.json()["id"]
    denied = client.post(
        f"/api/v1/ingest/batches/{batch_id}/approve",
        headers={"Authorization": "Bearer demo-viewer"},
        json={"notes": "viewer"},
    )
    assert denied.status_code == 403


def test_coverage_statuses_ch62_missing_bcd() -> None:
    client = make_client()
    body = client.get("/api/v1/duty/coverage").json()
    chapters = {c["chapter"]: c for c in body["chapters"]}
    assert "61" in chapters
    assert chapters["61"]["bcd_status"] in {"curated", "verified", "illustrative"}
    assert "62" in chapters
    assert chapters["62"]["classification_codes"] >= 1
    assert chapters["62"]["bcd_status"] == "missing"
    assert chapters["62"]["igst_status"] == "missing"
    assert chapters["62"]["bcd_rates"] == 0


def test_whoami_exposes_anonymous_publish_flag() -> None:
    client = make_client(allow_anonymous_publish=True)
    me = client.get("/api/v1/auth/whoami").json()
    assert me["auth_enabled"] is False
    assert me["allow_anonymous_publish"] is True
