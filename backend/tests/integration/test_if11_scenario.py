"""IF-11a/b/c: honesty status, promote path, trade scenarios."""

from __future__ import annotations

from decimal import Decimal

from backend.tests.helpers.db import make_client


def test_system_status_never_claims_live_for_curated_mirror() -> None:
    client = make_client(live_feed_enabled=True)
    # Fetch curated mirror — must not flip live_government_feed
    fetch = client.post("/api/v1/source-connections/cbic_notification_2026_q3/fetch")
    assert fetch.status_code == 200
    body = client.get("/api/v1/system/status").json()
    assert body["live_government_feed"] is False
    assert body["source_connection_kind"] in {"curated_mirror", "none", "verified_published"}
    assert body["source_connection_kind"] != "live_monitored"
    assert "Curated" in body["source_connection_label"] or "not connected" in body[
        "source_connection_label"
    ].lower()
    assert body["customs_mode_available"] is False
    assert any("approved" in b.lower() for b in body["customs_mode_blockers"])
    assert "approved tariff" in body["customs_mode_hint"].lower()


def test_customs_availability_endpoint_when_zero_approved() -> None:
    client = make_client()
    body = client.get("/api/v1/calculate/customs-availability").json()
    assert body["customs_mode_available"] is False
    assert body["approved_tariff_rule_count"] == 0
    assert "No approved tariff rules are published." in body["customs_mode_blockers"]


def test_promote_cbic_then_lookup_verified_and_customs() -> None:
    client = make_client()
    promote = client.post("/api/v1/ingest/promote-cbic", json={"notes": "test promote"})
    assert promote.status_code == 200, promote.text
    promo = promote.json()
    assert promo["approved_tariff_rule_count"] >= 1
    assert promo["rates_published"] >= 1

    status = client.get("/api/v1/system/status").json()
    assert status["approved_tariff_rule_count"] >= 1
    assert status["last_approved_at"] is not None
    assert status["source_connection_kind"] == "verified_published"
    assert status["source_connection_label"] == "Verified source"
    assert status["customs_mode_available"] is True
    assert status["live_government_feed"] is False

    lookup = client.get(
        "/api/v1/tariffs/lookup",
        params={"hs": "6109.10", "origin": "BD", "destination": "IN", "as_of": "2026-06-01"},
    )
    assert lookup.status_code == 200, lookup.text
    tariff = lookup.json()["tariff"]
    assert tariff is not None
    assert tariff["data_quality"] in {"demo_verified", "source_verified"}

    # Seed illustrative for same HS should be superseded (active illustrative count drops)
    assert status["illustrative_tariff_rule_count"] < status["active_tariff_rule_count"]

    scenario = client.post(
        "/api/v1/scenarios",
        json={
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
        },
    )
    assert scenario.status_code == 200, scenario.text
    sid = scenario.json()["id"]
    assert scenario.json()["freight"] is not None
    assert scenario.json()["organization_id"] == "org_demo"

    confirm = client.post(
        f"/api/v1/scenarios/{sid}/confirm-hs", json={"hs_code": "6109.10"}
    )
    assert confirm.status_code == 200
    assert confirm.json()["hs_confirmed_at"] is not None

    customs = client.post(
        f"/api/v1/scenarios/{sid}/calculate",
        json={"requested_mode": "customs"},
    )
    assert customs.status_code == 200, customs.text
    calc = customs.json()["latest_calculation"]
    assert calc["calculation_mode"] == "customs"
    assert Decimal(str(calc["landed_cost"])) > Decimal(str(calc["assessable_value"]))

    workspace = client.get(f"/api/v1/scenarios/{sid}/workspace").json()
    assert workspace["customs_mode_available"] is True
    assert workspace["shipment"]["freight"] is not None


def test_scenario_org_isolation() -> None:
    client = make_client()
    a = client.post(
        "/api/v1/scenarios",
        headers={"X-Organization-Id": "org_demo"},
        json={
            "title": "Org A",
            "product_text": "cotton shirts",
            "origin": "BD",
            "destination": "IN",
            "hs_code_working": "6109.10",
            "as_of_date": "2026-06-01",
            "invoice_value": "1000",
            "currency": "USD",
            "organization_id": "org_demo",
        },
    )
    assert a.status_code == 200
    sid = a.json()["id"]

    # Create a second org and try to read
    factory = client.app.state.session_factory
    with factory() as session:
        from datetime import UTC, datetime

        from backend.app.data.models import Organization

        session.add(
            Organization(
                id="org_other",
                name="Other Org",
                country="BD",
                tax_identifier=None,
                created_at=datetime.now(UTC),
            )
        )
        session.commit()

    denied = client.get(
        f"/api/v1/scenarios/{sid}",
        headers={"X-Organization-Id": "org_other"},
    )
    assert denied.status_code == 403


def test_updating_freight_changes_calculation_inputs() -> None:
    client = make_client()
    client.post("/api/v1/ingest/promote-cbic", json={})
    created = client.post(
        "/api/v1/scenarios",
        json={
            "title": "Freight test",
            "product_text": "cotton t-shirts",
            "origin": "BD",
            "destination": "IN",
            "hs_code_working": "6109.10",
            "as_of_date": "2026-06-01",
            "invoice_value": "1000",
            "currency": "USD",
            "freight": "0",
            "insurance": "0",
        },
    ).json()
    sid = created["id"]
    first = client.post(
        f"/api/v1/scenarios/{sid}/calculate", json={"requested_mode": "estimate"}
    ).json()["latest_calculation"]
    client.patch(f"/api/v1/scenarios/{sid}", json={"freight": "200"})
    second = client.post(
        f"/api/v1/scenarios/{sid}/calculate", json={"requested_mode": "estimate"}
    ).json()["latest_calculation"]
    assert Decimal(str(second["assessable_value"])) > Decimal(str(first["assessable_value"]))
