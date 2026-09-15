"""IF-2/IF-3/IF-4 integration: pipeline, corridors, publish gate."""

from __future__ import annotations

from backend.app.integrations.core.registry import reset_registry_for_tests
from backend.tests.helpers.db import make_client


def setup_function() -> None:
    reset_registry_for_tests()


def test_corridors_and_coverage_api() -> None:
    client = make_client()
    countries = client.get("/api/v1/countries").json()
    assert {c["code"] for c in countries} >= {"BD", "IN"}
    corridors = client.get("/api/v1/corridors").json()
    assert any(
        c["origin_country"] == "BD" and c["destination_country"] == "IN" for c in corridors
    )
    coverage = client.get(
        "/api/v1/source-coverage",
        params={"corridor_id": "corr_bd_in", "capability": "tariff_lookup"},
    ).json()
    assert len(coverage) >= 1


def test_pipeline_ingest_via_registry() -> None:
    client = make_client()
    response = client.post(
        "/api/v1/ingest/run",
        json={"source_key": "cbic_notification_2026_q3", "force": True},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending_review"
    assert body["validation_summary"]["pipeline"] == "integrations.v1"
    assert int(body["validation_summary"]["ok"]) >= 1
    assert int(body["validation_summary"]["error"]) >= 1  # invalid HS in fixture


def test_publish_gate_blocks_then_approve_works() -> None:
    client = make_client()
    batch = client.post(
        "/api/v1/ingest/run",
        json={"source_key": "cbic_notification_2026_q3", "force": True},
    ).json()
    approved = client.post(
        f"/api/v1/ingest/batches/{batch['id']}/approve",
        json={"notes": "IF-4 gate"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["published_source_id"]
