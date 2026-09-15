"""Unit tests for deterministic cost calculator."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.app.data.models import TariffRate
from backend.app.services.cost_service import calculate_from_tariff


def test_calculate_from_tariff_breakdown() -> None:
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
    result = calculate_from_tariff(Decimal("1000"), "USD", tariff)
    assert result.bcd == Decimal("100.00")
    assert result.sws == Decimal("10.00")
    # IGST on 1110 @ 5% = 55.50
    assert result.igst == Decimal("55.50")
    assert result.landed_cost == Decimal("1165.50")
    assert result.formula_steps
    assert result.warnings
