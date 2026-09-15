"""Normalize raw source records into internal shapes."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from backend.app.integrations.core.models import NormalizedTariffRule

_HS_DIGITS = re.compile(r"\D+")


def normalize_hs_code(value: str | None) -> str | None:
    if value is None:
        return None
    digits = _HS_DIGITS.sub("", str(value).strip())
    if len(digits) < 4:
        return str(value).strip() or None
    if len(digits) == 4:
        return digits
    if len(digits) >= 6:
        return f"{digits[:4]}.{digits[4:6]}"
    return digits


def normalize_country(value: str | None) -> str | None:
    if value is None:
        return None
    return str(value).strip().upper()[:2] or None


def normalize_percent(value: Any) -> Decimal | None:
    if value is None:
        return None
    raw = str(value).strip().replace("%", "")
    try:
        return Decimal(raw)
    except (InvalidOperation, ValueError):
        return None


def normalize_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    # ISO
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        pass
    # DD/MM/YYYY
    parts = re.split(r"[/-]", text)
    if len(parts) == 3 and len(parts[2]) == 4:
        d, m, y = parts[0], parts[1], parts[2]
        try:
            return date(int(y), int(m), int(d))
        except ValueError:
            return None
    return None


def normalize_regime(value: str | None) -> str:
    if not value:
        return "MFN"
    text = str(value).strip().upper()
    aliases = {
        "MOST FAVOURED NATION": "MFN",
        "MOST FAVORED NATION": "MFN",
        "PREFERENTIAL": "PREFERENTIAL",
        "SAFTA": "SAFTA",
    }
    return aliases.get(text, text)


def normalize_tariff_record(
    raw: dict[str, Any],
    *,
    source_document_id: str,
    default_origin: str | None = None,
    default_destination: str | None = None,
    default_effective_from: date | None = None,
) -> tuple[NormalizedTariffRule | None, list[str]]:
    """Return (rule, errors). Rule is None when required fields cannot be normalized."""
    errors: list[str] = []
    hs = normalize_hs_code(raw.get("hs_code") or raw.get("tariffHead") or raw.get("hs"))
    origin = normalize_country(
        raw.get("origin") or raw.get("origin_country") or default_origin
    )
    destination = normalize_country(
        raw.get("destination") or raw.get("destination_country") or default_destination
    )
    rate = normalize_percent(
        raw.get("rate")
        if raw.get("rate") is not None
        else raw.get("customs_duty")
        if raw.get("customs_duty") is not None
        else raw.get("basicDuty")
        if raw.get("basicDuty") is not None
        else raw.get("duty_rate")
    )
    effective_from = normalize_date(
        raw.get("effective_from") or raw.get("effective_date") or raw.get("validFrom")
    ) or default_effective_from
    effective_to = normalize_date(raw.get("effective_to") or raw.get("validTo"))
    regime = normalize_regime(raw.get("regime") or raw.get("agreement"))

    if not hs:
        errors.append("missing_hs_code")
    if not origin:
        errors.append("missing_origin")
    if not destination:
        errors.append("missing_destination")
    if rate is None:
        errors.append("invalid_rate")
    if effective_from is None:
        errors.append("missing_effective_from")

    if errors:
        return None, errors

    components = raw.get("duty_components")
    if not isinstance(components, dict):
        components = {}

    assert hs and origin and destination and rate is not None and effective_from is not None
    rule = NormalizedTariffRule(
        hs_code=hs,
        origin_country=origin,
        destination_country=destination,
        regime=regime,
        duty_rate=rate,
        effective_from=effective_from,
        effective_to=effective_to,
        source_document_id=source_document_id,
        source_page=int(raw["source_page"]) if raw.get("source_page") is not None else None,
        duty_components=dict(components),
        notes=str(raw["notes"]) if raw.get("notes") else None,
        raw=dict(raw),
    )
    return rule, []


def normalized_rule_to_proposal_payload(rule: NormalizedTariffRule) -> dict[str, Any]:
    """Shape expected by existing ingest publish path."""
    return {
        "hs_code": rule.hs_code,
        "origin": rule.origin_country,
        "destination": rule.destination_country,
        "rate": float(rule.duty_rate),
        "rate_type": "ad_valorem_pct",
        "duty_components": rule.duty_components
        or {
            "bcd_pct": float(rule.duty_rate),
            "sws_pct_of_bcd": 10.0,
            "igst_pct": 5.0,
        },
        "regime": rule.regime,
        "effective_from": rule.effective_from.isoformat(),
        "effective_to": rule.effective_to.isoformat() if rule.effective_to else None,
        "notes": rule.notes,
        "source_page": rule.source_page,
    }
