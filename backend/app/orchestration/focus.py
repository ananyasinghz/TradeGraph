"""Build focused Ask queries from UI context (V1.1d)."""

from __future__ import annotations

from typing import Literal

AskFocus = Literal["tariff", "shipment_gaps", "fta", "landed_cost"]

FOCUS_TOOLS: dict[AskFocus, tuple[str, ...]] = {
    "tariff": ("tariff_lookup",),
    "shipment_gaps": ("checklist_build", "tariff_lookup", "fta_check"),
    "fta": ("fta_check", "graph_expand"),
    "landed_cost": ("landed_cost", "tariff_lookup"),
}


def build_focus_query(
    focus: AskFocus,
    *,
    hs_code: str | None,
    origin: str,
    destination: str,
    as_of: str,
    product_text: str | None = None,
) -> str:
    hs = hs_code or "the working HS code"
    corridor = f"{origin} to {destination}"
    if focus == "tariff":
        return (
            f"Explain the import tariff for HS {hs} from {corridor} as of {as_of}. "
            "Include the rate, data quality, and source document id."
        )
    if focus == "shipment_gaps":
        product = product_text or "this shipment"
        return (
            f"What is missing from the shipment of {product} (HS {hs}, {corridor}, "
            f"as of {as_of})? List document checklist gaps and classification risks."
        )
    if focus == "fta":
        return (
            f"Why might preferential FTA duty apply or not apply for HS {hs} "
            f"from {corridor} as of {as_of}? Compare MFN vs preferential and certificate needs."
        )
    return (
        f"Explain the landed cost calculation for HS {hs} from {corridor} as of {as_of}. "
        "Break down BCD, SWS, and IGST using the deterministic calculator."
    )
