"""Admin Sources trust: path reconcile + mixed-batch approve."""

from __future__ import annotations

from sqlalchemy import select

from backend.app.data.models import SourceConnection, TariffRate
from backend.app.services.source_connection_service import ensure_default_connections
from backend.tests.helpers.db import make_client


STALE_PATH = "config/trade/sources/cbic_notification_2026_q3.json"
CANONICAL_PATH = "config/trade/fixtures/cbic/cbic_notification_2026_q3.json"


def test_stale_local_path_reconciled_and_refresh_works() -> None:
    client = make_client()
    # Seed defaults via list
    listed = client.get("/api/v1/source-connections")
    assert listed.status_code == 200

    factory = client.app.state.session_factory
    with factory() as session:
        row = session.scalar(
            select(SourceConnection).where(
                SourceConnection.key == "cbic_notification_2026_q3"
            )
        )
        assert row is not None
        row.local_path = STALE_PATH
        session.commit()

    with factory() as session:
        ensure_default_connections(session)
        session.commit()
        row = session.scalar(
            select(SourceConnection).where(
                SourceConnection.key == "cbic_notification_2026_q3"
            )
        )
        assert row is not None
        assert row.local_path == CANONICAL_PATH

    # Simulate stale path again; fetch itself reconciles then succeeds
    with factory() as session:
        row = session.scalar(
            select(SourceConnection).where(
                SourceConnection.key == "cbic_notification_2026_q3"
            )
        )
        assert row is not None
        row.local_path = STALE_PATH
        session.commit()

    response = client.post(
        "/api/v1/source-connections/cbic_notification_2026_q3/fetch"
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["checksum"]
    assert body["connection"]["local_path"] == CANONICAL_PATH


def test_mixed_batch_approve_publishes_only_ok_rows() -> None:
    client = make_client()
    batch = client.post(
        "/api/v1/ingest/run",
        json={"source_key": "cbic_notification_2026_q3", "force": True},
    ).json()
    assert batch["validation_summary"]["ok"] >= 1
    assert batch["validation_summary"]["error"] >= 1

    diff = client.get(f"/api/v1/ingest/batches/{batch['id']}/diff").json()
    assert len(diff["quarantined"]) >= 1
    assert any(c.get("change_type") in {"added", "changed", "unchanged"} for c in diff["changes"])

    approved = client.post(
        f"/api/v1/ingest/batches/{batch['id']}/approve",
        json={"notes": "Mixed batch trust test"},
    )
    assert approved.status_code == 200
    body = approved.json()
    assert body["status"] == "approved"

    ok_ids = {
        p["id"] for p in body["proposals"] if p["validation_status"] == "ok"
    }
    err_ids = {
        p["id"] for p in body["proposals"] if p["validation_status"] == "error"
    }
    assert ok_ids
    assert err_ids
    for p in body["proposals"]:
        if p["id"] in ok_ids:
            assert p["publish_status"] == "published"
        if p["id"] in err_ids:
            assert p["publish_status"] == "skipped"

    # Invalid HS from fixture must not appear as an active published rate
    factory = client.app.state.session_factory
    with factory() as session:
        bad = session.scalars(
            select(TariffRate).where(
                TariffRate.hs_code == "9999.99",
                TariffRate.status == "active",
            )
        ).all()
        assert bad == []
