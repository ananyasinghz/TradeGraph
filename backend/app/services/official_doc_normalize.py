"""Normalize official CBIC/ICEGATE HTML/PDF documents into the CBIC ingest envelope."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from backend.app.services.live_feed_normalize import (
    NormalizeResult,
    semantic_fingerprint,
    write_normalized_archive,
)

PARSER_VERSION = "official_india_doc.v2"

# Locked Live Source Verification document (CBIC Chapter 61 slice).
VERIFIED_IGST_RATE_NOTICE_MARKERS = (
    "NOTIFICATION NO. 9/2025-INTEGRATED TAX",
    "9/2025-INTEGRATED TAX (RATE)",
    "INTEGRATED TAX (RATE)",
)

# HS 6109.10 Bangladesh origin BCD 10% (ad valorem)
_RATE_LINE = re.compile(
    r"HS\s*(?P<hs>\d{4}\.?\d{0,4})"
    r".{0,80}?"
    r"(?:Bangladesh|BD).{0,40}?"
    r"(?:BCD|duty|rate).{0,20}?"
    r"(?P<rate>\d+(?:\.\d+)?)\s*%",
    re.IGNORECASE | re.DOTALL,
)
_RATE_LINE_ALT = re.compile(
    r"(?:BCD|duty|rate).{0,20}?(?P<rate>\d+(?:\.\d+)?)\s*%"
    r".{0,80}?"
    r"HS\s*(?P<hs>\d{4}\.?\d{0,4})"
    r".{0,40}?(?:Bangladesh|BD)",
    re.IGNORECASE | re.DOTALL,
)
_NOTIF_RE = re.compile(
    r"Notification\s+No\.?\s*([A-Za-z0-9/.\-–—]+)",
    re.IGNORECASE,
)
_EFFECTIVE_RE = re.compile(
    r"(?:effective\s+(?:from|on)|with\s+effect\s+from)\s+"
    r"(\d{1,2}\s+\w+\s+\d{4}|\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)
_HREF_RE = re.compile(
    r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class DiscoveryItem:
    title: str
    url: str


@dataclass(frozen=True)
class OfficialNormalizeResult(NormalizeResult):
    discovery: list[DiscoveryItem]
    evidence_excerpt: str


def _strip_html(html: str) -> str:
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", html)
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    text = _TAG_RE.sub(" ", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _normalize_hs(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if len(digits) < 4:
        return raw.strip()
    if len(digits) == 4:
        return digits
    # 610910 → 6109.10 ; 6109.10 already
    if "." in raw:
        return raw.strip()
    return f"{digits[:4]}.{digits[4:6]}" if len(digits) >= 6 else f"{digits[:4]}.{digits[4:]}"


def _parse_effective(text: str) -> str | None:
    m = _EFFECTIVE_RE.search(text)
    if not m:
        return None
    raw = m.group(1).strip()
    if re.match(r"\d{4}-\d{2}-\d{2}", raw):
        return raw
    # 1 July 2026 / 01 July 2026
    months = {
        "january": "01",
        "february": "02",
        "march": "03",
        "april": "04",
        "may": "05",
        "june": "06",
        "july": "07",
        "august": "08",
        "september": "09",
        "october": "10",
        "november": "11",
        "december": "12",
    }
    parts = raw.split()
    if len(parts) == 3:
        day, mon, year = parts
        mm = months.get(mon.lower())
        if mm:
            return f"{year}-{mm}-{int(day):02d}"
    return None


def extract_discovery_links(html: str, *, base_url: str) -> list[DiscoveryItem]:
    items: list[DiscoveryItem] = []
    seen: set[str] = set()
    for href, title_html in _HREF_RE.findall(html):
        title = _strip_html(title_html)[:200]
        abs_url = urljoin(base_url, href.strip())
        if abs_url in seen:
            continue
        lower = abs_url.lower()
        title_l = title.lower()
        if any(
            token in lower or token in title_l
            for token in ("notification", "circular", "tariff", "customs", ".pdf")
        ):
            seen.add(abs_url)
            items.append(DiscoveryItem(title=title or abs_url, url=abs_url))
    return items


def _extract_text(content: bytes, content_type: str | None) -> str:
    ctype = (content_type or "").split(";")[0].strip().lower()
    if ctype in {"application/pdf"} or content[:4] == b"%PDF":
        from backend.app.integrations.adapters import pdf_document

        return pdf_document.extract_pdf_text(content)
    try:
        raw = content.decode("utf-8")
    except UnicodeDecodeError:
        raw = content.decode("latin-1", errors="replace")
    if ctype in {"text/html", "application/xhtml+xml"} or "<html" in raw[:500].lower():
        return _strip_html(raw)
    return raw


def _extract_rates(text: str) -> list[dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for pattern in (_RATE_LINE, _RATE_LINE_ALT):
        for m in pattern.finditer(text):
            hs = _normalize_hs(m.group("hs"))
            rate = float(m.group("rate"))
            key = f"{hs}|BD|IN"
            found[key] = {
                "hs_code": hs,
                "origin": "BD",
                "destination": "IN",
                "rate": rate,
                "rate_type": "ad_valorem_pct",
                "duty_components": {
                    "bcd_pct": rate,
                    "sws_pct_of_bcd": 10.0,
                    "igst_pct": 5.0,
                },
                "notes": "Extracted from official document text (deterministic pattern).",
            }
    return list(found.values())


def _looks_like_igst_rate_notification(text: str) -> bool:
    upper = text.upper()
    has_marker = any(marker in upper for marker in VERIFIED_IGST_RATE_NOTICE_MARKERS)
    has_ch61 = (
        "ARTICLES OF APPAREL AND CLOTHING ACCESSORIES, KNITTED" in upper
        or "ARTICLE OF APPAREL AND CLOTHING ACCESSORIES, KNITTED" in upper
    )
    return has_marker and "SCHEDULE I" in upper and has_ch61


def _extract_igst_chapter61_rates(text: str) -> tuple[list[dict[str, Any]], list[str]]:
    """
    Document-specific extractor for CBIC Notification No. 9/2025-Integrated Tax (Rate).

    Schedule I lists chapter 61 knitted apparel (sale value not exceeding Rs 2500)
    at IGST 5%. Map exemplar HS 6109.10 for the BD→IN Chapter 61 verification slice.
    Does not invent BCD preferential rates.
    """
    warnings: list[str] = []
    compact = re.sub(r"\s+", " ", text)
    upper = compact.upper()

    # Confirm Schedule I chapter 61 knitted apparel line exists.
    ch61_sched_i = re.search(
        r"\b61\b\s+ARTICLE(?:S)? OF APPAREL AND CLOTHING ACCESSORIES,\s*KNITTED"
        r".{0,120}?SALE VALUE NOT EXCEEDING",
        upper,
    )
    if not ch61_sched_i:
        warnings.append("igst_ch61_schedule_i_line_not_found")
        return [], warnings

    # Header: "(i) 5 per cent. in respect of goods specified in Schedule I"
    sched_i_rate = 5.0
    m_rate = re.search(
        r"5\s*per\s*cent\.?\s*in\s*respect\s*of\s*goods\s*specified\s*in\s*Schedule\s*I",
        compact,
        re.IGNORECASE,
    )
    if not m_rate:
        m_alt = re.search(r"Schedule\s*I\s*[–\-:]\s*5\s*%", compact, re.IGNORECASE)
        if not m_alt:
            warnings.append("igst_schedule_i_rate_not_confirmed")
            return [], warnings

    effective = _parse_effective(compact)
    if not effective:
        # Notification dated 17-9-2025 / 17th September, 2025
        dm = re.search(
            r"DATED\s+(\d{1,2})[-/](\d{1,2})[-/](\d{4})",
            upper,
        )
        if dm:
            effective = f"{dm.group(3)}-{int(dm.group(2)):02d}-{int(dm.group(1)):02d}"
        else:
            dm2 = re.search(
                r"(\d{1,2})\s*(?:th|st|nd|rd)?\s*(September|Sep)\s*,?\s*(2025)",
                compact,
                re.IGNORECASE,
            )
            if dm2:
                effective = f"2025-09-{int(dm2.group(1)):02d}"

    warnings.append(
        "document_type_partial: IGST (Rate) schedule — not a complete BCD tariff pack; "
        "BCD not stated in this notification"
    )
    warnings.append(
        "mapped_exemplar_hs_6109_10: chapter 61 knitted apparel schedule line mapped to "
        "HS 6109.10 for BD->IN Chapter 61 verification slice"
    )

    rates = [
        {
            "hs_code": "6109.10",
            "origin": "BD",
            "destination": "IN",
            # Primary lookup rate stays BCD on merge; proposal rate is IGST-only marker.
            "rate": sched_i_rate,
            "rate_type": "ad_valorem_pct",
            "duty_components": {
                "igst_pct": sched_i_rate,
                "_partial_components": ["igst_pct"],
                "_provenance": {
                    "igst_pct": {
                        "value": sched_i_rate,
                        "source_key": "live_igst_notif_9_2025",
                        "source_document_id": None,
                        "data_quality": "source_verified",
                        "effective_from": effective,
                        "notes": (
                            "Official IGST Schedule I (5%) for Chapter 61 knitted apparel "
                            "(sale value not exceeding Rs 2500). BCD/SWS not in this document."
                        ),
                    }
                },
            },
            "notes": (
                "Official IGST Schedule I (5%) for Chapter 61 knitted/crocheted apparel "
                "of sale value not exceeding Rs 2500 per piece "
                "(Notification No. 9/2025-Integrated Tax (Rate)). "
                "Partial component update — does not set or invent BCD/SWS."
            ),
            "effective_from_hint": effective,
            "component_update_mode": "partial_igst",
        }
    ]
    return rates, warnings


def normalize_official_document(
    content: bytes,
    *,
    source_key: str,
    content_type: str | None = None,
    source_url: str | None = None,
    publisher: str | None = None,
) -> OfficialNormalizeResult:
    warnings: list[str] = []
    ctype = (content_type or "").split(";")[0].strip().lower()
    discovery: list[DiscoveryItem] = []

    # JSON packs reuse live envelope path semantics when served from official hosts.
    if ctype in {"application/json", "text/json", "application/vnd.api+json"} or (
        content[:1] == b"{" and b'"rates"' in content[:200]
    ):
        from backend.app.services import live_feed_normalize

        base = live_feed_normalize.normalize_live_json(
            content, source_key=source_key, content_type=ctype or "application/json"
        )
        return OfficialNormalizeResult(
            envelope=base.envelope,
            semantic_fingerprint=base.semantic_fingerprint,
            parser_version=PARSER_VERSION,
            document_type=base.document_type,
            warnings=base.warnings + ["official_doc_json_passthrough"],
            discovery=[],
            evidence_excerpt="",
        )

    raw_html = ""
    try:
        raw_html = content.decode("utf-8")
    except UnicodeDecodeError:
        raw_html = content.decode("latin-1", errors="replace")

    if ctype in {"text/html", "application/xhtml+xml", ""} and "<a" in raw_html.lower():
        discovery = extract_discovery_links(raw_html, base_url=source_url or "")

    text = _extract_text(content, content_type)
    if not text.strip():
        raise ValueError("empty_document_text")

    notif = _NOTIF_RE.search(text)
    notice_id = notif.group(1) if notif else None
    # Prefer Integrated Tax (Rate) style notice ids when present.
    igst_notice = re.search(
        r"NOTIFICATION\s+NO\.?\s*([0-9]+/[0-9]+-INTEGRATED\s+TAX\s*\(RATE\))",
        text,
        re.IGNORECASE,
    )
    if igst_notice:
        notice_id = igst_notice.group(1).replace(" ", "")

    effective = _parse_effective(text)
    rates = _extract_rates(text)
    if not rates and _looks_like_igst_rate_notification(text):
        igst_rates, igst_warnings = _extract_igst_chapter61_rates(text)
        rates = igst_rates
        warnings.extend(igst_warnings)
        if igst_rates and igst_rates[0].get("effective_from_hint") and not effective:
            effective = str(igst_rates[0]["effective_from_hint"])

    document_type = "amendment"
    if not rates:
        document_type = "unsupported"
        warnings.append(
            "no_extractable_chapter61_rates: document archived as evidence only — "
            "not a complete tariff schedule"
        )
    else:
        # Prefer chapter 61; keep others so validation can quarantine.
        ch61 = [r for r in rates if str(r["hs_code"]).startswith("61")]
        if not ch61:
            document_type = "unsupported"
            warnings.append("no_chapter_61_rates_extracted")
        else:
            document_type = "amendment"
            if not any("document_type_partial" in w for w in warnings):
                warnings.append(
                    "document_type_partial: treat as amendment/notice — not a complete tariff schedule"
                )

    title = (
        f"Official customs document {notice_id}"
        if notice_id
        else f"Official document fetch ({source_key})"
    )
    host = urlparse(source_url or "").hostname or "official"
    envelope: dict[str, Any] = {
        "source_key": source_key,
        "title": title,
        "publisher": publisher or f"Official portal ({host})",
        "url": source_url,
        "notice_id": notice_id or f"TG-OFFICIAL-{source_key}",
        "effective_from": effective or "2026-01-01",
        "disclaimer": (
            "Extracted from an official portal document via deterministic patterns. "
            "Illustrative applicability only until human review; not legal advice."
        ),
        "document_type": document_type,
        "corridor": {"origin": "BD", "destination": "IN"},
        "rates": rates,
        "chunks": [
            {
                "id": f"chunk_{source_key}_evidence",
                "hs_code": rates[0]["hs_code"] if rates else None,
                "tags": ["official_document", "notification", "chapter61"],
                "text": text[:1200],
            }
        ],
        "_live_meta": {
            "parser_version": PARSER_VERSION,
            "document_type": document_type,
            "warnings": warnings,
            "discovery_count": len(discovery),
            "final_url": source_url,
        },
        "_official_meta": {
            "parser_version": PARSER_VERSION,
            "notice_id": notice_id,
            "discovery": [{"title": d.title, "url": d.url} for d in discovery[:50]],
            "evidence_excerpt": text[:500],
        },
    }

    return OfficialNormalizeResult(
        envelope=envelope,
        semantic_fingerprint=semantic_fingerprint(envelope),
        parser_version=PARSER_VERSION,
        document_type=document_type,
        warnings=warnings,
        discovery=discovery,
        evidence_excerpt=text[:500],
    )


def write_discovery_manifest(path: Path, items: list[DiscoveryItem], *, base_url: str) -> None:
    path.write_text(
        json.dumps(
            {
                "base_url": base_url,
                "parser_version": PARSER_VERSION,
                "items": [{"title": i.title, "url": i.url} for i in items],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


__all__ = [
    "PARSER_VERSION",
    "DiscoveryItem",
    "OfficialNormalizeResult",
    "extract_discovery_links",
    "normalize_official_document",
    "write_discovery_manifest",
    "write_normalized_archive",
]
