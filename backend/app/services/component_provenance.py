"""Per-component duty provenance and merge rules (never invent BCD/SWS from IGST)."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from decimal import Decimal
from typing import Any

COMPONENT_KEYS = (
    "bcd_pct",
    "sws_pct_of_bcd",
    "igst_pct",
    "aidc_pct",
    "health_cess_pct",
    "compensation_cess_pct",
)

QUALITY_RANK = {
    "missing": 0,
    "illustrative": 1,
    "curated_official_backed": 2,
    "source_verified": 3,
}


def _as_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def provenance_block(
    *,
    value: float | None,
    source_key: str | None = None,
    source_document_id: str | None = None,
    data_quality: str = "missing",
    effective_from: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    return {
        "value": value,
        "source_key": source_key,
        "source_document_id": source_document_id,
        "data_quality": data_quality if value is not None else "missing",
        "effective_from": effective_from,
        "notes": notes,
    }


def extract_provenance(components: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    raw = dict(components or {})
    prov = raw.get("_provenance")
    out: dict[str, dict[str, Any]] = {}
    if isinstance(prov, dict):
        for key, block in prov.items():
            if key in COMPONENT_KEYS and isinstance(block, dict):
                out[key] = dict(block)
    for key in COMPONENT_KEYS:
        if key in out:
            continue
        if key in raw and not str(key).startswith("_"):
            out[key] = provenance_block(
                value=_as_float(raw.get(key)),
                data_quality="illustrative",
                notes="Legacy flat duty_components without explicit provenance",
            )
        else:
            out[key] = provenance_block(value=None, data_quality="missing")
    return out


def flatten_rates(components: dict[str, Any] | None, *, fallback_bcd: float | None = None) -> dict[str, float]:
    """Numeric rates for the calculator (0 for missing optional components)."""
    prov = extract_provenance(components)
    rates: dict[str, float] = {}
    bcd = _as_float(prov.get("bcd_pct", {}).get("value"), fallback_bcd)
    rates["bcd_pct"] = float(bcd if bcd is not None else 0.0)
    for key in COMPONENT_KEYS:
        if key == "bcd_pct":
            continue
        val = _as_float(prov.get(key, {}).get("value"))
        if key == "sws_pct_of_bcd" and (bcd is None or bcd == 0) and prov.get("bcd_pct", {}).get("data_quality") == "missing":
            # Do not invent SWS when BCD is missing.
            rates[key] = 0.0
            continue
        rates[key] = float(val if val is not None else (10.0 if key == "sws_pct_of_bcd" else 0.0))
    return rates


def partial_keys(components: dict[str, Any] | None) -> set[str]:
    raw = dict(components or {})
    marked = raw.get("_partial_components")
    if isinstance(marked, list) and marked:
        return {str(k) for k in marked if str(k) in COMPONENT_KEYS}
    # Heuristic: IGST-only packs that omit BCD
    if "igst_pct" in raw and "bcd_pct" not in raw:
        return {"igst_pct"}
    return set()


def merge_duty_components(
    existing: dict[str, Any] | None,
    incoming: dict[str, Any] | None,
    *,
    incoming_source_document_id: str | None = None,
    prefer_incoming_quality: bool = True,
) -> dict[str, Any]:
    """
    Merge component maps. Partial incoming (e.g. IGST-only) updates only declared keys.
    Never lets an IGST-only zero wipe curated/verified BCD or SWS.
    """
    base_prov = extract_provenance(existing)
    inc_prov = extract_provenance(incoming)
    keys_to_apply = partial_keys(incoming)
    apply_all = not keys_to_apply

    merged_prov: dict[str, dict[str, Any]] = deepcopy(base_prov)
    for key in COMPONENT_KEYS:
        if not apply_all and key not in keys_to_apply:
            continue
        inc = inc_prov.get(key) or provenance_block(value=None)
        # Ignore bogus BCD=0 from IGST-only partial packs
        if (
            key == "bcd_pct"
            and keys_to_apply == {"igst_pct"}
            and _as_float(inc.get("value")) in {0.0, None}
        ):
            continue
        if key == "sws_pct_of_bcd" and keys_to_apply == {"igst_pct"}:
            continue
        cur = merged_prov.get(key) or provenance_block(value=None)
        inc_q = QUALITY_RANK.get(str(inc.get("data_quality") or "missing"), 0)
        cur_q = QUALITY_RANK.get(str(cur.get("data_quality") or "missing"), 0)
        if prefer_incoming_quality and inc.get("value") is not None and inc_q >= cur_q:
            block = dict(inc)
            if incoming_source_document_id and not block.get("source_document_id"):
                block["source_document_id"] = incoming_source_document_id
            merged_prov[key] = block
        elif cur.get("value") is None and inc.get("value") is not None:
            merged_prov[key] = dict(inc)

    # If BCD missing, force SWS provenance to missing (do not invent).
    bcd_block = merged_prov.get("bcd_pct") or {}
    if bcd_block.get("value") is None or bcd_block.get("data_quality") == "missing":
        merged_prov["sws_pct_of_bcd"] = provenance_block(
            value=None,
            data_quality="missing",
            notes="SWS not applicable until BCD is sourced",
        )

    flat: dict[str, Any] = {}
    for key, block in merged_prov.items():
        if block.get("value") is not None:
            flat[key] = block["value"]
    flat["_provenance"] = merged_prov
    if keys_to_apply:
        flat["_partial_components"] = sorted(keys_to_apply)
    return flat


def primary_bcd_rate(components: dict[str, Any] | None, fallback: float | Decimal | None = None) -> Decimal:
    rates = flatten_rates(components, fallback_bcd=_as_float(fallback))
    return Decimal(str(rates["bcd_pct"]))


def coverage_flags(components: dict[str, Any] | None) -> dict[str, str]:
    prov = extract_provenance(components)
    return {k: str((prov.get(k) or {}).get("data_quality") or "missing") for k in COMPONENT_KEYS}


def attach_curated_ch61_defaults(
    components: dict[str, Any] | None,
    *,
    hs_code: str,
    effective_from: str = "2026-01-01",
) -> dict[str, Any]:
    """Ensure ch61 BD→IN rows carry curated BCD/SWS provenance when flat rates exist."""
    raw = dict(components or {})
    prov = extract_provenance(raw)
    if hs_code.startswith("61"):
        if prov["bcd_pct"].get("value") is not None and prov["bcd_pct"].get("data_quality") in {
            "illustrative",
            "missing",
        }:
            if prov["bcd_pct"].get("source_key") is None:
                prov["bcd_pct"] = provenance_block(
                    value=_as_float(prov["bcd_pct"].get("value")),
                    source_key="curated_bcd_ch61_bd_in",
                    source_document_id="src_curated_bcd_ch61_v1",
                    data_quality="curated_official_backed",
                    effective_from=effective_from,
                    notes=(
                        "Curated official-backed BCD for BD→IN Chapter 61 demo stack; "
                        "not derived from IGST (Rate) notifications."
                    ),
                )
        if prov["sws_pct_of_bcd"].get("value") is not None and prov["bcd_pct"].get("value") is not None:
            if prov["sws_pct_of_bcd"].get("source_key") is None:
                prov["sws_pct_of_bcd"] = provenance_block(
                    value=_as_float(prov["sws_pct_of_bcd"].get("value"), 10.0),
                    source_key="curated_sws_finance_act",
                    source_document_id="src_curated_sws_v1",
                    data_quality="curated_official_backed",
                    effective_from=effective_from,
                    notes="Curated SWS as % of BCD (Finance Act style); separate from IGST source.",
                )
        if prov["igst_pct"].get("value") is not None and prov["igst_pct"].get("source_key") is None:
            if prov["igst_pct"].get("data_quality") != "source_verified":
                prov["igst_pct"] = provenance_block(
                    value=_as_float(prov["igst_pct"].get("value")),
                    source_key="curated_igst_placeholder",
                    source_document_id="src_in_cbic_illustrative_2026",
                    data_quality="illustrative",
                    effective_from=effective_from,
                    notes="Illustrative IGST until replaced by verified Integrated Tax (Rate) ingest.",
                )
    flat = {k: v["value"] for k, v in prov.items() if v.get("value") is not None}
    flat["_provenance"] = prov
    return flat


def applicable_stack_signature(components: dict[str, Any] | None) -> str:
    """Stable signature of applicable numeric stack (for impact dedupe)."""
    rates = flatten_rates(components)
    parts = [f"{k}={rates.get(k, 0)}" for k in COMPONENT_KEYS]
    return "|".join(parts)
