"""Firebase ID-token verification via Google securetoken JWKS."""

from __future__ import annotations

from functools import lru_cache

import jwt
from jwt import PyJWKClient

from backend.app.core.config import Settings
from backend.app.core.errors import AppError

_FIREBASE_JWKS_URL = (
    "https://www.googleapis.com/service_accounts/v1/jwk/"
    "securetoken@system.gserviceaccount.com"
)


@lru_cache(maxsize=2)
def _firebase_jwks_client() -> PyJWKClient:
    return PyJWKClient(_FIREBASE_JWKS_URL, cache_keys=True, lifespan=300)


def decode_firebase_id_token(token: str, settings: Settings) -> dict[str, object]:
    project_id = (settings.firebase_project_id or "").strip()
    if not project_id:
        raise AppError(
            code="FIREBASE_NOT_CONFIGURED",
            message="TRADE_FIREBASE_PROJECT_ID is required to verify Firebase tokens",
            status_code=501,
        )
    issuer = f"https://securetoken.google.com/{project_id}"
    try:
        client = _firebase_jwks_client()
        signing_key = client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=project_id,
            issuer=issuer,
            options={"require": ["exp", "iat", "sub", "auth_time"]},
        )
    except jwt.PyJWTError as exc:
        raise AppError(
            code="AUTH_INVALID",
            message=f"Invalid Firebase ID token: {exc}",
            status_code=401,
        ) from exc
    except OSError as exc:
        raise AppError(
            code="JWKS_UNAVAILABLE",
            message=f"Firebase JWKS fetch failed: {exc}",
            status_code=503,
        ) from exc
    return dict(claims)
