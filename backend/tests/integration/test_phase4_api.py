"""Phase 4 ingestion approve/publish tests."""

from __future__ import annotations

from backend.tests.helpers.db import make_client


def test_ingest_archive_validates_and_awaits_approve() -> None:
    client = make_client()
    created = client.post("/api/v1/ingest/run", json={"source_key": "cbic_notification_2026_q3"})
    assert created.status_code == 200
    batch = created.json()
    assert batch["status"] == "pending_review"
    assert batch["validation_summary"]["ok"] >= 3
    assert batch["validation_summary"]["error"] >= 2
    assert any(p["validation_status"] == "error" for p in batch["proposals"])
    assert any(
        p["kind"] == "tariff_rate" and p["validation_status"] == "ok" for p in batch["proposals"]
    )

    # Idempotent without force
    again = client.post(
        "/api/v1/ingest/run",
        json={"source_key": "cbic_notification_2026_q3"},
    ).json()
    assert again["id"] == batch["id"]


def test_approve_publishes_demo_verified_rates_and_data_version() -> None:
    client = make_client()
    batch = client.post(
        "/api/v1/ingest/run",
        json={"source_key": "cbic_notification_2026_q3", "force": True},
    ).json()
    approved = client.post(
        f"/api/v1/ingest/batches/{batch['id']}/approve",
        json={"notes": "Reviewed for Phase 4 demo"},
    )
    assert approved.status_code == 200
    body = approved.json()
    assert body["status"] == "approved"
    assert body["published_source_id"]
    assert body["data_version_id"]

    tariffs = client.get(
        "/api/v1/tariffs",
        params={"hs": "6109.90", "origin": "BD", "destination": "IN", "as_of": "2026-08-01"},
    ).json()
    assert float(tariffs[0]["rate"]) == 9.0
    assert tariffs[0]["data_quality"] in {"demo_verified", "source_verified"}
    assert tariffs[0]["source_document_id"] == body["published_source_id"]

    versions = client.get("/api/v1/data-versions").json()
    assert len(versions) >= 1
    assert versions[0]["id"] == body["data_version_id"]
    assert versions[0]["record_counts"]["tariff_rates"] >= 2


def test_reject_blocks_publish() -> None:
    client = make_client()
    batch = client.post(
        "/api/v1/ingest/run",
        json={"source_key": "cbic_notification_2026_q3", "force": True},
    ).json()
    rejected = client.post(
        f"/api/v1/ingest/batches/{batch['id']}/reject",
        json={"notes": "Bad extract"},
    ).json()
    assert rejected["status"] == "rejected"
    assert all(p["publish_status"] == "skipped" for p in rejected["proposals"])

    conflict = client.post(f"/api/v1/ingest/batches/{batch['id']}/approve", json={})
    assert conflict.status_code == 409
