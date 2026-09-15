"""Keyword retrieval over regulatory text chunks (no paid vector DB)."""

from __future__ import annotations

import re
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.data.models import RegulatoryChunk
from backend.app.domain.trade import RetrievalHit


def _tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2]


def search_chunks(
    session: Session,
    *,
    query: str,
    hs_code: str | None = None,
    top_k: int = 5,
) -> list[RetrievalHit]:
    rows = session.scalars(select(RegulatoryChunk)).all()
    q_tokens = _tokenize(query)
    if not q_tokens:
        return []

    q_counts = Counter(q_tokens)
    scored: list[tuple[float, RegulatoryChunk]] = []
    for row in rows:
        if hs_code and row.hs_code == hs_code:
            hs_bonus = 2.0
        elif hs_code is None:
            hs_bonus = 0.5
        else:
            hs_bonus = 0.2

        doc_tokens = _tokenize(row.text + " " + " ".join(row.tags or []))
        if not doc_tokens:
            continue
        overlap = sum(min(q_counts[t], c) for t, c in Counter(doc_tokens).items() if t in q_counts)
        if overlap <= 0 and hs_bonus < 2.0:
            continue
        score = float(overlap) + hs_bonus
        scored.append((score, row))

    scored.sort(key=lambda item: item[0], reverse=True)
    hits: list[RetrievalHit] = []
    for score, row in scored[:top_k]:
        hits.append(
            RetrievalHit(
                chunk_id=row.id,
                source_document_id=row.source_document_id,
                hs_code=row.hs_code,
                score=round(score, 3),
                text=row.text,
                tags=list(row.tags or []),
            )
        )
    return hits
