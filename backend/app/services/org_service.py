"""Organization / user tenancy helpers (IF-10)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import Settings, get_settings
from backend.app.data.models import Organization, UserAccount
from backend.app.domain.trade import OrganizationOut, UserAccountOut


def _now() -> datetime:
    return datetime.now(UTC)


def ensure_demo_org(session: Session, settings: Settings | None = None) -> Organization:
    settings = settings or get_settings()
    org_id = settings.default_organization_id
    org = session.get(Organization, org_id)
    if org is None:
        org = Organization(
            id=org_id,
            name="TradeGraph Demo Org",
            country="IN",
            tax_identifier=None,
            created_at=_now(),
        )
        session.add(org)
        session.flush()
    user = session.scalar(
        select(UserAccount).where(UserAccount.organization_id == org.id).limit(1)
    )
    if user is None:
        session.add(
            UserAccount(
                id="user_demo_admin",
                organization_id=org.id,
                email="admin@demo.tradegraph.local",
                name="Demo Admin",
                role="admin",
                idp_subject="demo-admin",
                created_at=_now(),
            )
        )
        session.flush()
    return org


def _email_allowlisted(email: str, settings: Settings) -> bool:
    raw = (settings.firebase_allowed_emails or "").strip()
    if not raw:
        return True
    allowed = {e.strip().lower() for e in raw.split(",") if e.strip()}
    return email.lower() in allowed


def _bootstrap_admin(email: str, settings: Settings) -> bool:
    raw = (settings.bootstrap_admin_emails or "").strip()
    if not raw:
        return False
    admins = {e.strip().lower() for e in raw.split(",") if e.strip()}
    return email.lower() in admins


def upsert_firebase_user(
    session: Session,
    *,
    subject: str,
    email: str,
    name: str | None,
    settings: Settings | None = None,
) -> UserAccount:
    """Create or update a user from a verified Firebase ID token."""
    settings = settings or get_settings()
    email_n = (email or "").strip().lower()
    if not email_n:
        raise ValueError("Firebase token missing email")
    if not _email_allowlisted(email_n, settings):
        from backend.app.core.errors import AppError

        raise AppError(
            code="EMAIL_NOT_ALLOWLISTED",
            message="This email is not allowed to access TradeGraph",
            status_code=403,
        )

    org = ensure_demo_org(session, settings)
    row = session.scalar(select(UserAccount).where(UserAccount.idp_subject == subject))
    if row is None:
        row = session.scalar(select(UserAccount).where(UserAccount.email == email_n))
    now = _now()
    if row is None:
        role = "admin" if _bootstrap_admin(email_n, settings) else "operator"
        from uuid import uuid4

        row = UserAccount(
            id=str(uuid4()),
            organization_id=org.id,
            email=email_n,
            name=(name or email_n).strip()[:256],
            role=role,
            idp_subject=subject,
            created_at=now,
            last_login_at=now,
        )
        session.add(row)
    else:
        row.idp_subject = subject
        row.email = email_n
        if name:
            row.name = name.strip()[:256]
        if _bootstrap_admin(email_n, settings) and row.role != "admin":
            row.role = "admin"
        row.last_login_at = now
    session.flush()
    return row


def list_organizations(session: Session) -> list[OrganizationOut]:
    ensure_demo_org(session)
    rows = session.scalars(select(Organization).order_by(Organization.name)).all()
    return [
        OrganizationOut(
            id=r.id,
            name=r.name,
            country=r.country,
            tax_identifier=r.tax_identifier,
            created_at=r.created_at,
        )
        for r in rows
    ]


def resolve_user_by_idp_subject(
    session: Session, subject: str
) -> UserAccountOut | None:
    row = session.scalar(select(UserAccount).where(UserAccount.idp_subject == subject))
    if row is None:
        return None
    return UserAccountOut(
        id=row.id,
        organization_id=row.organization_id,
        email=row.email,
        name=row.name,
        role=row.role,
        idp_subject=row.idp_subject,
        created_at=row.created_at,
    )


def idp_configured(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return bool(settings.idp_issuer and settings.idp_audience)
