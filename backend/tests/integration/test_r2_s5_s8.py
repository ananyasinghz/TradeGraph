"""R2 S5-S8: schema enrichment, sources lifecycle, classification, snapshots."""

from __future__ import annotations

from pathlib import Path

from backend.tests.helpers.db import make_client


def test_sources_have_checksum_and_no_live_claim() -> None:
    client = make_client()
    sources = client.get("/api/v1/sources")
    assert sources.status_code == 200
    rows = sources.json()
    assert rows
    for row in rows:
        assert row["live_claim"] is False
        assert row["live_government_feed"] is False
        assert row["status"] == "published"
        assert row["checksum"]
        assert "live government feed" in (row.get("honesty_notice") or "").lower()


def test_source_status_machine_and_archive(tmp_path: Path) -> None:
    client = make_client()
    archive = tmp_path / "sample_notice.txt"
    archive.write_text("illustrative CBIC excerpt for archive test", encoding="utf-8")

    created = client.post(
        "/api/v1/sources/archive",
        json={
            "title": "Archived test notice",
            "publisher": "TradeGraph test",
            "archive_path": str(archive),
            "source_id": "src_test_archive_s6",
            "notes": "fixture",
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["status"] == "fetched"
    assert body["checksum"]
    assert body["live_claim"] is False
    assert body["archive_path"]

    bad = client.post(
        "/api/v1/sources/src_test_archive_s6/transition",
        json={"status": "published"},
    )
    assert bad.status_code == 400
    assert bad.json()["error"]["code"] == "INVALID_STATUS_TRANSITION"

    for status in ("parsed", "awaiting_review", "approved", "published"):
        step = client.post(
            "/api/v1/sources/src_test_archive_s6/transition",
            json={"status": status},
        )
        assert step.status_code == 200, step.text
        assert step.json()["status"] == status


def test_classification_candidates_and_confirm() -> None:
    client = make_client()
    suggest = client.post(
        "/api/v1/classification/candidates",
        json={"product_text": "100% cotton knitted T-shirts", "chapter": "61", "limit": 5},
    )
    assert suggest.status_code == 200
    candidates = suggest.json()["candidates"]
    assert candidates
    assert candidates[0]["hs_code"].startswith("6109")

    created = client.post(
        "/api/v1/shipments",
        json={
            "title": "Classify me",
            "product_text": "100% cotton knitted T-shirts",
            "origin": "BD",
            "destination": "IN",
            "hs_code_working": None,
            "as_of_date": "2026-06-01",
            "invoice_value": "1000",
            "currency": "USD",
            "incoterm": "CIF",
            "qty": 1,
        },
    )
    assert created.status_code == 200
    shipment_id = created.json()["id"]
    assert created.json()["line_items"]

    cand = client.get(f"/api/v1/shipments/{shipment_id}/classification/candidates")
    assert cand.status_code == 200
    top = cand.json()["candidates"][0]["hs_code"]

    confirm = client.post(
        f"/api/v1/shipments/{shipment_id}/classification/confirm",
        json={"hs_code": top},
    )
    assert confirm.status_code == 200
    assert confirm.json()["hs_code_working"] == top

    workspace = client.get(f"/api/v1/shipments/{shipment_id}/workspace")
    assert workspace.status_code == 200
    assert workspace.json()["classification_candidates"]


def test_calculation_snapshot_estimate_vs_customs() -> None:
    client = make_client()
    created = client.post(
        "/api/v1/shipments",
        json={
            "title": "Cost snapshot",
            "product_text": "cotton T-shirts",
            "origin": "BD",
            "destination": "IN",
            "hs_code_working": "6109.10",
            "as_of_date": "2026-06-01",
            "invoice_value": "5000",
            "currency": "USD",
            "incoterm": "CIF",
            "qty": 10,
        },
    )
    shipment_id = created.json()["id"]

    estimate = client.post(
        f"/api/v1/shipments/{shipment_id}/calculate",
        json={"requested_mode": "estimate"},
    )
    assert estimate.status_code == 200
    latest = estimate.json()["latest_calculation"]
    assert latest["calculation_mode"] == "estimate"
    assert "Estimated" in latest["title"]
    assert estimate.json()["calculation_snapshots"]

    customs_blocked = client.post(
        f"/api/v1/shipments/{shipment_id}/calculate",
        json={"requested_mode": "customs"},
    )
    # Seed MFN for 6109.10 is illustrative / incomplete freight → customs unavailable
    assert customs_blocked.status_code == 400
    assert customs_blocked.json()["error"]["code"] == "CUSTOMS_MODE_UNAVAILABLE"

    snaps = client.get(f"/api/v1/shipments/{shipment_id}/calculation-snapshots")
    assert snaps.status_code == 200
    assert len(snaps.json()) >= 1
    assert snaps.json()[0]["calculation_mode"] == "estimate"


def test_shipment_line_item_and_evidence() -> None:
    client = make_client()
    created = client.post(
        "/api/v1/shipments",
        json={
            "title": "Evidence case",
            "product_text": "cotton knitted shirts",
            "origin": "BD",
            "destination": "IN",
            "hs_code_working": "6105.10",
            "as_of_date": "2026-06-01",
            "invoice_value": "2000",
            "currency": "USD",
            "incoterm": "CIF",
            "qty": 1,
        },
    )
    shipment_id = created.json()["id"]
    line = client.post(
        f"/api/v1/shipments/{shipment_id}/line-items",
        json={
            "description": "Extra carton of shirts",
            "line_number": 2,
            "hs_code": "6105.10",
            "qty": "5",
            "unit_value": "40",
        },
    )
    assert line.status_code == 200
    assert len(line.json()["line_items"]) >= 2

    evidence = client.post(
        f"/api/v1/shipments/{shipment_id}/evidence",
        json={
            "kind": "citation",
            "label": "Seed tariff source",
            "source_document_id": "src_in_cbic_illustrative_2026",
            "excerpt": "Illustrative schedule excerpt",
        },
    )
    assert evidence.status_code == 200
    assert evidence.json()["evidence"]
