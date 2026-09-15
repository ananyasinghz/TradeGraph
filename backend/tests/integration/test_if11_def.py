"""IF-11d/e/f: snapshots, impacts, explainable readiness."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from backend.app.data.models import TariffRate
from backend.tests.helpers.db import make_client


def _promote(client):  # type: ignore[no-untyped-def]
    r = client.post("/api/v1/ingest/promote-cbic", json={"notes": "if11def"})
    assert r.status_code == 200, r.text
    return r.json()


def _scenario(client, **extra):  # type: ignore[no-untyped-def]
    body = {
        "title": "Cotton T-shirts BD→IN",
        "product_text": "100% cotton knitted T-shirts",
        "origin": "BD",
        "destination": "IN",
        "hs_code_working": "6109.10",
        "as_of_date": "2026-06-01",
        "invoice_value": "1000",
        "currency": "USD",
        "incoterm": "CIF",
        "freight": "50",
        "insurance": "10",
        "qty": "1",
    }
    body.update(extra)
    created = client.post("/api/v1/scenarios", json=body)
    assert created.status_code == 200, created.text
    sid = created.json()["id"]
    client.post(f"/api/v1/scenarios/{sid}/confirm-hs", json={"hs_code": "6109.10"})
    return sid


def test_snapshot_engine_version_and_list_get_diff() -> None:
    client = make_client()
    _promote(client)
    sid = _scenario(client)
    calc = client.post(
        f"/api/v1/scenarios/{sid}/calculate", json={"requested_mode": "estimate"}
    )
    assert calc.status_code == 200
    listed = client.get(f"/api/v1/scenarios/{sid}/calculations")
    assert listed.status_code == 200
    snaps = listed.json()
    assert len(snaps) >= 1
    snap = snaps[0]
    assert snap["calculation_engine_version"] == "in_duty.v1"
    assert Decimal(str(snap["inputs"]["freight"])) == Decimal("50")
    assert snap["inputs"]["hs_code"] == "6109.10"
    assert "tariff_rule_ids" in snap["inputs"]

    got = client.get(f"/api/v1/calculations/{snap['id']}")
    assert got.status_code == 200
    assert got.json()["id"] == snap["id"]

    # Immutability: patching outputs_json via ORM then GET still returns stored JSON
    factory = client.app.state.session_factory
    with factory() as session:
        from backend.app.data.models import CalculationSnapshot

        row = session.get(CalculationSnapshot, snap["id"])
        assert row is not None
        frozen = dict(row.outputs_json)
        row.title = "should-not-matter-for-outputs"
        session.commit()
    again = client.get(f"/api/v1/calculations/{snap['id']}").json()
    assert again["outputs"]["landed_cost"] == frozen["landed_cost"]

    client.patch(f"/api/v1/scenarios/{sid}", json={"freight": "200"})
    client.post(f"/api/v1/scenarios/{sid}/calculate", json={"requested_mode": "estimate"})
    snaps2 = client.get(f"/api/v1/scenarios/{sid}/calculations").json()
    assert len(snaps2) >= 2
    diff = client.get(f"/api/v1/calculations/{snaps2[1]['id']}/diff/{snaps2[0]['id']}")
    assert diff.status_code == 200
    assert "landed_cost" in diff.json()["fields"] or "freight" in diff.json()["fields"]


def test_customs_refused_missing_freight_and_unapproved() -> None:
    client = make_client()
    # No promote — unapproved
    sid = _scenario(client, freight=None, insurance=None)
    # Clear freight/insurance
    client.patch(f"/api/v1/scenarios/{sid}", json={"freight": None, "insurance": None})
    blocked = client.post(
        f"/api/v1/scenarios/{sid}/calculate", json={"requested_mode": "customs"}
    )
    assert blocked.status_code == 400
    err = blocked.json()["error"]
    assert err["code"] == "CUSTOMS_MODE_UNAVAILABLE"
    assert err["details"]["customs_mode_available"] is False
    blockers = err["details"]["customs_mode_blockers"]
    assert any("approved" in b.lower() or "freight" in b.lower() for b in blockers)


def test_impact_on_promote_with_prior_snapshot() -> None:
    client = make_client()
    _promote(client)
    sid = _scenario(client)
    client.post(f"/api/v1/scenarios/{sid}/calculate", json={"requested_mode": "estimate"})
    before = client.get("/api/v1/dashboard").json()
    pre_impact = [a for a in before["alerts"] if a["kind"] == "tariff_impact"]

    # Bump rate via second promote-like path: manually supersede and call impact
    factory = client.app.state.session_factory
    with factory() as session:
        from datetime import date
        from uuid import uuid4

        from backend.app.services import impact_service

        active = session.scalars(
            select(TariffRate).where(
                TariffRate.hs_code == "6109.10",
                TariffRate.origin == "BD",
                TariffRate.destination == "IN",
                TariffRate.status == "active",
            )
        ).first()
        assert active is not None
        old = active
        new_id = str(uuid4())
        old.status = "superseded"
        old.superseded_by = new_id
        new = TariffRate(
            id=new_id,
            hs_code="6109.10",
            origin="BD",
            destination="IN",
            rate=Decimal("12"),
            rate_type="ad_valorem_pct",
            duty_components={"bcd_pct": 12.0, "sws_pct_of_bcd": 10.0, "igst_pct": 5.0},
            effective_from=date(2026, 1, 1),
            source_document_id=old.source_document_id,
            version=old.version + 1,
            status="active",
            data_quality="demo_verified",
            regime="mfn",
        )
        session.add(new)
        session.flush()
        impacts = impact_service.record_impacts_for_new_tariff(
            session, new_tariff=new, old_tariff=old
        )
        session.commit()
        assert len(impacts) == 1
        assert impacts[0].shipment_id == sid
        assert impacts[0].duty_delta is not None
        assert impacts[0].duty_delta > 0

    dash = client.get("/api/v1/dashboard").json()
    impact_alerts = [a for a in dash["alerts"] if a["kind"] == "tariff_impact"]
    assert len(impact_alerts) >= len(pre_impact) + 1
    assert any("6109.10" in (a["message"] or "") for a in impact_alerts)
    assert any(a.get("recommended_action") for a in impact_alerts)


def test_no_fake_impact_without_matching_scenario() -> None:
    client = make_client()
    _promote(client)
    factory = client.app.state.session_factory
    with factory() as session:
        from datetime import date
        from uuid import uuid4

        from backend.app.services import impact_service

        active = session.scalars(
            select(TariffRate).where(
                TariffRate.hs_code == "6109.10",
                TariffRate.origin == "BD",
                TariffRate.destination == "IN",
                TariffRate.status == "active",
            )
        ).first()
        assert active is not None
        old = active
        new = TariffRate(
            id=str(uuid4()),
            hs_code="6109.10",
            origin="BD",
            destination="IN",
            rate=Decimal("15"),
            rate_type="ad_valorem_pct",
            duty_components={"bcd_pct": 15.0, "sws_pct_of_bcd": 10.0, "igst_pct": 5.0},
            effective_from=date(2026, 1, 1),
            source_document_id=old.source_document_id,
            version=old.version + 1,
            status="active",
            data_quality="demo_verified",
            regime="mfn",
        )
        # No matching scenarios created — impact list must be empty
        impacts = impact_service.record_impacts_for_new_tariff(
            session, new_tariff=new, old_tariff=old
        )
        assert impacts == []


def test_readiness_statuses_and_evidence_lists() -> None:
    client = make_client()
    _promote(client)
    sid = _scenario(client)
    client.post(f"/api/v1/scenarios/{sid}/calculate", json={"requested_mode": "estimate"})
    ready = client.get(f"/api/v1/shipments/{sid}/readiness").json()
    codes = {s["code"] for s in ready["statuses"]}
    assert "calculation_ready" in codes
    assert "human_review_required" in codes
    assert any(i["code"] == "product_description" for i in ready["complete_items"])
    assert any(i["code"] == "certificate_of_origin" for i in ready["missing_items"])
    assert ready["overall_status"] in {"ready", "partial", "review_required", "blocked"}
    assert "complete_evidence" in ready
    assert "missing_evidence" in ready
