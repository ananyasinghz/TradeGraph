"""Publishing stage facade."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.domain.trade import IngestionBatchDetail
from backend.app.ingestion import approval


def publish_approved_batch(
    session: Session,
    batch_id: str,
    notes: str | None = None,
) -> IngestionBatchDetail:
    """Approve + publish (same gate). Separate name for pipeline clarity."""
    return approval.approve(session, batch_id, notes=notes)
