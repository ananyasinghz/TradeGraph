"""Organization / user tenancy helpers (IF-10)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import Settings, get_settings
from backend.app.core.errors import AppError
from backend.app.data.models import Organization, UserAccount
from backend.app.domain.trade import OrganizationOut, UserAccountOut

if TYPE_CHECKING:
    from backend.app.services.auth_service import Principal


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
            mfa_required=False,
            created_at=_now(),
        )
        session.add(org)
        session.flush()
    # Ensure demo role accounts exist for local/token auth tests.
    demo_users = (
        ("user_demo_admin", "admin@demo.tradegraph.local", "Demo Admin", "admin", "demo-admin"),
        ("user_demo_operator", "operator@demo.tradegraph.local", "Demo Operator", "operator", "demo-operator"),
        ("user_demo_reviewer", "reviewer@demo.tradegraph.local", "Demo Reviewer", "reviewer", "demo-reviewer"),
        ("user_demo_viewer", "viewer@demo.tradegraph.local", "Demo Viewer", "viewer", "demo-viewer"),
    )
    for uid, email, name, role, subject in demo_users:
        existing = session.get(UserAccount, uid) or session.scalar(
            select(UserAccount).where(UserAccount.email == email)
        )
        if existing is None:
            session.add(
                UserAccount(
                    id=uid,
                    organization_id=org.id,
                    email=email,
                    name=name,
                    role=role,
                    idp_subject=subject,
                    notification_prefs={"watchlist_email": True, "in_app": True},
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
    """Create or update a user from a verified Firebase ID token.

    Avoid writing ``last_login_at`` on every authenticated request — the SPA
    fires many parallel calls and SQLite otherwise hits ``database is locked``.
    """
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
    dirty = False
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
        dirty = True
    else:
        if row.idp_subject != subject:
            row.idp_subject = subject
            dirty = True
        if row.email != email_n:
            row.email = email_n
            dirty = True
        if name:
            cleaned = name.strip()[:256]
            if row.name != cleaned:
                row.name = cleaned
                dirty = True
        if _bootstrap_admin(email_n, settings) and row.role != "admin":
            row.role = "admin"
            dirty = True
        # Touch last_login at most every 5 minutes to cut write contention.
        last = row.last_login_at
        if last is None:
            row.last_login_at = now
            dirty = True
        else:
            last_aware = last if last.tzinfo is not None else last.replace(tzinfo=UTC)
            if (now - last_aware).total_seconds() >= 300:
                row.last_login_at = now
                dirty = True
    if dirty:
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
            mfa_required=bool(getattr(r, "mfa_required", False)),
            slack_webhook_url=getattr(r, "slack_webhook_url", None),
            created_at=r.created_at,
        )
        for r in rows
    ]


def _user_out(row: UserAccount) -> UserAccountOut:
    return UserAccountOut(
        id=row.id,
        organization_id=row.organization_id,
        email=row.email,
        name=row.name,
        role=row.role,
        idp_subject=row.idp_subject,
        notification_prefs=dict(row.notification_prefs or {}),
        created_at=row.created_at,
    )


def resolve_user_by_idp_subject(
    session: Session, subject: str
) -> UserAccountOut | None:
    row = session.scalar(select(UserAccount).where(UserAccount.idp_subject == subject))
    if row is None:
        return None
    return _user_out(row)


def resolve_user_for_principal(
    session: Session,
    principal: Principal,
    settings: Settings | None = None,
) -> UserAccount | None:
    """Resolve or create a UserAccount row for the authenticated principal."""
    settings = settings or get_settings()
    org = ensure_demo_org(session, settings)
    row: UserAccount | None = None
    if principal.user_id:
        row = session.get(UserAccount, principal.user_id)
    if row is None and principal.email:
        row = session.scalar(
            select(UserAccount).where(UserAccount.email == principal.email.lower())
        )
    if row is None and principal.actor:
        row = session.scalar(
            select(UserAccount).where(UserAccount.idp_subject == principal.actor)
        )
    if row is None and (principal.authenticated or not settings.auth_enabled):
        from uuid import uuid4

        email = (principal.email or f"{principal.actor}@demo.tradegraph.local").lower()
        # Prefer seeded demo admin when auth is off.
        if not settings.auth_enabled:
            seeded = session.get(UserAccount, "user_demo_admin")
            if seeded is not None:
                return seeded
        row = UserAccount(
            id=str(uuid4()),
            organization_id=principal.organization_id or org.id,
            email=email,
            name=principal.actor,
            role=principal.role,
            idp_subject=principal.actor,
            notification_prefs={"watchlist_email": True, "in_app": True},
            created_at=_now(),
        )
        session.add(row)
        session.flush()
    return row


def update_me(
    session: Session,
    principal: Principal,
    *,
    display_name: str | None = None,
    notification_prefs: dict[str, Any] | None = None,
    settings: Settings | None = None,
) -> UserAccountOut:
    row = resolve_user_for_principal(session, principal, settings=settings)
    if row is None:
        raise AppError(
            code="USER_NOT_FOUND",
            message="No user account for principal",
            status_code=404,
        )
    if display_name is not None:
        row.name = display_name.strip()[:256]
    if notification_prefs is not None:
        merged = dict(row.notification_prefs or {})
        merged.update(notification_prefs)
        row.notification_prefs = merged
    session.flush()
    return _user_out(row)


def idp_configured(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return bool(settings.idp_issuer and settings.idp_audience)
