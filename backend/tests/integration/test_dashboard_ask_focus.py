"""Dashboard + context Ask focus tests (V1.1c/d)."""

from __future__ import annotations

from backend.tests.helpers.db import make_client


def test_dashboard_returns_shipments_alerts_and_data_status() -> None:
    client = make_client()
    client.post(
        "/api/v1/shipments",
        json={
            "title": "Dash shipment",
            "product_text": "Cotton T-shirts",
            "origin": "BD",
            "destination": "IN",
            "hs_code_working": "6109.10",
            "as_of_date": "2026-06-01",
            "invoice_value": "1000",
            "currency": "USD",
            "incoterm": "CIF",
            "qty": 1,
        },
    )
    response = client.get("/api/v1/dashboard")
    assert response.status_code == 200
    body = response.json()
    assert len(body["shipments"]) >= 1
    assert body["data_status"]["hs_chapter"] == "61"
    assert "Bangladesh" in body["data_status"]["corridor"]
    assert isinstance(body["alerts"], list)


def test_ask_focus_tariff_without_query() -> None:
    client = make_client()
    response = client.post(
        "/api/v1/ask",
        json={
            "focus": "tariff",
            "hs_code": "6109.10",
            "origin": "BD",
            "destination": "IN",
            "as_of": "2026-06-01",
            "orchestration_mode": "adaptive",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert "tariff_lookup" in body["tools_invoked"]
    assert body["result"]["tariffs"]
    assert float(body["result"]["tariffs"][0]["rate"]) == 20.0


def test_ask_focus_shipment_gaps() -> None:
    client = make_client()
    created = client.post(
        "/api/v1/shipments",
        json={
            "title": "Gaps shipment",
            "product_text": "Cotton T-shirts",
            "origin": "BD",
            "destination": "IN",
            "hs_code_working": "6109.10",
            "as_of_date": "2026-06-01",
            "invoice_value": "1000",
            "currency": "USD",
            "incoterm": "CIF",
            "qty": 1,
        },
    ).json()
    response = client.post(
        "/api/v1/ask",
        json={
            "focus": "shipment_gaps",
            "shipment_id": created["id"],
            "orchestration_mode": "adaptive",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert "checklist_build" in body["tools_invoked"]
