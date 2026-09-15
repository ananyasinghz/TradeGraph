"""OIDC / IdP helpers — JWT verification lives in auth_service (IF-12e)."""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.config import Settings, get_settings
from backend.app.services import auth_service


@dataclass(frozen=True)
class IdpClaims:
    subject: str
    email: str | None = None
    name: str | None = None


def parse_bearer_subject(authorization: str | None, settings: Settings | None = None) -> str | None:
    """Resolve actor/subject from Authorization when auth or IdP is configured."""
    settings = settings or get_settings()
    if not authorization:
        return None
    try:
        principal = auth_service.resolve_principal(settings, authorization)
    except Exception:
        return None
    if not principal.authenticated:
        return None
    return principal.actor
