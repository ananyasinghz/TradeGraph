"""Shipment open/closed/discard lifecycle."""

from __future__ import annotations

from backend.tests.helpers.db import make_client


def _create(client):
    return client.post(
        "/api/v1/shipments",
        json={
            "title": "Lifecycle tee",
            "product_text": "100% cotton shirts",
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


def test_create_is_open_and_list_filters() -> None:
    client = make_client()
    created = _create(client)
    assert created["lifecycle"] == "open"
    assert created["status"] == "open"

    open_rows = client.get("/api/v1/shipments?lifecycle=open").json()
    assert any(r["id"] == created["id"] for r in open_rows)

    closed = client.post(f"/api/v1/shipments/{created['id']}/close").json()
    assert closed["lifecycle"] == "closed"
    assert closed["closed_at"] is not None

    open_rows2 = client.get("/api/v1/shipments?lifecycle=open").json()
    assert all(r["id"] != created["id"] for r in open_rows2)
    closed_rows = client.get("/api/v1/shipments?lifecycle=closed").json()
    assert any(r["id"] == created["id"] for r in closed_rows)

    tl = client.get(f"/api/v1/scenarios/{created['id']}/timeline").json()
    assert any(e["event_type"] == "case_closed" for e in tl["events"])


def test_closed_blocks_update_until_reopen() -> None:
    client = make_client()
    created = _create(client)
    client.post(f"/api/v1/shipments/{created['id']}/close")
    blocked = client.patch(
        f"/api/v1/shipments/{created['id']}",
        json={"freight": "10"},
    )
    assert blocked.status_code == 409

    client.post(f"/api/v1/shipments/{created['id']}/reopen")
    ok = client.patch(
        f"/api/v1/shipments/{created['id']}",
        json={"freight": "10"},
    )
    assert ok.status_code == 200


def test_discard_soft_deletes() -> None:
    client = make_client()
    created = _create(client)
    discarded = client.delete(f"/api/v1/shipments/{created['id']}")
    assert discarded.status_code == 200
    assert discarded.json()["lifecycle"] == "discarded"
    open_rows = client.get("/api/v1/shipments?lifecycle=open").json()
    assert all(r["id"] != created["id"] for r in open_rows)
    all_rows = client.get("/api/v1/shipments?lifecycle=all").json()
    assert all(r["id"] != created["id"] for r in all_rows)
