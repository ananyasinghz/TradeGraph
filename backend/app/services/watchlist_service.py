"""HS/corridor watchlist and rate-change feed."""

from __future__ import annotations

from datetime import UTC, datetime
from itertools import pairwise

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.errors import AppError
from backend.app.data.models import Shipment, WatchlistItem
from backend.app.domain.trade import WatchlistChange, WatchlistItemCreate, WatchlistItemOut
from backend.app.services import tariff_service


def _now() -> datetime:
    return datetime.now(UTC)


def _item_out(session: Session, row: WatchlistItem) -> WatchlistItemOut:
    title: str | None = None
    if row.shipment_id:
        ship = session.get(Shipment, row.shipment_id)
        title = ship.title if ship else None
    return WatchlistItemOut(
        id=row.id,
        hs_code=row.hs_code,
        origin=row.origin,
        destination=row.destination,
        created_at=row.created_at,
        last_seen_rate_id=row.last_seen_rate_id,
        shipment_id=row.shipment_id,
        shipment_title=title,
        organization_id=row.organization_id,
    )


def list_items(
    session: Session, *, organization_id: str | None = None
) -> list[WatchlistItemOut]:
    stmt = select(WatchlistItem).order_by(WatchlistItem.created_at.desc())
    if organization_id:
        stmt = stmt.where(WatchlistItem.organization_id == organization_id)
    rows = session.scalars(stmt).all()
    return [_item_out(session, r) for r in rows]


def add_item(
    session: Session,
    payload: WatchlistItemCreate,
    *,
    organization_id: str | None = None,
) -> WatchlistItemOut:
    hs_code = payload.hs_code
    origin = payload.origin.upper()
    destination = payload.destination.upper()
    shipment_id = payload.shipment_id

    if shipment_id:
        ship = session.get(Shipment, shipment_id)
        if ship is None:
            raise AppError(
                code="SHIPMENT_NOT_FOUND", message="Shipment not found", status_code=404
            )
        origin = ship.origin.upper()
        destination = ship.destination.upper()
        if not hs_code:
            if not ship.hs_code_working:
                raise AppError(
                    code="HS_REQUIRED",
                    message="Shipment has no working HS code to watch",
                    status_code=400,
                )
            hs_code = ship.hs_code_working

    assert hs_code is not None

    stmt = select(WatchlistItem).where(
        WatchlistItem.hs_code == hs_code,
        WatchlistItem.origin == origin,
        WatchlistItem.destination == destination,
    )
    if shipment_id:
        stmt = stmt.where(WatchlistItem.shipment_id == shipment_id)
    else:
        stmt = stmt.where(WatchlistItem.shipment_id.is_(None))
    existing = session.scalar(stmt)
    if existing is not None:
        return _item_out(session, existing)

    active = tariff_service.list_tariffs(
        session,
        hs_code=hs_code,
        origin=origin,
        destination=destination,
        include_history=False,
    )
    from backend.app.core.config import get_settings
    from backend.app.services.org_service import ensure_demo_org

    org = ensure_demo_org(session, get_settings())
    row = WatchlistItem(
        hs_code=hs_code,
        origin=origin,
        destination=destination,
        created_at=_now(),
        last_seen_rate_id=active[0].id if active else None,
        shipment_id=shipment_id,
        organization_id=organization_id or org.id,
    )
    session.add(row)
    session.flush()
    return _item_out(session, row)


def delete_item(
    session: Session, item_id: str, *, organization_id: str | None = None
) -> None:
    row = session.get(WatchlistItem, item_id)
    if row is None:
        raise AppError(
            code="WATCHLIST_NOT_FOUND", message="Watchlist item not found", status_code=404
        )
    if (
        organization_id
        and row.organization_id
        and row.organization_id != organization_id
    ):
        raise AppError(
            code="ORG_FORBIDDEN",
            message="Watchlist item not in your organization",
            status_code=403,
        )
    session.delete(row)
    session.flush()


def _affected_shipments(
    session: Session, item: WatchlistItem
) -> tuple[list[str], list[str]]:
    ids: list[str] = []
    titles: list[str] = []
    seen: set[str] = set()

    def _add(ship: Shipment | None) -> None:
        if ship is None or ship.id in seen:
            return
        seen.add(ship.id)
        ids.append(ship.id)
        titles.append(ship.title)

    if item.shipment_id:
        _add(session.get(Shipment, item.shipment_id))

    matches = session.scalars(
        select(Shipment).where(
            Shipment.hs_code_working == item.hs_code,
            Shipment.origin == item.origin,
            Shipment.destination == item.destination,
        )
    ).all()
    for ship in matches:
        _add(ship)
    return ids, titles


def list_changes(
    session: Session, *, organization_id: str | None = None
) -> list[WatchlistChange]:
    """Emit supersession events for watched HS corridors from tariff history."""
    stmt = select(WatchlistItem)
    if organization_id:
        stmt = stmt.where(WatchlistItem.organization_id == organization_id)
    items = session.scalars(stmt).all()
    changes: list[WatchlistChange] = []
    for item in items:
        history = tariff_service.list_tariffs(
            session,
            hs_code=item.hs_code,
            origin=item.origin,
            destination=item.destination,
            include_history=True,
        )
        by_version = sorted(history, key=lambda r: r.version)
        affected_ids, affected_titles = _affected_shipments(session, item)
        for older, newer in pairwise(by_version):
            if older.rate == newer.rate:
                continue
            if older.superseded_by == newer.id or (
                older.status == "superseded" and newer.version > older.version
            ):
                base = (
                    f"{item.hs_code} {item.origin}→{item.destination}: "
                    f"{older.rate}% → {newer.rate}% effective {newer.effective_from}"
                )
                if affected_titles:
                    named = ", ".join(f"“{t}”" for t in affected_titles)
                    summary = f"{base} — may affect {named}."
                else:
                    summary = base
                changes.append(
                    WatchlistChange(
                        watchlist_item_id=item.id,
                        hs_code=item.hs_code,
                        origin=item.origin,
                        destination=item.destination,
                        old_rate=older.rate,
                        new_rate=newer.rate,
                        old_version=older.version,
                        new_version=newer.version,
                        effective_from=newer.effective_from,
                        source_document_id=newer.source_document_id,
                        summary=summary,
                        affected_shipment_ids=affected_ids,
                        affected_shipment_titles=affected_titles,
                    )
                )
        active = next((r for r in history if r.status == "active"), None)
        if active is not None:
            item.last_seen_rate_id = active.id
    session.flush()
    changes.sort(key=lambda c: c.effective_from, reverse=True)
    return changes
