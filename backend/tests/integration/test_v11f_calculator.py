"""V1.1f calculator formula narrative + missing freight warnings."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.app.data.models import TariffRate
from backend.app.domain.trade import LandedCostInput
from backend.app.services.cost_service import calculate_from_tariff
from backend.tests.helpers.db import make_client


def test_formula_steps_and_freight_warning() -> None:
    tariff = TariffRate(
        id="t1",
        hs_code="6109.10",
        origin="BD",
        destination="IN",
        rate=Decimal("10"),
        rate_type="ad_valorem_pct",
        duty_components={"bcd_pct": 10, "sws_pct_of_bcd": 10, "igst_pct": 5},
        agreement_id=None,
        effective_from=date(2026, 1, 1),
        effective_to=None,
        source_document_id="src",
        version=2,
        status="active",
        data_quality="illustrative",
        superseded_by=None,
    )
    payload = LandedCostInput(
        hs_code="6109.10",
        origin="BD",
        destination="IN",
        as_of=date(2026, 6, 1),
        invoice_value=Decimal("1000"),
        currency="USD",
        incoterm="FOB",
    )
    result = calculate_from_tariff(
        Decimal("1000"), "USD", tariff, incoterm="FOB", payload=payload
    )
    assert len(result.formula_steps) >= 6
    assert any("BCD" in step for step in result.formula_steps)
    assert result.warnings
    assert any("Freight" in w or "freight" in w for w in result.warnings)


def test_calculate_api_returns_formula() -> None:
    client = make_client()
    response = client.post(
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
    assert response.status_code == 200
    body = response.json()
    assert body["formula_steps"]
    assert body["warnings"]
    assert float(body["landed_cost"]) == 1165.5
