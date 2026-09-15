"""Source selection policy for multi-source corridors (IF-7)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from backend.app.core.config import Settings, get_settings
from backend.app.data.models import SourceDocument, TariffRate
from backend.app.services import corridor_service
from backend.app.services.data_quality import is_verified_quality


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class SourceSelectionService:
    """
    Prefer:
    1. demo_verified/source_verified approved quality
    2. matching regime
    3. current effective date
    4. complete evidence (source document archived)
    5. recently refreshed source
    Conflicts → flag for review (returned in warnings).
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def select_tariff_candidates(
        self,
        session: Session,
        *,
        origin: str,
        destination: str,
        hs_code: str,
        as_of: date,
        regime: str | None = None,
    ) -> list[TariffRate]:
        stmt = (
            select(TariffRate)
            .options(joinedload(TariffRate.source_document), joinedload(TariffRate.hs))
            .where(
                TariffRate.hs_code == hs_code,
                TariffRate.origin == origin.upper(),
                TariffRate.destination == destination.upper(),
                TariffRate.effective_from <= as_of,
                or_(TariffRate.effective_to.is_(None), TariffRate.effective_to >= as_of),
            )
        )
        rows = list(session.scalars(stmt).unique().all())
        if regime:
            preferred = [
                r
                for r in rows
                if (r.regime or "").upper() == regime.upper()
                or (r.agreement_id or "").upper() == regime.upper()
            ]
            if preferred:
                rows = preferred
        return sorted(rows, key=self._score, reverse=True)

    def select_best_tariff(
        self,
        session: Session,
        *,
        origin: str,
        destination: str,
        hs_code: str,
        as_of: date,
        regime: str | None = None,
    ) -> tuple[TariffRate | None, list[str]]:
        candidates = self.select_tariff_candidates(
            session,
            origin=origin,
            destination=destination,
            hs_code=hs_code,
            as_of=as_of,
            regime=regime,
        )
        warnings: list[str] = []
        if not candidates:
            return None, warnings
        best = candidates[0]
        # Conflict: another candidate with different rate and similar score band
        for other in candidates[1:]:
            if other.rate != best.rate and abs(self._score(other) - self._score(best)) < 5:
                warnings.append(
                    f"Conflicting rate {other.rate} from {other.source_document_id} "
                    f"vs {best.rate} from {best.source_document_id} — flagged for review"
                )
                break
        return best, warnings

    def preferred_source_codes(
        self, session: Session, origin: str, destination: str
    ) -> list[str]:
        corridor = corridor_service.get_corridor(session, origin, destination)
        if corridor is None:
            return []
        return list(corridor.tariff_source_codes or [])

    def is_source_stale(self, doc: SourceDocument | None) -> bool:
        if doc is None:
            return True
        retrieved = _as_utc(doc.fetched_at or doc.retrieved_at)
        if retrieved is None:
            return True
        max_age = timedelta(hours=self.settings.live_feed_max_age_hours)
        return datetime.now(UTC) - retrieved > max_age

    def _score(self, row: TariffRate) -> float:
        score = 0.0
        if is_verified_quality(row.data_quality):
            score += 50
        elif row.data_quality == "illustrative":
            score += 10
        if row.status == "active":
            score += 20
        if row.source_document is not None:
            doc = row.source_document
            if doc.archive_path or doc.file_path:
                score += 15
            if doc.checksum:
                score += 5
            if doc.status in {"published", "approved"}:
                score += 10
            retrieved = _as_utc(doc.fetched_at or doc.retrieved_at)
            if retrieved is not None:
                age_h = (datetime.now(UTC) - retrieved).total_seconds() / 3600
                score += max(0.0, 10.0 - min(age_h, 10.0))
        score += float(row.version or 0)
        return score
