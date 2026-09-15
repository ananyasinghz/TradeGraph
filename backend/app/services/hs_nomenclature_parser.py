"""Parse HS nomenclature text into structured records."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

# ITC spaced: 0302 41 00 or 6109 10 00; dotted: 6109.10; compact: 610910 / 730120
_CODE_SPACED = re.compile(
    r"(?<!\d)(\d{4})(?:\s+(\d{2}))?(?:\s+(\d{2}))?(?!\d)"
)
_CODE_DOTTED = re.compile(r"(?<!\d)(\d{4})\.(\d{2})(?:\.(\d{2}))?(?!\d)")
_CODE_COMPACT = re.compile(r"(?<!\d)(\d{6}|\d{8})(?!\d)")
# Mapping PDF style: "... 730120 Description..."
_MAPPING_LINE = re.compile(
    r"^(?P<cat>.+?)\s+(?P<code>\d{6,8})\s+(?P<desc>.+)$"
)


@dataclass(frozen=True)
class HsRecord:
    code: str
    description: str
    chapter: str
    parent_code: str | None
    source_pack: str
    page: int | None = None


def normalize_hs_code(raw: str) -> str | None:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) < 4:
        return None
    if len(digits) == 4:
        return digits
    if len(digits) == 5:
        return None
    if len(digits) == 6:
        return f"{digits[:4]}.{digits[4:6]}"
    if len(digits) >= 8:
        return f"{digits[:4]}.{digits[4:6]}.{digits[6:8]}"
    # 7 digits — ignore
    return None


def chapter_of(code: str) -> str:
    digits = re.sub(r"\D", "", code)
    return digits[:2] if len(digits) >= 2 else ""


def parent_of(code: str) -> str | None:
    digits = re.sub(r"\D", "", code)
    if len(digits) >= 8:
        return f"{digits[:4]}.{digits[4:6]}"
    if len(digits) >= 6:
        return digits[:4]
    return None


def _clean_desc(text: str) -> str:
    t = re.sub(r"\s+", " ", text).strip(" -:\t")
    return t[:2000]


def parse_mapping_lines(text: str, *, source_pack: str, page: int | None = None) -> list[HsRecord]:
    out: list[HsRecord] = []
    seen: set[str] = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.lower().startswith("product category"):
            continue
        m = _MAPPING_LINE.match(line)
        if not m:
            # fallback: first 6–8 digit token
            cm = _CODE_COMPACT.search(line)
            if not cm:
                continue
            code = normalize_hs_code(cm.group(1))
            if not code:
                continue
            desc = _clean_desc(line[cm.end() :]) or _clean_desc(line[: cm.start()])
            if not desc:
                continue
        else:
            code = normalize_hs_code(m.group("code"))
            if not code:
                continue
            desc = _clean_desc(m.group("desc"))
            cat = _clean_desc(m.group("cat"))
            if cat and cat.lower() not in desc.lower():
                desc = f"{cat}: {desc}" if desc else cat
        if code in seen or len(desc) < 3:
            continue
        seen.add(code)
        out.append(
            HsRecord(
                code=code,
                description=desc,
                chapter=chapter_of(code),
                parent_code=parent_of(code),
                source_pack=source_pack,
                page=page,
            )
        )
    return out


def parse_itc_text(text: str, *, source_pack: str, page: int | None = None) -> list[HsRecord]:
    """Extract HS lines from ITC-HS continuous text (spaced codes)."""
    out: list[HsRecord] = []
    seen: set[str] = set()
    # Prefer lines that start with a code
    for line in text.splitlines():
        raw = line.strip()
        if not raw:
            continue
        m = _CODE_SPACED.match(raw) or _CODE_DOTTED.match(raw)
        if not m:
            continue
        parts = [g for g in m.groups() if g]
        code = normalize_hs_code("".join(parts))
        if not code or len(re.sub(r"\D", "", code)) < 6:
            # skip bare chapter headings like 0302 alone unless 6+
            digits = re.sub(r"\D", "", code or "")
            if len(digits) < 6:
                continue
        desc = _clean_desc(raw[m.end() :])
        # strip leading dashes used in ITC layout
        desc = re.sub(r"^[\-\s]+", "", desc)
        if len(desc) < 4:
            continue
        if code in seen:
            continue
        seen.add(code)
        out.append(
            HsRecord(
                code=code,
                description=desc,
                chapter=chapter_of(code),
                parent_code=parent_of(code),
                source_pack=source_pack,
                page=page,
            )
        )
    return out


def parse_pages(
    pages: Iterable[dict[str, object]],
    *,
    source_pack: str,
    style: str = "auto",
) -> list[HsRecord]:
    by_code: dict[str, HsRecord] = {}
    for row in pages:
        text = str(row.get("text") or "")
        page = int(row["page"]) if row.get("page") is not None else None
        if style == "mapping" or (style == "auto" and "ITC-HS Codes" in text[:200]):
            records = parse_mapping_lines(text, source_pack=source_pack, page=page)
        else:
            records = parse_itc_text(text, source_pack=source_pack, page=page)
            if style == "auto" and not records:
                records = parse_mapping_lines(text, source_pack=source_pack, page=page)
        for rec in records:
            prev = by_code.get(rec.code)
            if prev is None or len(rec.description) > len(prev.description):
                by_code[rec.code] = rec
    return sorted(by_code.values(), key=lambda r: r.code)
