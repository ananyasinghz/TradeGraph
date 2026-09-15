"""Shipment workspace aggregation tests (V1.1b)."""

from __future__ import annotations

from backend.tests.helpers.db import make_client


def test_shipment_workspace_aggregates_tariff_fta_and_risks() -> None:
    client = make_client()
    created = client.post(
        "/api/v1/shipments",
        json={
            "title": "Workspace demo",
            "product_text": "Cotton T-shirts",
            "origin": "BD",
            "destination": "IN",
            "hs_code_working": "6109.10",
            "as_of_date": "2026-06-01",
            "invoice_value": "5000",
            "currency": "USD",
            "incoterm": "CIF",
            "qty": 1,
        },
    )
    assert created.status_code == 200
    shipment_id = created.json()["id"]

    ws = client.get(f"/api/v1/shipments/{shipment_id}/workspace")
    assert ws.status_code == 200
    body = ws.json()
    assert body["shipment"]["id"] == shipment_id
    assert body["tariff"] is not None
    assert float(body["tariff"]["rate"]) == 10.0
    assert body["fta"] is not None
    assert body["fta"]["status"] in {
        "eligible",
        "potentially_eligible",
        "needs_evidence",
        "ineligible",
        "not_covered",
        "rule_not_available",
        "unknown",
    }
    assert isinstance(body["risks"], list) and len(body["risks"]) >= 1
    assert isinstance(body["next_actions"], list) and len(body["next_actions"]) >= 1
    assert "6109.10" in body["summary"]

    client.post(f"/api/v1/shipments/{shipment_id}/calculate", json={})
    client.post(f"/api/v1/shipments/{shipment_id}/checklist", json={})
    refreshed = client.get(f"/api/v1/shipments/{shipment_id}/workspace").json()
    assert refreshed["calculation"] is not None
    assert refreshed["checklist"] is not None
    assert "landed cost" in refreshed["summary"].lower()
