"""Chapter-level tariff coverage matrix (honest zeros where missing)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.data.models import (
    AgreementEligibility,
    ExemptionRule,
    HsCode,
    TariffRate,
)
from backend.app.domain.trade import TariffCoverageChapterOut, TariffCoverageOut
from backend.app.services.component_provenance import extract_provenance

Status = Literal["verified", "curated", "missing", "needs_review", "illustrative"]

_QUALITY_TO_STATUS: dict[str, Status] = {
    "source_verified": "verified",
    "demo_verified": "verified",
    "curated_official_backed": "curated",
    "illustrative": "illustrative",
    "missing": "missing",
}


def _status_from_qualities(qualities: list[str]) -> Status:
    if not qualities:
        return "missing"
    mapped = [_QUALITY_TO_STATUS.get(q, "needs_review") for q in qualities]
    if "verified" in mapped:
        return "verified"
    if "curated" in mapped:
        return "curated"
    if "illustrative" in mapped:
        return "illustrative"
    if "needs_review" in mapped:
        return "needs_review"
    return "missing"


def chapter_coverage(
    session: Session,
    *,
    origin: str = "BD",
    destination: str = "IN",
) -> TariffCoverageOut:
    origin_u = origin.upper()
    dest_u = destination.upper()

    hs_rows = session.scalars(select(HsCode)).all()
    by_chapter: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "classification": set(),
            "bcd": set(),
            "sws": set(),
            "igst": set(),
            "exemption": set(),
            "preferential": set(),
            "bcd_q": [],
            "sws_q": [],
            "igst_q": [],
        }
    )

    for hs in hs_rows:
        ch = str(hs.chapter or (hs.code or "")[:2]).zfill(2)[-2:]
        by_chapter[ch]["classification"].add(hs.code)

    rates = session.scalars(
        select(TariffRate).where(
            TariffRate.origin == origin_u,
            TariffRate.destination == dest_u,
            TariffRate.status == "active",
            TariffRate.regime == "mfn",
        )
    ).all()
    for rate in rates:
        ch = (rate.hs_code or "")[:2].zfill(2)[-2:]
        prov = extract_provenance(rate.duty_components)
        for key, bucket, qlist in (
            ("bcd_pct", "bcd", "bcd_q"),
            ("sws_pct_of_bcd", "sws", "sws_q"),
            ("igst_pct", "igst", "igst_q"),
        ):
            block = prov.get(key) or {}
            q = str(block.get("data_quality") or "missing")
            # Count only when value is present — explicit 0% still counts as sourced.
            if q != "missing" and block.get("value") is not None:
                by_chapter[ch][bucket].add(rate.hs_code)
                by_chapter[ch][qlist].append(q)

    exemptions = session.scalars(
        select(ExemptionRule).where(
            ExemptionRule.origin == origin_u,
            ExemptionRule.destination == dest_u,
            ExemptionRule.status == "active",
        )
    ).all()
    for rule in exemptions:
        match = str(rule.hs_match or "")
        ch = match[:2].zfill(2)[-2:] if match else ""
        if ch:
            by_chapter[ch]["exemption"].add(rule.id)

    prefs = session.scalars(
        select(AgreementEligibility).where(
            AgreementEligibility.origin == origin_u,
            AgreementEligibility.destination == dest_u,
        )
    ).all()
    for rule in prefs:
        ch = (rule.hs_code or "")[:2].zfill(2)[-2:]
        by_chapter[ch]["preferential"].add(rule.hs_code)

    chapters: list[TariffCoverageChapterOut] = []
    for ch, buckets in sorted(by_chapter.items()):
        class_n = len(buckets["classification"])
        chapters.append(
            TariffCoverageChapterOut(
                chapter=ch,
                classification_codes=class_n,
                bcd_rates=len(buckets["bcd"]),
                sws_rates=len(buckets["sws"]),
                igst_rates=len(buckets["igst"]),
                exemption_rules=len(buckets["exemption"]),
                preferential_rules=len(buckets["preferential"]),
                classification_status="curated" if class_n else "missing",
                bcd_status=_status_from_qualities(buckets["bcd_q"]),
                sws_status=_status_from_qualities(buckets["sws_q"]),
                igst_status=_status_from_qualities(buckets["igst_q"]),
                exemption_status="curated" if buckets["exemption"] else "missing",
                preferential_status="illustrative" if buckets["preferential"] else "missing",
            )
        )
    return TariffCoverageOut(origin=origin_u, destination=dest_u, chapters=chapters)
