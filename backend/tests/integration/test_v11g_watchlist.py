"""V1.1g shipment-linked watchlist alerts."""

from __future__ import annotations

from backend.tests.helpers.db import make_client


def test_watch_shipment_names_affected_in_changes() -> None:
    client = make_client()
    created = client.post(
        "/api/v1/shipments",
        json={
            "title": "Watched cotton tees",
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
    sid = created.json()["id"]

    watched = client.post("/api/v1/watchlist", json={"shipment_id": sid})
    assert watched.status_code == 200
    body = watched.json()
    assert body["hs_code"] == "6109.10"
    assert body["shipment_id"] == sid
    assert body["shipment_title"] == "Watched cotton tees"

    changes = client.get("/api/v1/watchlist/changes").json()
    assert changes
    matched = [c for c in changes if sid in (c.get("affected_shipment_ids") or [])]
    assert matched
    assert any("Watched cotton tees" in c["summary"] for c in matched)

    dash = client.get("/api/v1/dashboard").json()
    watch_alerts = [a for a in dash["alerts"] if a["kind"] == "watchlist"]
    assert watch_alerts
    assert any(a.get("shipment_id") == sid for a in watch_alerts)
