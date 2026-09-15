"""R2/R3 S9-S13: FTA conditions, docs/PDF/uploads, readiness, auth, jobs."""

from __future__ import annotations

import base64

from backend.tests.helpers.db import make_client


def _create_shipment(client, hs: str = "6109.10"):
    created = client.post(
        "/api/v1/shipments",
        json={
            "title": "S9-S13 case",
            "product_text": "100% cotton knitted T-shirts",
            "origin": "BD",
            "destination": "IN",
            "hs_code_working": hs,
            "as_of_date": "2026-06-01",
            "invoice_value": "5000",
            "currency": "USD",
            "incoterm": "CIF",
            "qty": 10,
        },
    )
    assert created.status_code == 200, created.text
    return created.json()["id"]


def test_fta_condition_engine_needs_evidence_then_eligible() -> None:
    client = make_client()
    shipment_id = _create_shipment(client)
    client.post(f"/api/v1/shipments/{shipment_id}/checklist")

    pending = client.post(
        "/api/v1/fta/check",
        json={
            "hs_code": "6109.10",
            "origin": "BD",
            "destination": "IN",
            "as_of": "2026-06-01",
            "shipment_id": shipment_id,
            "conditions": {"origin_criteria_met": False, "rvc_pct": None},
        },
    )
    assert pending.status_code == 200
    assert pending.json()["status"] == "needs_evidence"
    assert pending.json()["conditions"]

    upload = client.post(
        f"/api/v1/shipments/{shipment_id}/uploads",
        data={"doc_code": "certificate_of_origin"},
        files={"file": ("coo.txt", b"certificate stub", "text/plain")},
    )
    assert upload.status_code == 200, upload.text

    eligible = client.post(
        "/api/v1/fta/check",
        json={
            "hs_code": "6109.10",
            "origin": "BD",
            "destination": "IN",
            "as_of": "2026-06-01",
            "shipment_id": shipment_id,
            "conditions": {"origin_criteria_met": True, "rvc_pct": "55"},
        },
    )
    assert eligible.status_code == 200
    assert eligible.json()["status"] == "eligible"
    assert all(c["status"] == "passed" for c in eligible.json()["conditions"])


def test_document_pdf_and_form() -> None:
    client = make_client()
    shipment_id = _create_shipment(client)
    client.post(f"/api/v1/shipments/{shipment_id}/checklist")
    form = client.get(f"/api/v1/shipments/{shipment_id}/forms/commercial_invoice")
    assert form.status_code == 200
    assert form.json()["fields"]

    pdf = client.get(
        f"/api/v1/shipments/{shipment_id}/drafts/commercial_invoice?as_pdf=true"
    )
    assert pdf.status_code == 200
    body = pdf.json()
    assert body["content_type"] == "application/pdf"
    assert body["pdf_base64"]
    raw = base64.b64decode(body["pdf_base64"])
    assert raw.startswith(b"%PDF")


def test_readiness_score_on_workspace() -> None:
    client = make_client()
    shipment_id = _create_shipment(client)
    ready = client.get(f"/api/v1/shipments/{shipment_id}/readiness")
    assert ready.status_code == 200
    assert "score" in ready.json()
    assert ready.json()["band"] in {"blocked", "partial", "ready"}

    workspace = client.get(f"/api/v1/shipments/{shipment_id}/workspace")
    assert workspace.status_code == 200
    assert workspace.json()["readiness"] is not None


def test_auth_whoami_and_forbidden_when_enabled() -> None:
    open_client = make_client()
    who = open_client.get("/api/v1/auth/whoami")
    assert who.status_code == 200
    assert who.json()["auth_enabled"] is False

    locked = make_client(auth_enabled=True)
    denied = locked.get("/api/v1/auth/whoami")
    assert denied.status_code == 401

    ok = locked.get(
        "/api/v1/auth/whoami", headers={"Authorization": "Bearer demo-admin"}
    )
    assert ok.status_code == 200
    assert ok.json()["role"] == "admin"

    viewer = locked.get(
        "/api/v1/auth/audit", headers={"Authorization": "Bearer demo-viewer"}
    )
    assert viewer.status_code == 403


def test_watchlist_impact_job_and_ready() -> None:
    client = make_client()
    job = client.post("/api/v1/jobs/watchlist-impact")
    assert job.status_code == 200
    assert job.json()["job_type"] == "watchlist_impact"

    notes = client.get("/api/v1/notifications")
    assert notes.status_code == 200

    ready = client.get("/api/v1/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    assert ready.json()["database"] == "ok"
