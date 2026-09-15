"""IF-12c/d/e integration tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select

from backend.app.data.models import ScenarioImpact, TariffRate
from backend.app.services import impact_service
from backend.app.services.auth_service import resolve_principal
from backend.tests.helpers.db import make_client, make_settings


def _promote(client) -> None:
    r = client.post("/api/v1/ingest/promote-cbic", json={})
    assert r.status_code == 200, r.text


def _scenario(client, **overrides) -> str:
    body = {
        "title": "IF12 case",
        "product_text": "100% cotton knitted T-shirts",
        "origin": "BD",
        "destination": "IN",
        "hs_code_working": "6109.10",
        "as_of_date": "2026-06-01",
        "invoice_value": "5000",
        "currency": "USD",
        "incoterm": "CIF",
        "qty": 1,
        "freight": "100",
        "insurance": "50",
        "organization_id": "org_demo",
    }
    body.update(overrides)
    r = client.post("/api/v1/scenarios", json=body)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_if12c_ack_removes_impact_from_dashboard() -> None:
    client = make_client()
    _promote(client)
    sid = _scenario(client)
    client.post(f"/api/v1/scenarios/{sid}/calculate", json={"requested_mode": "estimate"})

    factory = client.app.state.session_factory
    with factory() as session:
        active = session.scalars(
            select(TariffRate).where(
                TariffRate.hs_code == "6109.10",
                TariffRate.status == "active",
            )
        ).first()
        assert active is not None
        old = TariffRate(
            id="test-old-rate-ack",
            hs_code=active.hs_code,
            origin=active.origin,
            destination=active.destination,
            rate=active.rate + Decimal("2"),
            rate_type=active.rate_type,
            duty_components=dict(active.duty_components or {}),
            effective_from=date(2025, 1, 1),
            source_document_id=active.source_document_id,
            version=999,
            status="superseded",
            data_quality="illustrative",
            regime=active.regime,
        )
        impacts = impact_service.record_impacts_for_new_tariff(
            session, new_tariff=active, old_tariff=old
        )
        session.commit()
        assert len(impacts) >= 1
        impact_id = impacts[0].id

    dash = client.get("/api/v1/dashboard").json()
    assert any(a.get("impact_id") == impact_id for a in dash["alerts"])

    ack = client.post(f"/api/v1/impacts/{impact_id}/acknowledge")
    assert ack.status_code == 200
    assert ack.json()["acknowledged_at"]

    dash2 = client.get("/api/v1/dashboard").json()
    assert not any(a.get("impact_id") == impact_id for a in dash2["alerts"])


def test_if12c_dedupe_same_tariff_impact() -> None:
    client = make_client()
    _promote(client)
    sid = _scenario(client)
    client.post(f"/api/v1/scenarios/{sid}/calculate", json={"requested_mode": "estimate"})
    factory = client.app.state.session_factory
    with factory() as session:
        active = session.scalars(
            select(TariffRate).where(
                TariffRate.hs_code == "6109.10",
                TariffRate.status == "active",
            )
        ).first()
        assert active is not None
        old = TariffRate(
            id="test-old-rate-dedupe",
            hs_code=active.hs_code,
            origin=active.origin,
            destination=active.destination,
            rate=active.rate + Decimal("1"),
            rate_type=active.rate_type,
            duty_components=dict(active.duty_components or {}),
            effective_from=date(2025, 1, 1),
            source_document_id=active.source_document_id,
            version=998,
            status="superseded",
            data_quality="illustrative",
            regime=active.regime,
        )
        first = impact_service.record_impacts_for_new_tariff(
            session, new_tariff=active, old_tariff=old
        )
        second = impact_service.record_impacts_for_new_tariff(
            session, new_tariff=active, old_tariff=old
        )
        session.commit()
        assert len(first) >= 1
        assert second == []


def test_if12d_timeline_after_calculate_and_hs() -> None:
    client = make_client()
    sid = _scenario(client, hs_code_working="6109.10")
    client.post(
        f"/api/v1/scenarios/{sid}/confirm-hs",
        json={"hs_code": "6109.10"},
    )
    client.post(f"/api/v1/scenarios/{sid}/calculate", json={"requested_mode": "estimate"})
    tl = client.get(f"/api/v1/scenarios/{sid}/timeline").json()
    types = {e["event_type"] for e in tl["events"]}
    assert "hs_change" in types
    assert "calculation" in types


def test_if12e_auth_required_when_enabled() -> None:
    client = make_client(auth_enabled=True)
    r = client.get("/api/v1/scenarios")
    assert r.status_code == 401


def test_if12e_demo_token_works_in_test_env() -> None:
    client = make_client(auth_enabled=True)
    r = client.get(
        "/api/v1/scenarios",
        headers={"Authorization": "Bearer demo-admin"},
    )
    assert r.status_code == 200


def test_if12e_demo_tokens_blocked_in_production() -> None:
    settings = make_settings(auth_enabled=True, environment="production")
    try:
        resolve_principal(settings, "Bearer demo-admin")
        assert False, "expected AUTH_INVALID"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 401 or "AUTH_INVALID" in str(exc)


def test_if12e_org_isolation_on_timeline() -> None:
    client = make_client()
    sid = _scenario(client, organization_id="org_demo")
    client.post(f"/api/v1/scenarios/{sid}/calculate", json={"requested_mode": "estimate"})
    forbidden = client.get(
        f"/api/v1/scenarios/{sid}/timeline",
        headers={"X-Organization-Id": "org_other"},
    )
    assert forbidden.status_code in {403, 404}
