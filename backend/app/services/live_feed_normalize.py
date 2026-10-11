"""Normalize live HTTP JSON into the CBIC ingest envelope used by run_ingest."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

PARSER_VERSION = "live_cbic_envelope.v1"


@dataclass(frozen=True)
class NormalizeResult:
    envelope: dict[str, Any]
    semantic_fingerprint: str
    parser_version: str
    document_type: str
    warnings: list[str]


def _canonical_rate(rate: dict[str, Any]) -> dict[str, Any]:
    components = rate.get("duty_components") or {}
    if not isinstance(components, dict):
        components = {}
    return {
        "hs_code": str(rate.get("hs_code") or "").strip(),
        "origin": str(rate.get("origin") or "").upper(),
        "destination": str(rate.get("destination") or "").upper(),
        "rate": str(rate.get("rate")),
        "rate_type": str(rate.get("rate_type") or "ad_valorem_pct"),
        "duty_components": {
            "bcd_pct": components.get("bcd_pct"),
            "sws_pct_of_bcd": components.get("sws_pct_of_bcd"),
            "igst_pct": components.get("igst_pct"),
        },
    }


def semantic_fingerprint(envelope: dict[str, Any]) -> str:
    """Stable hash of normalized publishable rate fields (excludes notes/chunks)."""
    rates = [_canonical_rate(r) for r in (envelope.get("rates") or []) if isinstance(r, dict)]
    rates.sort(key=lambda r: (r["hs_code"], r["origin"], r["destination"], r["rate"]))
    payload = {
        "effective_from": envelope.get("effective_from"),
        "corridor": envelope.get("corridor"),
        "rates": rates,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def normalize_live_json(
    content: bytes,
    *,
    source_key: str,
    content_type: str | None = None,
) -> NormalizeResult:
    warnings: list[str] = []
    ctype = (content_type or "").split(";")[0].strip().lower()
    if ctype and ctype not in {"application/json", "text/json", "application/vnd.api+json", ""}:
        raise ValueError(f"unsupported_content_type:{ctype}")

    try:
        raw = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid_json:{exc}") from exc

    if not isinstance(raw, dict):
        raise ValueError("envelope_not_object")

    document_type = str(raw.get("document_type") or raw.get("pack_type") or "tariff_pack").strip()
    if document_type.lower() in {"amendment_only", "exemption_notice", "partial_notification"}:
        warnings.append(
            "document_type_partial: treat as amendment/notice — not a complete tariff schedule"
        )

    if "rates" not in raw or not isinstance(raw.get("rates"), list):
        raise ValueError("missing_rates_array")

    envelope = dict(raw)
    envelope["source_key"] = str(envelope.get("source_key") or source_key)
    if "corridor" not in envelope:
        envelope["corridor"] = {"origin": "BD", "destination": "IN"}
    envelope["_live_meta"] = {
        "parser_version": PARSER_VERSION,
        "document_type": document_type,
        "warnings": warnings,
    }

    return NormalizeResult(
        envelope=envelope,
        semantic_fingerprint=semantic_fingerprint(envelope),
        parser_version=PARSER_VERSION,
        document_type=document_type,
        warnings=warnings,
    )


def write_normalized_archive(path: "Path", envelope: dict[str, Any]) -> None:
    from pathlib import Path

    Path(path).write_text(
        json.dumps(envelope, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
