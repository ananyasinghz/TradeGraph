"""Admin user and invite management (clearance R6–R7)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.errors import AppError
from backend.app.data.models import Organization, UserAccount, UserInvite
from backend.app.domain.trade import (
    AdminUserOut,
    AdminUserRoleUpdate,
    UserInviteCreate,
    UserInviteOut,
)
from backend.app.services.auth_service import Principal, _ROLE_RANK


def _now() -> datetime:
    return datetime.now(UTC)


def _user_out(row: UserAccount, org_name: str | None = None) -> AdminUserOut:
    return AdminUserOut(
        id=row.id,
        email=row.email,
        name=row.name,
        role=row.role,
        organization_id=row.organization_id,
        organization_name=org_name,
        created_at=row.created_at,
    )


def list_users(session: Session, *, organization_id: str | None = None) -> list[AdminUserOut]:
    stmt = select(UserAccount).order_by(UserAccount.email)
    if organization_id:
        stmt = stmt.where(UserAccount.organization_id == organization_id)
    rows = session.scalars(stmt).all()
    org_ids = {r.organization_id for r in rows}
    orgs = {
        o.id: o.name
        for o in session.scalars(select(Organization).where(Organization.id.in_(org_ids))).all()
    } if org_ids else {}
    return [_user_out(r, orgs.get(r.organization_id)) for r in rows]


def set_user_role(
    session: Session,
    user_id: str,
    payload: AdminUserRoleUpdate,
    *,
    organization_id: str | None = None,
) -> AdminUserOut:
    row = session.get(UserAccount, user_id)
    if row is None:
        raise AppError(code="USER_NOT_FOUND", message="User not found", status_code=404)
    if organization_id and row.organization_id != organization_id:
        raise AppError(code="ORG_FORBIDDEN", message="User not in your organization", status_code=403)
    role = payload.role
    if role not in _ROLE_RANK:
        raise AppError(code="INVALID_ROLE", message=f"Invalid role: {role}", status_code=400)
    row.role = role
    session.flush()
    org = session.get(Organization, row.organization_id)
    return _user_out(row, org.name if org else None)


def _invite_out(row: UserInvite) -> UserInviteOut:
    return UserInviteOut(
        id=row.id,
        organization_id=row.organization_id,
        email=row.email,
        role=row.role,
        invited_by=row.invited_by,
        status=row.status,
        created_at=row.created_at,
        accepted_at=row.accepted_at,
    )


def create_invite(
    session: Session,
    payload: UserInviteCreate,
    *,
    principal: Principal,
    organization_id: str,
) -> UserInviteOut:
    email = payload.email.strip().lower()
    if not email or "@" not in email:
        raise AppError(code="INVALID_EMAIL", message="Valid email required", status_code=400)
    existing = session.scalar(
        select(UserInvite).where(
            UserInvite.organization_id == organization_id,
            UserInvite.email == email,
            UserInvite.status == "pending",
        )
    )
    if existing is not None:
        return _invite_out(existing)
    row = UserInvite(
        organization_id=organization_id,
        email=email,
        role=payload.role,
        invited_by=principal.actor,
        status="pending",
        created_at=_now(),
    )
    session.add(row)
    session.flush()
    from backend.app.services import email_service

    email_service.send_email(
        to=email,
        subject="TradeGraph invitation",
        body=f"You have been invited to TradeGraph as {payload.role}.",
    )
    return _invite_out(row)


def list_invites(session: Session, *, organization_id: str) -> list[UserInviteOut]:
    rows = session.scalars(
        select(UserInvite)
        .where(UserInvite.organization_id == organization_id)
        .order_by(UserInvite.created_at.desc())
    ).all()
    return [_invite_out(r) for r in rows]
