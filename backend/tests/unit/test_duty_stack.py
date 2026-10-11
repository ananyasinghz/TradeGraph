"""Unit tests for full India duty stack + exemptions."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select

from backend.app.calculation.duty_components import calculate_india_import
from backend.app.data.models import ExemptionRule, TariffRate
from backend.app.services.cost_service import calculate_from_tariff
from backend.app.services.exemption_service import apply_effect_to_rates, list_applicable_exemptions
from backend.tests.helpers.db import make_seeded_engine


def test_full_stack_includes_aidc_health_cc() -> None:
    components, total, landed = calculate_india_import(
        assessable_value=Decimal("100000"),
        currency="INR",
        bcd_pct=Decimal("20"),
        aidc_pct=Decimal("5"),
        health_cess_pct=Decimal("0"),
        sws_pct_of_bcd=Decimal("10"),
        igst_pct=Decimal("18"),
        compensation_cess_pct=Decimal("0"),
    )
    codes = [c.code for c in components]
    assert codes == ["BCD", "AIDC", "CHCESS", "SWS", "IGST", "CC"]
    by = {c.code: c for c in components}
    assert by["BCD"].amount == Decimal("20000.00")
    assert by["AIDC"].amount == Decimal("5000.00")
    assert by["CHCESS"].amount == Decimal("0.00")
    assert by["SWS"].amount == Decimal("2000.00")
    # IGST base = 100000+20000+5000+0+2000 = 127000 @ 18% = 22860
    assert by["IGST"].amount == Decimal("22860.00")
    assert total == Decimal("49860.00")
    assert landed == Decimal("149860.00")


def test_calculate_from_tariff_still_supports_classic_bcd_sws_igst() -> None:
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
    assert result.aidc == Decimal("0.00")
    assert result.igst == Decimal("55.50")
    assert result.landed_cost == Decimal("1165.50")
    assert len(result.duty_stack) == 6


def test_exemption_effect_overlay() -> None:
    base = {
        "bcd_pct": Decimal("20"),
        "aidc_pct": Decimal("5"),
        "health_cess_pct": Decimal("0"),
        "sws_pct_of_bcd": Decimal("10"),
        "igst_pct": Decimal("18"),
        "compensation_cess_pct": Decimal("0"),
    }
    merged = apply_effect_to_rates(base, {"bcd_pct": 5, "aidc_pct": 0})
    assert merged["bcd_pct"] == Decimal("5")
    assert merged["aidc_pct"] == Decimal("0")
    assert merged["igst_pct"] == Decimal("18")


def test_seeded_exemptions_for_610910() -> None:
    _engine, factory = make_seeded_engine()
    with factory() as session:
        rows = list_applicable_exemptions(
            session,
            hs_code="6109.10",
            origin="BD",
            destination="IN",
            as_of=date(2026, 6, 1),
        )
        assert any(r.serial_no == "282" for r in rows)
        assert any(r.eligibility == "eligible_if_coo" for r in rows)
        count = session.scalar(select(func.count()).select_from(ExemptionRule))
        assert int(count or 0) >= 3


def test_seeded_610910_has_curated_component_provenance() -> None:
    _engine, factory = make_seeded_engine()
    with factory() as session:
        row = session.scalars(
            select(TariffRate).where(
                TariffRate.hs_code == "6109.10",
                TariffRate.origin == "BD",
                TariffRate.destination == "IN",
                TariffRate.status == "active",
                TariffRate.regime == "mfn",
            )
        ).first()
        assert row is not None
        prov = (row.duty_components or {}).get("_provenance") or {}
        assert prov["bcd_pct"]["data_quality"] == "curated_official_backed"
        assert prov["sws_pct_of_bcd"]["data_quality"] == "curated_official_backed"
        assert float(prov["bcd_pct"]["value"]) == 20.0
