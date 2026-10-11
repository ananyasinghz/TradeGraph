"""Simple product template CRUD (R8 optional)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.errors import AppError
from backend.app.data.models import ProductTemplate
from backend.app.domain.trade import (
    ProductTemplateCreate,
    ProductTemplateOut,
    ProductTemplateUpdate,
)


def _now() -> datetime:
    return datetime.now(UTC)


def _out(row: ProductTemplate) -> ProductTemplateOut:
    return ProductTemplateOut(
        id=row.id,
        organization_id=row.organization_id,
        name=row.name,
        product_text=row.product_text,
        hs_code=row.hs_code,
        origin=row.origin,
        destination=row.destination,
        notes=row.notes,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def list_templates(session: Session, *, organization_id: str) -> list[ProductTemplateOut]:
    rows = session.scalars(
        select(ProductTemplate)
        .where(ProductTemplate.organization_id == organization_id)
        .order_by(ProductTemplate.name)
    ).all()
    return [_out(r) for r in rows]


def create_template(
    session: Session, payload: ProductTemplateCreate, *, organization_id: str
) -> ProductTemplateOut:
    now = _now()
    row = ProductTemplate(
        organization_id=organization_id,
        name=payload.name.strip(),
        product_text=payload.product_text,
        hs_code=payload.hs_code,
        origin=payload.origin.upper() if payload.origin else None,
        destination=payload.destination.upper() if payload.destination else None,
        notes=payload.notes,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.flush()
    return _out(row)


def update_template(
    session: Session,
    template_id: str,
    payload: ProductTemplateUpdate,
    *,
    organization_id: str,
) -> ProductTemplateOut:
    row = session.get(ProductTemplate, template_id)
    if row is None or row.organization_id != organization_id:
        raise AppError(code="TEMPLATE_NOT_FOUND", message="Template not found", status_code=404)
    data = payload.model_dump(exclude_unset=True)
    for key in ("origin", "destination"):
        if key in data and isinstance(data[key], str):
            data[key] = data[key].upper()
    for key, value in data.items():
        setattr(row, key, value)
    row.updated_at = _now()
    session.flush()
    return _out(row)
