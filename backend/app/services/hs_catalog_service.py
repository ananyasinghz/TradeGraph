"""Upsert HS nomenclature into hs_codes + synonyms + FTS5 index."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from backend.app.data.models import HsCode, HsSynonym
from backend.app.integrations.adapters.pdf_document import extract_pdf_pages
from backend.app.services.hs_nomenclature_parser import (
    HsRecord,
    chapter_of,
    parent_of,
    parse_pages,
)

ROOT = Path(__file__).resolve().parents[3]

# Common trade synonyms keyed by HS prefix (heading)
DEFAULT_SYNONYMS: list[tuple[str, str, float]] = [
    ("6109", "t-shirt", 1.5),
    ("6109", "tshirt", 1.5),
    ("6109", "tee", 1.0),
    ("6105", "shirt", 1.2),
    ("6106", "blouse", 1.2),
    ("6110", "jersey", 1.2),
    ("6110", "pullover", 1.2),
    ("6110", "sweater", 1.2),
    ("6203", "trousers", 1.5),
    ("6203", "pants", 1.4),
    ("6203", "slacks", 1.2),
    ("6204", "trousers", 1.3),
    ("6204", "pants", 1.2),
    ("6103", "trousers", 1.2),
    ("6103", "pants", 1.1),
    ("7318", "screw", 1.5),
    ("7318", "bolt", 1.3),
    ("7318", "screws", 1.5),
    ("8471", "laptop", 1.5),
    ("8471", "computer", 1.2),
    ("8517", "smartphone", 1.5),
    ("8517", "mobile", 1.3),
    ("6111", "babies", 1.4),
    ("6111", "baby", 1.4),
    ("6108", "briefs", 1.4),
    ("6108", "panties", 1.3),
    ("6108", "underwear", 1.2),
    ("6402", "footwear", 1.3),
    ("6402", "shoes", 1.2),
]


def ensure_fts(session: Session) -> None:
    session.execute(
        text(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS hs_codes_fts USING fts5(
                code UNINDEXED,
                description,
                synonyms,
                tokenize = 'porter'
            )
            """
        )
    )
    session.flush()


def rebuild_fts(session: Session) -> int:
    ensure_fts(session)
    session.execute(text("DELETE FROM hs_codes_fts"))
    rows = session.scalars(select(HsCode)).all()
    syn_map: dict[str, list[str]] = {}
    for syn in session.scalars(select(HsSynonym)).all():
        syn_map.setdefault(syn.hs_code, []).append(syn.term)
    count = 0
    for row in rows:
        syn_text = " ".join(syn_map.get(row.code, []))
        session.execute(
            text(
                "INSERT INTO hs_codes_fts(code, description, synonyms) "
                "VALUES (:code, :description, :synonyms)"
            ),
            {
                "code": row.code,
                "description": row.description,
                "synonyms": syn_text,
            },
        )
        count += 1
    session.flush()
    return count


def upsert_from_records(
    session: Session,
    records: Iterable[HsRecord],
    *,
    seed_default_synonyms: bool = True,
) -> dict[str, int]:
    ensure_fts(session)
    inserted = 0
    updated = 0
    now = datetime.now(UTC)
    for rec in records:
        digits = re.sub(r"\D", "", rec.code)
        heading = digits[:4] if len(digits) >= 4 else None
        existing = session.get(HsCode, rec.code)
        if existing is None:
            session.add(
                HsCode(
                    code=rec.code,
                    description=rec.description,
                    chapter=rec.chapter,
                    parent_code=rec.parent_code,
                    source_pack=rec.source_pack,
                    heading=heading,
                    updated_at=now,
                )
            )
            inserted += 1
        else:
            existing.description = rec.description
            existing.chapter = rec.chapter
            existing.parent_code = rec.parent_code
            existing.source_pack = rec.source_pack
            existing.heading = heading
            existing.updated_at = now
            updated += 1
    session.flush()

    syn_added = 0
    if seed_default_synonyms:
        syn_added = seed_synonyms(session)

    fts_count = rebuild_fts(session)
    return {
        "inserted": inserted,
        "updated": updated,
        "synonyms_added": syn_added,
        "fts_rows": fts_count,
    }


def seed_synonyms(session: Session) -> int:
    added = 0
    codes = {c.code: c for c in session.scalars(select(HsCode)).all()}
    for prefix, term, weight in DEFAULT_SYNONYMS:
        matches = [c for c in codes if c.replace(".", "").startswith(prefix)]
        for code in matches[:40]:  # cap per prefix
            exists = session.scalar(
                select(HsSynonym).where(HsSynonym.hs_code == code, HsSynonym.term == term)
            )
            if exists is not None:
                continue
            session.add(
                HsSynonym(id=str(uuid4()), hs_code=code, term=term, weight=weight)
            )
            added += 1
    session.flush()
    return added


def upsert_from_json_list(
    session: Session,
    items: list[dict[str, object]],
    *,
    seed_default_synonyms: bool = True,
) -> dict[str, int]:
    records: list[HsRecord] = []
    for item in items:
        code = str(item.get("code") or "").strip()
        desc = str(item.get("description") or "").strip()
        if not code or not desc:
            continue
        chapter = str(item.get("chapter") or chapter_of(code))
        records.append(
            HsRecord(
                code=code,
                description=desc,
                chapter=chapter,
                parent_code=parent_of(code),
                source_pack=str(item.get("source_pack") or "json"),
            )
        )
    return upsert_from_records(
        session, records, seed_default_synonyms=seed_default_synonyms
    )


def load_min_fixture(session: Session) -> dict[str, int]:
    path = ROOT / "config" / "trade" / "fixtures" / "hs" / "nomenclature_min.v1.json"
    items = json.loads(path.read_text(encoding="utf-8"))
    return upsert_from_json_list(session, items)


def load_from_pdf(session: Session, pdf_path: Path, *, style: str = "auto") -> dict[str, int]:
    pages = extract_pdf_pages(pdf_path)
    records = parse_pages(pages, source_pack=pdf_path.stem, style=style)
    return upsert_from_records(session, records)


def load_from_jsonl_pages(
    session: Session, jsonl_path: Path, *, source_pack: str, style: str = "auto"
) -> dict[str, int]:
    pages: list[dict[str, object]] = []
    with jsonl_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                pages.append(json.loads(line))
    records = parse_pages(pages, source_pack=source_pack, style=style)
    return upsert_from_records(session, records)


def fts_search(session: Session, query: str, *, limit: int = 50) -> list[tuple[str, float]]:
    """Return (hs_code, bm25_rank) — lower bm25 is better in SQLite FTS5."""
    ensure_fts(session)
    tokens = re.findall(r"[a-z0-9]+", query.lower())
    stop = {"the", "and", "for", "with", "from", "percent", "100"}
    tokens = [t for t in tokens if len(t) > 2 and t not in stop][:12]
    if not tokens:
        return []

    def _run(match_q: str) -> list[tuple[str, float]]:
        try:
            rows = session.execute(
                text(
                    "SELECT code, bm25(hs_codes_fts) AS rank "
                    "FROM hs_codes_fts WHERE hs_codes_fts MATCH :q "
                    "ORDER BY rank LIMIT :lim"
                ),
                {"q": match_q, "lim": limit},
            ).all()
            return [(str(r[0]), float(r[1])) for r in rows]
        except Exception:
            return []

    hits = _run(" AND ".join(tokens))
    if not hits:
        hits = _run(" OR ".join(tokens))
    return hits


def _fts_query(product_text: str) -> str:
    tokens = re.findall(r"[a-z0-9]+", product_text.lower())
    stop = {"the", "and", "for", "with", "from", "percent", "100"}
    tokens = [t for t in tokens if len(t) > 2 and t not in stop][:12]
    if not tokens:
        return ""
    return " AND ".join(tokens)
