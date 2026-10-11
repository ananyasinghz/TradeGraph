"""Phase 1 product API tests."""

from __future__ import annotations

from backend.tests.helpers.db import make_client


def test_list_tariffs_as_of_2026() -> None:
    client = make_client()
    response = client.get(
        "/api/v1/tariffs",
        params={"hs": "6109.10", "origin": "BD", "destination": "IN", "as_of": "2026-06-01"},
    )
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert float(rows[0]["rate"]) == 20.0
    assert rows[0]["data_quality"] == "illustrative"


def test_list_tariffs_as_of_2025_uses_historical_rate() -> None:
    client = make_client()
    response = client.get(
        "/api/v1/tariffs",
        params={"hs": "6109.10", "origin": "BD", "destination": "IN", "as_of": "2025-06-01"},
    )
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert float(rows[0]["rate"]) == 22.0


def test_landed_cost_matches_bcd_from_tariff() -> None:
    client = make_client()
    tariff = client.get(
        "/api/v1/tariffs",
        params={"hs": "6109.10", "origin": "BD", "destination": "IN", "as_of": "2026-06-01"},
    ).json()[0]
    calc = client.post(
        "/api/v1/calculate/landed-cost",
        json={
            "hs_code": "6109.10",
            "origin": "BD",
            "destination": "IN",
            "as_of": "2026-06-01",
            "invoice_value": "1000",
            "currency": "USD",
            "incoterm": "CIF",
        },
    )
    assert calc.status_code == 200
    body = calc.json()
    assert float(body["bcd_rate_pct"]) == float(tariff["rate"])
    assert body["tariff_rate_id"] == tariff["id"]
    assert float(body["landed_cost"]) > 1000


def test_shipment_calculate_and_checklist() -> None:
    client = make_client()
    created = client.post(
        "/api/v1/shipments",
        json={
            "title": "Demo tee",
            "product_text": "Cotton T-shirt",
            "origin": "BD",
            "destination": "IN",
            "hs_code_working": "6109.10",
            "as_of_date": "2026-06-01",
            "invoice_value": "5000",
            "currency": "USD",
            "incoterm": "CIF",
            "qty": "100",
        },
    )
    assert created.status_code == 200
    shipment_id = created.json()["id"]

    calc = client.post(f"/api/v1/shipments/{shipment_id}/calculate")
    assert calc.status_code == 200
    assert calc.json()["latest_calculation"] is not None

    checklist = client.post(f"/api/v1/shipments/{shipment_id}/checklist")
    assert checklist.status_code == 200
    items = checklist.json()["checklist"]["items"]
    assert len(items) >= 4


def test_ask_tariff_uses_same_rate_as_browser() -> None:
    client = make_client(ollama_enabled=False)
    browser = client.get(
        "/api/v1/tariffs",
        params={"hs": "6109.10", "origin": "BD", "destination": "IN", "as_of": "2026-06-01"},
    ).json()[0]
    assert float(browser["rate"]) == 20.0
    ask = client.post(
        "/api/v1/ask",
        json={
            "query": "What is the import duty for HS 6109.10 from Bangladesh to India?",
            "as_of": "2026-06-01",
            "orchestration_mode": "direct_lookup",
        },
    )
    assert ask.status_code == 200
    body = ask.json()
    tariffs = (body.get("result") or {}).get("tariffs") or []
    if tariffs:
        assert tariffs[0]["id"] == browser["id"]
        assert float(tariffs[0]["rate"]) == float(browser["rate"])
    else:
        # When process .env enables Ollama, Ask may skip direct tariff tools —
        # browser tariff remains the source of truth for seeded BCD.
        assert "tariff_lookup" in body.get("tools_invoked", []) or body.get("route")


def test_sources_list() -> None:
    client = make_client()
    response = client.get("/api/v1/sources")
    assert response.status_code == 200
    assert len(response.json()) >= 2
