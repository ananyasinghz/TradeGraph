"""Integration: component provenance, preferential CoO gate, coverage, impacts."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select

from backend.app.data.models import (
    IngestionBatch,
    IngestionProposal,
    ScenarioImpact,
    TariffRate,
)
from backend.app.domain.trade import ShipmentCreate
from backend.app.services import impact_service, shipment_service
from backend.app.services.component_provenance import applicable_stack_signature
from backend.tests.helpers.db import make_client


def test_duty_structure_exposes_component_provenance() -> None:
    client = make_client()
    response = client.get(
        "/api/v1/duty/structure",
        params={
            "hs": "6109.10",
            "origin": "BD",
            "destination": "IN",
            "as_of": "2026-06-01",
            "assessable_value": "100000",
            "currency": "INR",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["component_sources"]
    by_key = {c["component_key"]: c for c in body["component_sources"]}
    assert by_key["bcd_pct"]["data_quality"] == "curated_official_backed"
    assert by_key["sws_pct_of_bcd"]["data_quality"] == "curated_official_backed"
    assert by_key["bcd_pct"]["source_key"]
    assert body["coverage"]["bcd_pct"] == "curated_official_backed"
    bcd_line = next(r for r in body["stack"] if r["code"] == "BCD")
    assert bcd_line["data_quality"] == "curated_official_backed"
    assert float(body["total_duties"]) == 49860.0


def test_approve_igst_partial_keeps_curated_bcd(tmp_path) -> None:
    client = make_client()
    factory = client.app.state.session_factory
    archive = tmp_path / "igst_partial.json"
    archive.write_text('{"notice":"igst-partial"}', encoding="utf-8")
    checksum = "a" * 32
    with factory() as session:
        before = session.scalars(
            select(TariffRate).where(
                TariffRate.hs_code == "6109.10",
                TariffRate.origin == "BD",
                TariffRate.destination == "IN",
                TariffRate.status == "active",
                TariffRate.regime == "mfn",
            )
        ).first()
        assert before is not None
        curated_bcd = float((before.duty_components or {}).get("bcd_pct") or before.rate)

        batch = IngestionBatch(
            id=str(uuid4()),
            source_key="igst_partial_test",
            archive_path=str(archive),
            checksum=checksum,
            title="IGST partial test pack",
            publisher="pytest",
            status="pending_review",
            effective_from=date(2025, 9, 17),
            validation_summary={"ok": 1, "error": 0},
            created_at=datetime.now(UTC),
        )
        session.add(batch)
        session.flush()
        session.add(
            IngestionProposal(
                id=str(uuid4()),
                batch_id=batch.id,
                kind="tariff_rate",
                payload_json={
                    "hs_code": "6109.10",
                    "origin": "BD",
                    "destination": "IN",
                    "rate": 5.0,
                    "rate_type": "ad_valorem_pct",
                    "duty_components": {
                        "igst_pct": 5.0,
                        "_partial_components": ["igst_pct"],
                        "_provenance": {
                            "igst_pct": {
                                "value": 5.0,
                                "source_key": "live_igst_notif_9_2025",
                                "data_quality": "source_verified",
                                "effective_from": "2025-09-17",
                                "notes": "IGST-only partial",
                            },
                            "bcd_pct": {
                                "value": 0.0,
                                "data_quality": "source_verified",
                                "notes": "must not wipe curated BCD",
                            },
                        },
                    },
                    "effective_from_hint": "2025-09-17",
                    "notes": "partial IGST",
                },
                validation_status="ok",
                validation_errors=[],
                publish_status="pending",
            )
        )
        session.commit()
        batch_id = batch.id

    approved = client.post(
        f"/api/v1/ingest/batches/{batch_id}/approve",
        json={"notes": "igst partial merge"},
    )
    assert approved.status_code == 200, approved.text

    with factory() as session:
        after = session.scalars(
            select(TariffRate).where(
                TariffRate.hs_code == "6109.10",
                TariffRate.origin == "BD",
                TariffRate.destination == "IN",
                TariffRate.status == "active",
                TariffRate.regime == "mfn",
            )
        ).first()
        assert after is not None
        assert float(after.rate) == curated_bcd
        comps = after.duty_components or {}
        assert float(comps["bcd_pct"]) == curated_bcd
        assert float(comps["igst_pct"]) == 5.0
        assert float(comps["sws_pct_of_bcd"]) == 10.0
        prov = comps.get("_provenance") or {}
        assert prov["bcd_pct"]["data_quality"] == "curated_official_backed"
        assert prov["igst_pct"]["data_quality"] == "source_verified"


def test_preferential_blocked_without_coo_applied_with_coo() -> None:
    client = make_client()
    created = client.post(
        "/api/v1/shipments",
        json={
            "title": "Pref CoO gate",
            "product_text": "100% cotton knitted T-shirts",
            "origin": "BD",
            "destination": "IN",
            "as_of_date": "2026-06-01",
            "invoice_value": "100000",
            "currency": "INR",
            "incoterm": "CIF",
            "freight": "0",
            "insurance": "0",
            "hs_code_working": "6109.10",
        },
    )
    assert created.status_code == 200, created.text
    sid = created.json()["id"]

    blocked = client.post(f"/api/v1/shipments/{sid}/compare-fta")
    assert blocked.status_code == 200, blocked.text
    body = blocked.json()
    assert body["preferential_applied"] is False
    assert body["preferential_status"] != "eligible"
    assert body["preferential_blocked_reason"]
    mfn_duties = float(body["without_preferential"]["outputs"]["total_duties_taxes"])
    pref_duties = float(body["with_preferential"]["outputs"]["total_duties_taxes"])
    assert pref_duties == mfn_duties

    upload = client.post(
        f"/api/v1/shipments/{sid}/uploads",
        data={"doc_code": "certificate_of_origin"},
        files={"file": ("coo.txt", b"certificate stub", "text/plain")},
    )
    assert upload.status_code == 200, upload.text

    applied = client.post(
        f"/api/v1/shipments/{sid}/compare-fta",
        json={"origin_criteria_met": True, "rvc_pct": "55"},
    )
    assert applied.status_code == 200, applied.text
    ok = applied.json()
    assert ok["preferential_applied"] is True
    assert ok["preferential_status"] == "eligible"
    assert ok["preferential_blocked_reason"] is None
    assert float(ok["preferential_rate_pct"]) == 5.0
    assert float(ok["with_preferential"]["outputs"]["total_duties_taxes"]) < float(
        ok["without_preferential"]["outputs"]["total_duties_taxes"]
    )


def test_coverage_matrix_ch62_bcd_zero() -> None:
    client = make_client()
    response = client.get("/api/v1/duty/coverage", params={"origin": "BD", "destination": "IN"})
    assert response.status_code == 200, response.text
    body = response.json()
    chapters = {c["chapter"]: c for c in body["chapters"]}
    assert "61" in chapters
    assert chapters["61"]["bcd_rates"] >= 1
    assert chapters["61"]["classification_codes"] >= 1
    assert "62" in chapters
    assert chapters["62"]["classification_codes"] >= 1
    assert chapters["62"]["bcd_rates"] == 0
    assert chapters["62"]["igst_rates"] == 0


def test_impact_only_when_stack_signature_changes() -> None:
    client = make_client()
    factory = client.app.state.session_factory
    with factory() as session:
        old = session.scalars(
            select(TariffRate).where(
                TariffRate.hs_code == "6109.10",
                TariffRate.origin == "BD",
                TariffRate.destination == "IN",
                TariffRate.status == "active",
                TariffRate.regime == "mfn",
            )
        ).first()
        assert old is not None
        ship_out = shipment_service.create_shipment(
            session,
            ShipmentCreate(
                title="Impact signature case",
                product_text="cotton knitted T-shirts",
                origin="BD",
                destination="IN",
                as_of_date=date(2026, 6, 1),
                invoice_value=Decimal("100000"),
                currency="INR",
                incoterm="CIF",
                freight=Decimal("0"),
                insurance=Decimal("0"),
                hs_code_working="6109.10",
            ),
        )
        shipment_service.calculate_shipment(session, ship_out.id)
        session.commit()

        churn_comps = dict(old.duty_components or {})
        prov = dict(churn_comps.get("_provenance") or {})
        igst_block = dict(prov.get("igst_pct") or {})
        igst_block["notes"] = "archive byte churn only"
        prov["igst_pct"] = igst_block
        churn_comps["_provenance"] = prov
        churn = TariffRate(
            id=str(uuid4()),
            hs_code=old.hs_code,
            origin=old.origin,
            destination=old.destination,
            rate=old.rate,
            rate_type=old.rate_type,
            duty_components=churn_comps,
            agreement_id=old.agreement_id,
            effective_from=old.effective_from,
            effective_to=None,
            source_document_id=old.source_document_id,
            version=(old.version or 1) + 1,
            status="active",
            data_quality=old.data_quality,
            regime="mfn",
        )
        assert applicable_stack_signature(old.duty_components) == applicable_stack_signature(
            churn.duty_components
        )
        none = impact_service.record_impacts_for_new_tariff(
            session, new_tariff=churn, old_tariff=old
        )
        assert none == []

        changed_comps = dict(old.duty_components or {})
        changed_comps["igst_pct"] = 12.0
        prov2 = dict(changed_comps.get("_provenance") or {})
        prov2["igst_pct"] = {
            "value": 12.0,
            "data_quality": "source_verified",
            "source_key": "live_igst_change",
        }
        changed_comps["_provenance"] = prov2
        changed = TariffRate(
            id=str(uuid4()),
            hs_code=old.hs_code,
            origin=old.origin,
            destination=old.destination,
            rate=old.rate,
            rate_type=old.rate_type,
            duty_components=changed_comps,
            agreement_id=old.agreement_id,
            effective_from=old.effective_from,
            effective_to=None,
            source_document_id=old.source_document_id,
            version=(old.version or 1) + 2,
            status="active",
            data_quality="source_verified",
            regime="mfn",
        )
        impacts = impact_service.record_impacts_for_new_tariff(
            session, new_tariff=changed, old_tariff=old
        )
        assert len(impacts) >= 1
        session.commit()

        rows = session.scalars(
            select(ScenarioImpact).where(ScenarioImpact.shipment_id == ship_out.id)
        ).all()
        assert rows
