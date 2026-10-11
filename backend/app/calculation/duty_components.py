"""India import duty component engine (IF-9) — controlled formulas, no eval()."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Protocol

TWOPLACES = Decimal("0.01")


def _money(value: Decimal) -> Decimal:
    return value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


@dataclass
class CalculationContext:
    jurisdiction: str
    regime: str
    assessable_value: Decimal
    currency: str
    rates: dict[str, Decimal]


@dataclass
class ComponentResult:
    code: str
    display_name: str
    amount: Decimal
    rate: Decimal
    included_in_customs: bool
    included_in_landed: bool
    notification_sl: str | None = None
    tariff_rate_pct: Decimal | None = None
    effective_rate_pct: Decimal | None = None


class DutyComponent(Protocol):
    code: str
    display_name: str
    order: int

    def calculate(self, ctx: CalculationContext) -> ComponentResult: ...


def _rate(ctx: CalculationContext, key: str, default: Decimal = Decimal("0")) -> Decimal:
    return ctx.rates.get(key, default)


class BasicCustomsDuty:
    code = "BCD"
    display_name = "Basic Customs Duty (BCD)"
    order = 1

    def calculate(self, ctx: CalculationContext) -> ComponentResult:
        rate = _rate(ctx, "bcd_pct")
        amount = _money(ctx.assessable_value * rate / Decimal("100"))
        return ComponentResult(
            code=self.code,
            display_name=self.display_name,
            amount=amount,
            rate=rate,
            included_in_customs=True,
            included_in_landed=True,
            tariff_rate_pct=rate,
            effective_rate_pct=rate,
        )


class CustomsAIDC:
    code = "AIDC"
    display_name = "Customs AIDC"
    order = 2

    def calculate(self, ctx: CalculationContext) -> ComponentResult:
        rate = _rate(ctx, "aidc_pct")
        amount = _money(ctx.assessable_value * rate / Decimal("100"))
        return ComponentResult(
            code=self.code,
            display_name=self.display_name,
            amount=amount,
            rate=rate,
            included_in_customs=True,
            included_in_landed=True,
            tariff_rate_pct=rate,
            effective_rate_pct=rate,
        )


class HealthCess:
    code = "CHCESS"
    display_name = "Custom Health CESS"
    order = 3

    def calculate(self, ctx: CalculationContext) -> ComponentResult:
        rate = _rate(ctx, "health_cess_pct")
        amount = _money(ctx.assessable_value * rate / Decimal("100"))
        return ComponentResult(
            code=self.code,
            display_name=self.display_name,
            amount=amount,
            rate=rate,
            included_in_customs=True,
            included_in_landed=True,
            tariff_rate_pct=rate,
            effective_rate_pct=rate,
        )


class SocialWelfareSurcharge:
    code = "SWS"
    display_name = "Social Welfare Surcharge (SWS/SWC)"
    order = 4

    def calculate(self, ctx: CalculationContext) -> ComponentResult:
        rate = _rate(ctx, "sws_pct_of_bcd", Decimal("10"))
        bcd = _money(ctx.assessable_value * _rate(ctx, "bcd_pct") / Decimal("100"))
        amount = _money(bcd * rate / Decimal("100"))
        return ComponentResult(
            code=self.code,
            display_name=self.display_name,
            amount=amount,
            rate=rate,
            included_in_customs=True,
            included_in_landed=True,
            tariff_rate_pct=rate,
            effective_rate_pct=rate,
        )


class IGST:
    code = "IGST"
    display_name = "IGST Levy"
    order = 5

    def calculate(self, ctx: CalculationContext) -> ComponentResult:
        rate = _rate(ctx, "igst_pct", Decimal("5"))
        bcd = _money(ctx.assessable_value * _rate(ctx, "bcd_pct") / Decimal("100"))
        aidc = _money(ctx.assessable_value * _rate(ctx, "aidc_pct") / Decimal("100"))
        health = _money(ctx.assessable_value * _rate(ctx, "health_cess_pct") / Decimal("100"))
        sws = _money(bcd * _rate(ctx, "sws_pct_of_bcd", Decimal("10")) / Decimal("100"))
        base = ctx.assessable_value + bcd + aidc + health + sws
        amount = _money(base * rate / Decimal("100"))
        return ComponentResult(
            code=self.code,
            display_name=self.display_name,
            amount=amount,
            rate=rate,
            included_in_customs=True,
            included_in_landed=True,
            tariff_rate_pct=rate,
            effective_rate_pct=rate,
        )


class CompensationCess:
    code = "CC"
    display_name = "Compensation Cess (CC)"
    order = 6

    def calculate(self, ctx: CalculationContext) -> ComponentResult:
        rate = _rate(ctx, "compensation_cess_pct")
        bcd = _money(ctx.assessable_value * _rate(ctx, "bcd_pct") / Decimal("100"))
        aidc = _money(ctx.assessable_value * _rate(ctx, "aidc_pct") / Decimal("100"))
        health = _money(ctx.assessable_value * _rate(ctx, "health_cess_pct") / Decimal("100"))
        sws = _money(bcd * _rate(ctx, "sws_pct_of_bcd", Decimal("10")) / Decimal("100"))
        base = ctx.assessable_value + bcd + aidc + health + sws
        amount = _money(base * rate / Decimal("100"))
        return ComponentResult(
            code=self.code,
            display_name=self.display_name,
            amount=amount,
            rate=rate,
            included_in_customs=True,
            included_in_landed=True,
            tariff_rate_pct=rate,
            effective_rate_pct=rate,
        )


_IN_IMPORT_COMPONENTS: list[DutyComponent] = [
    BasicCustomsDuty(),
    CustomsAIDC(),
    HealthCess(),
    SocialWelfareSurcharge(),
    IGST(),
    CompensationCess(),
]


def components_for_jurisdiction(
    jurisdiction: str, *, regime: str = "import"
) -> list[DutyComponent]:
    del regime
    if jurisdiction.upper() == "IN":
        return list(_IN_IMPORT_COMPONENTS)
    return [BasicCustomsDuty()]


def calculate_india_import(
    *,
    assessable_value: Decimal,
    currency: str,
    bcd_pct: Decimal,
    sws_pct_of_bcd: Decimal = Decimal("10"),
    igst_pct: Decimal = Decimal("5"),
    aidc_pct: Decimal = Decimal("0"),
    health_cess_pct: Decimal = Decimal("0"),
    compensation_cess_pct: Decimal = Decimal("0"),
    regime: str = "import",
    notification_labels: dict[str, str] | None = None,
) -> tuple[list[ComponentResult], Decimal, Decimal]:
    """Return (components, total_duties, landed_cost)."""
    ctx = CalculationContext(
        jurisdiction="IN",
        regime=regime,
        assessable_value=_money(assessable_value),
        currency=currency,
        rates={
            "bcd_pct": bcd_pct,
            "sws_pct_of_bcd": sws_pct_of_bcd,
            "igst_pct": igst_pct,
            "aidc_pct": aidc_pct,
            "health_cess_pct": health_cess_pct,
            "compensation_cess_pct": compensation_cess_pct,
        },
    )
    labels = notification_labels or {}
    results: list[ComponentResult] = []
    for c in sorted(_IN_IMPORT_COMPONENTS, key=lambda x: x.order):
        row = c.calculate(ctx)
        if labels.get(row.code):
            row.notification_sl = labels[row.code]
        results.append(row)
    total_duties = _money(sum((r.amount for r in results), Decimal("0")))
    landed = _money(ctx.assessable_value + total_duties)
    return results, total_duties, landed
