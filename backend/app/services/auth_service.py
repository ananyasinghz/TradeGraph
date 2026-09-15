"""Auth principals, Firebase/JWT/JWKS, role checks, and audit logging."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated, Any, Literal

import httpx
import jwt
from fastapi import Depends, Header, Request
from jwt import PyJWKClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.dependencies import SessionDep, SettingsDep
from backend.app.core.config import Settings
from backend.app.core.errors import AppError
from backend.app.data.models import AuditLog
from backend.app.domain.trade import AuditLogOut, AuthWhoAmI
from backend.app.services import firebase_auth, org_service

Role = Literal["viewer", "operator", "reviewer", "admin"]
_ROLE_RANK: dict[str, int] = {
    "viewer": 1,
    "operator": 2,
    "reviewer": 3,
    "admin": 4,
}


@dataclass(frozen=True)
class Principal:
    actor: str
    role: Role
    authenticated: bool
    organization_id: str | None = None
    auth_method: str = "none"  # none | demo_token | jwt | firebase
    email: str | None = None
    user_id: str | None = None


def parse_token_map(raw: str) -> dict[str, tuple[str, Role]]:
    """Parse TRADE_AUTH_TOKENS: token:actor:role,..."""
    mapping: dict[str, tuple[str, Role]] = {}
    for part in (raw or "").split(","):
        item = part.strip()
        if not item:
            continue
        bits = item.split(":")
        if len(bits) != 3:
            continue
        token, actor, role = bits[0].strip(), bits[1].strip(), bits[2].strip().lower()
        if role not in _ROLE_RANK:
            continue
        mapping[token] = (actor, role)  # type: ignore[assignment]
    return mapping


def _demo_tokens_allowed(settings: Settings) -> bool:
    return settings.environment in {"development", "test"}


@lru_cache(maxsize=4)
def _jwks_client(url: str) -> PyJWKClient:
    return PyJWKClient(url, cache_keys=True, lifespan=300)


def verify_jwt_bearer(token: str, settings: Settings) -> Principal:
    """Validate Bearer JWT via JWKS (issuer + audience required)."""
    if not settings.idp_jwks_url or not settings.idp_issuer or not settings.idp_audience:
        raise AppError(
            code="IDP_NOT_CONFIGURED",
            message="JWT auth requires TRADE_IDP_ISSUER, TRADE_IDP_AUDIENCE, TRADE_IDP_JWKS_URL",
            status_code=501,
        )
    try:
        client = _jwks_client(settings.idp_jwks_url)
        signing_key = client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256", "ES256"],
            audience=settings.idp_audience,
            issuer=settings.idp_issuer,
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise AppError(
            code="AUTH_INVALID",
            message=f"Invalid JWT: {exc}",
            status_code=401,
        ) from exc
    except (httpx.HTTPError, OSError) as exc:
        raise AppError(
            code="JWKS_UNAVAILABLE",
            message=f"JWKS fetch failed: {exc}",
            status_code=503,
        ) from exc

    sub = str(claims.get("sub") or "")
    if not sub:
        raise AppError(code="AUTH_INVALID", message="JWT missing sub", status_code=401)

    role_raw = (
        claims.get("trade_role")
        or claims.get("role")
        or (claims.get("realm_access") or {}).get("roles", ["viewer"])
    )
    if isinstance(role_raw, list):
        role_candidate = next(
            (r for r in role_raw if str(r).lower() in _ROLE_RANK),
            "viewer",
        )
    else:
        role_candidate = str(role_raw)
    role = role_candidate.lower() if role_candidate.lower() in _ROLE_RANK else "viewer"
    org = claims.get("organization_id") or claims.get("org_id") or claims.get("org")
    email = claims.get("email")
    return Principal(
        actor=sub,
        role=role,  # type: ignore[arg-type]
        authenticated=True,
        organization_id=str(org) if org else settings.default_organization_id,
        auth_method="jwt",
        email=str(email) if email else None,
    )


def verify_firebase_bearer(
    session: Session, token: str, settings: Settings
) -> Principal:
    claims = firebase_auth.decode_firebase_id_token(token, settings)
    sub = str(claims.get("sub") or "")
    email = str(claims.get("email") or "").strip()
    name = str(claims.get("name") or claims.get("email") or sub)
    if not sub:
        raise AppError(code="AUTH_INVALID", message="Firebase token missing sub", status_code=401)
    user = org_service.upsert_firebase_user(
        session,
        subject=sub,
        email=email or f"{sub}@users.firebase.local",
        name=name,
        settings=settings,
    )
    role = user.role if user.role in _ROLE_RANK else "viewer"
    return Principal(
        actor=user.email,
        role=role,  # type: ignore[arg-type]
        authenticated=True,
        organization_id=user.organization_id,
        auth_method="firebase",
        email=user.email,
        user_id=user.id,
    )


def resolve_principal(
    settings: Settings,
    authorization: str | None,
    *,
    session: Session | None = None,
) -> Principal:
    if not settings.auth_enabled:
        return Principal(
            actor="anonymous",
            role="admin",
            authenticated=False,
            organization_id=settings.default_organization_id,
            auth_method="none",
        )
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AppError(
            code="AUTH_REQUIRED",
            message="Authorization Bearer token required",
            status_code=401,
        )
    token = authorization.split(" ", 1)[1].strip()

    # Firebase ID tokens (when project configured)
    if settings.firebase_project_id and token.count(".") >= 2 and session is not None:
        try:
            return verify_firebase_bearer(session, token, settings)
        except AppError as exc:
            if exc.code not in {"AUTH_INVALID", "FIREBASE_NOT_CONFIGURED", "EMAIL_NOT_ALLOWLISTED"}:
                raise
            if exc.code == "EMAIL_NOT_ALLOWLISTED":
                raise
            # Fall through to IdP / demo tokens when Firebase decode fails
            if settings.idp_jwks_url:
                pass
            elif not _demo_tokens_allowed(settings):
                raise

    # Prefer generic IdP JWT when configured
    if settings.idp_jwks_url and settings.idp_issuer and settings.idp_audience:
        if token.count(".") >= 2:
            return verify_jwt_bearer(token, settings)

    # Demo static tokens — development/test only
    if _demo_tokens_allowed(settings):
        mapping = parse_token_map(settings.auth_tokens)
        if token in mapping:
            actor, role = mapping[token]
            return Principal(
                actor=actor,
                role=role,
                authenticated=True,
                organization_id=settings.default_organization_id,
                auth_method="demo_token",
                email=f"{actor}@demo.tradegraph.local",
            )

    raise AppError(code="AUTH_INVALID", message="Invalid token", status_code=401)


def get_principal(
    settings: SettingsDep,
    session: SessionDep,
    authorization: Annotated[str | None, Header()] = None,
) -> Principal:
    return resolve_principal(settings, authorization, session=session)


PrincipalDep = Annotated[Principal, Depends(get_principal)]


def require_role(minimum: Role):
    def _dep(principal: PrincipalDep) -> Principal:
        if _ROLE_RANK[principal.role] < _ROLE_RANK[minimum]:
            raise AppError(
                code="FORBIDDEN",
                message=f"Role {minimum} or higher required",
                status_code=403,
            )
        return principal

    return _dep


def resolve_organization_id(
    settings: Settings,
    principal: Principal,
    x_organization_id: str | None,
) -> str:
    """When auth is on, prefer token org; header may not escalate to another org."""
    if not settings.auth_enabled:
        return x_organization_id or settings.default_organization_id
    if principal.organization_id:
        if x_organization_id and x_organization_id != principal.organization_id:
            raise AppError(
                code="ORG_MISMATCH",
                message="X-Organization-Id does not match authenticated organization",
                status_code=403,
            )
        return principal.organization_id
    return x_organization_id or settings.default_organization_id


def write_audit(
    session: Session,
    *,
    principal: Principal,
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    detail: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> AuditLog:
    row = AuditLog(
        created_at=datetime.now(UTC),
        actor=principal.actor,
        role=principal.role,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        detail_json=dict(detail or {}),
        request_id=request_id,
    )
    session.add(row)
    session.flush()
    return row


def whoami(settings: Settings, principal: Principal) -> AuthWhoAmI:
    return AuthWhoAmI(
        authenticated=principal.authenticated,
        auth_enabled=settings.auth_enabled,
        actor=principal.actor,
        role=principal.role,
        email=principal.email,
        organization_id=principal.organization_id,
        auth_method=principal.auth_method,
    )


def list_audit(session: Session, *, limit: int = 50) -> list[AuditLogOut]:
    rows = session.scalars(
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    ).all()
    return [
        AuditLogOut(
            id=r.id,
            created_at=r.created_at,
            actor=r.actor,
            role=r.role,
            action=r.action,
            resource_type=r.resource_type,
            resource_id=r.resource_id,
            detail=dict(r.detail_json or {}),
            request_id=r.request_id,
        )
        for r in rows
    ]


def audit_from_request(
    session: Session,
    request: Request,
    principal: Principal,
    *,
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    write_audit(
        session,
        principal=principal,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        detail=detail,
        request_id=getattr(request.state, "request_id", None),
    )
