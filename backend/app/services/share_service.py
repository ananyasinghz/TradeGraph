"""Client share tokens for readiness + papers only (R11)."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.errors import AppError
from backend.app.data.models import ShareLink, Shipment
from backend.app.domain.trade import PublicShareOut, ShareLinkOut
from backend.app.services import readiness_service, shipment_service
from backend.app.services.auth_service import Principal


def _now() -> datetime:
    return datetime.now(UTC)


def create_share_link(
    session: Session,
    shipment_id: str,
    *,
    principal: Principal,
    organization_id: str | None = None,
    expires_days: int = 14,
) -> ShareLinkOut:
    shipment_service.get_shipment(session, shipment_id, organization_id=organization_id)
    row = session.get(Shipment, shipment_id)
    assert row is not None
    token = secrets.token_urlsafe(24)
    link = ShareLink(
        token=token,
        shipment_id=shipment_id,
        organization_id=row.organization_id,
        created_by=principal.actor,
        created_at=_now(),
        expires_at=_now() + timedelta(days=expires_days),
    )
    session.add(link)
    session.flush()
    return ShareLinkOut(
        id=link.id,
        token=link.token,
        shipment_id=link.shipment_id,
        organization_id=link.organization_id,
        created_by=link.created_by,
        created_at=link.created_at,
        expires_at=link.expires_at,
        share_path=f"/public/share/{link.token}",
    )


def get_public_share(session: Session, token: str) -> PublicShareOut:
    link = session.scalar(select(ShareLink).where(ShareLink.token == token))
    if link is None or link.revoked_at is not None:
        raise AppError(code="SHARE_NOT_FOUND", message="Share link not found", status_code=404)
    if link.expires_at is not None:
        exp = link.expires_at if link.expires_at.tzinfo else link.expires_at.replace(tzinfo=UTC)
        if exp < _now():
            raise AppError(code="SHARE_EXPIRED", message="Share link expired", status_code=410)
    detail = shipment_service.get_shipment(session, link.shipment_id)
    readiness = readiness_service.score_shipment(session, link.shipment_id)
    papers = list(detail.checklist.items) if detail.checklist else []
    return PublicShareOut(
        shipment_id=detail.id,
        title=detail.title,
        readiness=readiness,
        papers=papers,
    )
