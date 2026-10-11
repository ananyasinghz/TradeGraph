"""Clearance portal Rounds 2–5: timeline, blocked_reasons, pack, queue, impacts, ask."""

from __future__ import annotations

import io
import zipfile

from backend.tests.helpers.db import make_client


def _create_shipment(client, *, title: str = "R2-R5 case", hs: str | None = "6109.10"):
    payload = {
        "title": title,
        "product_text": "100% cotton knitted T-shirts",
        "origin": "BD",
        "destination": "IN",
        "hs_code_working": hs,
        "as_of_date": "2026-06-01",
        "invoice_value": "5000",
        "currency": "USD",
        "incoterm": "CIF",
        "qty": 10,
    }
    created = client.post("/api/v1/shipments", json=payload)
    assert created.status_code == 200, created.text
    return created.json()["id"]


def test_shipment_timeline_alias() -> None:
    client = make_client()
    sid = _create_shipment(client)
    client.post(
        f"/api/v1/shipments/{sid}/classification/confirm",
        json={"hs_code": "6109.10"},
    )
    timeline = client.get(f"/api/v1/shipments/{sid}/timeline")
    assert timeline.status_code == 200, timeline.text
    body = timeline.json()
    assert body["scenario_id"] == sid
    assert isinstance(body["events"], list)
    assert any(e["event_type"] == "hs_change" for e in body["events"])


def test_blocked_reasons_on_readiness_and_dashboard() -> None:
    client = make_client()
    sid = _create_shipment(client, title="Blocked reasons case", hs=None)

    ready = client.get(f"/api/v1/shipments/{sid}/readiness")
    assert ready.status_code == 200
    reasons = ready.json()["blocked_reasons"]
    assert isinstance(reasons, list)
    assert "missing_hs" in reasons

    dash = client.get("/api/v1/dashboard")
    assert dash.status_code == 200
    cards = dash.json()["shipments"]
    matched = [c for c in cards if c["id"] == sid]
    assert matched
    assert "missing_hs" in matched[0]["blocked_reasons"]


def test_classification_override_hs_persists() -> None:
    client = make_client()
    sid = _create_shipment(client, hs=None)
    confirm = client.post(
        f"/api/v1/shipments/{sid}/classification/confirm",
        json={
            "hs_code": "6109.10",
            "override_hs": "6105.10",
            "reason": "Broker override after fabric review",
        },
    )
    assert confirm.status_code == 200, confirm.text
    body = confirm.json()
    assert body["hs_code_working"] == "6105.10"
    assert body["assumptions"]["hs_override"]["override_hs"] == "6105.10"
    assert "Broker override" in body["assumptions"]["hs_override"]["reason"]

    missing_reason = client.post(
        f"/api/v1/shipments/{sid}/classification/confirm",
        json={"hs_code": "6109.10", "override_hs": "6105.10"},
    )
    assert missing_reason.status_code == 400


def test_pack_zip_contains_drafts_uploads_and_disclaimer() -> None:
    client = make_client()
    sid = _create_shipment(client)
    client.post(f"/api/v1/shipments/{sid}/checklist")
    upload = client.post(
        f"/api/v1/shipments/{sid}/uploads",
        data={"doc_code": "custom_broker_note"},
        files={"file": ("note.txt", b"broker note", "text/plain")},
    )
    assert upload.status_code == 200, upload.text
    assert upload.json()["doc_code"] == "custom_broker_note"

    pack = client.get(f"/api/v1/shipments/{sid}/pack")
    assert pack.status_code == 200, pack.text
    assert pack.headers["content-type"].startswith("application/zip")
    with zipfile.ZipFile(io.BytesIO(pack.content)) as zf:
        names = set(zf.namelist())
        assert "DISCLAIMER.txt" in names
        assert any(n.startswith("drafts/") and "invoice" in n for n in names)
        assert any(n.startswith("drafts/") and "packing" in n for n in names)
        assert any(n.startswith("drafts/") and "checklist" in n for n in names)
        assert any(n.startswith("uploads/") and "note.txt" in n for n in names)
        assert b"not an official" in zf.read("DISCLAIMER.txt").lower()


def test_dashboard_queue_filter() -> None:
    client = make_client()
    blocked_id = _create_shipment(client, title="Queue blocked", hs=None)
    ok_id = _create_shipment(client, title="Queue ok", hs="6109.10")

    all_dash = client.get("/api/v1/dashboard?queue=all")
    assert all_dash.status_code == 200
    all_ids = {c["id"] for c in all_dash.json()["shipments"]}
    assert blocked_id in all_ids
    assert ok_id in all_ids

    blocked_dash = client.get("/api/v1/dashboard?queue=blocked")
    assert blocked_dash.status_code == 200
    blocked_ids = {c["id"] for c in blocked_dash.json()["shipments"]}
    assert blocked_id in blocked_ids
    assert all(
        c.get("readiness_band") == "blocked" for c in blocked_dash.json()["shipments"]
    )

    alerts_dash = client.get("/api/v1/dashboard?queue=alerts")
    assert alerts_dash.status_code == 200
    assert isinstance(alerts_dash.json()["shipments"], list)


def test_impacts_list_endpoint() -> None:
    client = make_client()
    response = client.get("/api/v1/impacts")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_watchlist_changes_include_affected_shipment_ids() -> None:
    client = make_client()
    sid = _create_shipment(client, title="Watchlist affected")
    watched = client.post("/api/v1/watchlist", json={"shipment_id": sid})
    assert watched.status_code == 200
    changes = client.get("/api/v1/watchlist/changes")
    assert changes.status_code == 200
    rows = changes.json()
    assert rows
    assert any(sid in (c.get("affected_shipment_ids") or []) for c in rows)


def test_ask_history_and_next_action_code() -> None:
    client = make_client()
    sid = _create_shipment(client, hs=None)
    ask = client.post(
        "/api/v1/ask",
        json={
            "focus": "tariff",
            "shipment_id": sid,
            "origin": "BD",
            "destination": "IN",
            "as_of": "2026-06-01",
            "orchestration_mode": "adaptive",
        },
    )
    assert ask.status_code == 200, ask.text
    body = ask.json()
    assert body["next_action"]
    assert body["next_action_code"] in {
        "upload_coo",
        "confirm_hs",
        "add_freight",
        "open_fta",
        "none",
    }
    # Missing HS on focus tariff should nudge confirm_hs.
    assert body["next_action_code"] == "confirm_hs"

    history = client.get(f"/api/v1/shipments/{sid}/ask-history")
    assert history.status_code == 200, history.text
    rows = history.json()
    assert len(rows) >= 1
    assert rows[0]["ask_run_id"] == body["ask_run_id"]
    assert rows[0]["shipment_id"] == sid
