"""Org-scoped party CRUD (clearance R8)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from backend.app.core.errors import AppError
from backend.app.data.models import Party
from backend.app.domain.trade import PartyCreate, PartyOut, PartyUpdate


def _now() -> datetime:
    return datetime.now(UTC)


def _out(row: Party) -> PartyOut:
    return PartyOut(
        id=row.id,
        organization_id=row.organization_id,
        name=row.name,
        role=row.role,
        country=row.country,
        address_text=row.address_text,
        tax_id=row.tax_id,
        notes=row.notes,
        created_at=row.created_at,
    )


def list_parties(session: Session, *, organization_id: str) -> list[PartyOut]:
    rows = session.scalars(
        select(Party)
        .where(
            or_(
                Party.organization_id == organization_id,
                Party.organization_id.is_(None),
            )
        )
        .order_by(Party.name)
    ).all()
    return [_out(r) for r in rows]


def create_party(
    session: Session, payload: PartyCreate, *, organization_id: str
) -> PartyOut:
    row = Party(
        organization_id=organization_id,
        name=payload.name.strip(),
        role=payload.role,
        country=payload.country.upper() if payload.country else None,
        address_text=payload.address_text,
        tax_id=payload.tax_id,
        notes=payload.notes,
        created_at=_now(),
    )
    session.add(row)
    session.flush()
    return _out(row)


def update_party(
    session: Session,
    party_id: str,
    payload: PartyUpdate,
    *,
    organization_id: str,
) -> PartyOut:
    row = session.get(Party, party_id)
    if row is None:
        raise AppError(code="PARTY_NOT_FOUND", message="Party not found", status_code=404)
    if row.organization_id and row.organization_id != organization_id:
        raise AppError(code="ORG_FORBIDDEN", message="Party not in your organization", status_code=403)
    data = payload.model_dump(exclude_unset=True)
    if "country" in data and isinstance(data["country"], str):
        data["country"] = data["country"].upper()
    if "name" in data and isinstance(data["name"], str):
        data["name"] = data["name"].strip()
    for key, value in data.items():
        setattr(row, key, value)
    if row.organization_id is None:
        row.organization_id = organization_id
    session.flush()
    return _out(row)
