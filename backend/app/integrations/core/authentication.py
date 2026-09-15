"""Auth helpers for providers that require credentials (stubs for IF-1)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuthContext:
    """Resolved credentials for a source. Never store secrets in seed YAML."""

    scheme: str  # none | bearer | basic | api_key
    token: str | None = None
    api_key: str | None = None
    username: str | None = None
    password: str | None = None


def no_auth() -> AuthContext:
    return AuthContext(scheme="none")
