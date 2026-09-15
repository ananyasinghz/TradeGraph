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


class DutyComponent(Protocol):
    code: str
    display_name: str
    order: int

    def calculate(self, ctx: CalculationContext) -> ComponentResult: ...


class BasicCustomsDuty:
    code = "BCD"
    display_name = "Basic Customs Duty"
    order = 1

    def calculate(self, ctx: CalculationContext) -> ComponentResult:
        rate = ctx.rates.get("bcd_pct", Decimal("0"))
        amount = _money(ctx.assessable_value * rate / Decimal("100"))
        return ComponentResult(
            code=self.code,
            display_name=self.display_name,
            amount=amount,
            rate=rate,
            included_in_customs=True,
            included_in_landed=True,
        )


class SocialWelfareSurcharge:
    code = "SWS"
    display_name = "Social Welfare Surcharge"
    order = 2

    def calculate(self, ctx: CalculationContext) -> ComponentResult:
        rate = ctx.rates.get("sws_pct_of_bcd", Decimal("10"))
        bcd = ctx.assessable_value * ctx.rates.get("bcd_pct", Decimal("0")) / Decimal("100")
        amount = _money(_money(bcd) * rate / Decimal("100"))
        return ComponentResult(
            code=self.code,
            display_name=self.display_name,
            amount=amount,
            rate=rate,
            included_in_customs=True,
            included_in_landed=True,
        )


class IGST:
    code = "IGST"
    display_name = "Integrated GST"
    order = 3

    def calculate(self, ctx: CalculationContext) -> ComponentResult:
        rate = ctx.rates.get("igst_pct", Decimal("5"))
        bcd_pct = ctx.rates.get("bcd_pct", Decimal("0"))
        sws_pct = ctx.rates.get("sws_pct_of_bcd", Decimal("10"))
        bcd = _money(ctx.assessable_value * bcd_pct / Decimal("100"))
        sws = _money(bcd * sws_pct / Decimal("100"))
        amount = _money((ctx.assessable_value + bcd + sws) * rate / Decimal("100"))
        return ComponentResult(
            code=self.code,
            display_name=self.display_name,
            amount=amount,
            rate=rate,
            included_in_customs=True,
            included_in_landed=True,
        )


_IN_IMPORT_COMPONENTS: list[DutyComponent] = [
    BasicCustomsDuty(),
    SocialWelfareSurcharge(),
    IGST(),
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
    regime: str = "import",
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
        },
    )
    results = [c.calculate(ctx) for c in sorted(_IN_IMPORT_COMPONENTS, key=lambda x: x.order)]
    total_duties = _money(sum((r.amount for r in results), Decimal("0")))
    landed = _money(ctx.assessable_value + total_duties)
    return results, total_duties, landed
