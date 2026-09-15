"""V1.1e documents statuses, drafts, why-required."""

from __future__ import annotations

from backend.tests.helpers.db import make_client


def _create_shipment(client) -> str:  # type: ignore[no-untyped-def]
    created = client.post(
        "/api/v1/shipments",
        json={
            "title": "Docs test shipment",
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
    return created.json()["id"]


def test_document_status_draft_export_and_why() -> None:
    client = make_client()
    sid = _create_shipment(client)

    built = client.post(f"/api/v1/shipments/{sid}/checklist")
    assert built.status_code == 200
    items = built.json()["checklist"]["items"]
    assert items
    assert items[0]["status"] == "not_started"
    doc_code = items[0]["doc_code"]

    patched = client.patch(
        f"/api/v1/shipments/{sid}/documents/{doc_code}",
        json={"status": "draft"},
    )
    assert patched.status_code == 200
    updated = next(i for i in patched.json()["checklist"]["items"] if i["doc_code"] == doc_code)
    assert updated["status"] == "draft"
    assert updated["done"] is False

    ready = client.patch(
        f"/api/v1/shipments/{sid}/documents/{doc_code}",
        json={"status": "ready"},
    )
    assert ready.status_code == 200
    ready_item = next(i for i in ready.json()["checklist"]["items"] if i["doc_code"] == doc_code)
    assert ready_item["done"] is True

    inv = client.get(f"/api/v1/shipments/{sid}/drafts/commercial_invoice")
    assert inv.status_code == 200
    assert "COMMERCIAL INVOICE" in inv.json()["text"]
    assert inv.json()["filename"].endswith(".txt")

    pack = client.get(f"/api/v1/shipments/{sid}/drafts/packing_list")
    assert pack.status_code == 200
    assert "PACKING LIST" in pack.json()["text"]

    chk = client.get(f"/api/v1/shipments/{sid}/drafts/checklist")
    assert chk.status_code == 200
    assert "DOCUMENT CHECKLIST" in chk.json()["text"]

    why = client.get(
        "/api/v1/document-requirements/why",
        params={"doc_code": doc_code, "origin": "BD", "destination": "IN", "hs": "6109.10"},
    )
    assert why.status_code == 200
    body = why.json()
    assert body["doc_code"] == doc_code
    assert body["why"]
    assert "source_tip" in body
