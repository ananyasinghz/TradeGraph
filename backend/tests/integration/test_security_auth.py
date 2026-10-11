"""Firebase auth + portal RBAC / hardening integration tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from io import BytesIO
from unittest.mock import patch

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from backend.app.services import firebase_auth
from backend.tests.helpers.db import make_client, make_settings


def _rsa_keypair():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return key, private_pem


def test_firebase_claim_verify_mocked() -> None:
    settings = make_settings(
        auth_enabled=True,
        firebase_project_id="tradegraph-test",
        bootstrap_admin_emails="admin@example.com",
    )
    private_key, _ = _rsa_keypair()
    now = datetime.now(UTC)
    claims = {
        "sub": "firebase-uid-1",
        "email": "admin@example.com",
        "name": "Admin User",
        "aud": "tradegraph-test",
        "iss": "https://securetoken.google.com/tradegraph-test",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
        "auth_time": int(now.timestamp()),
    }
    token = jwt.encode(claims, private_key, algorithm="RS256")

    class _Key:
        key = private_key.public_key()

    class _Client:
        def get_signing_key_from_jwt(self, _token: str) -> _Key:
            return _Key()

    with patch.object(firebase_auth, "_firebase_jwks_client", return_value=_Client()):
        decoded = firebase_auth.decode_firebase_id_token(token, settings)
    assert decoded["sub"] == "firebase-uid-1"
    assert decoded["email"] == "admin@example.com"


def test_route_matrix_requires_auth_and_roles() -> None:
    client = make_client(auth_enabled=True)

    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/api/v1/tariffs").status_code == 401
    assert client.get("/api/v1/shipments").status_code == 401
    assert client.post("/api/v1/ask", json={"query": "duty?"}).status_code == 401

    viewer = {"Authorization": "Bearer demo-viewer"}
    assert client.get("/api/v1/tariffs", headers=viewer).status_code == 200
    assert client.get("/api/v1/shipments", headers=viewer).status_code == 403
    assert client.post("/api/v1/eval/run", headers=viewer).status_code == 403
    assert client.get("/api/v1/auth/audit", headers=viewer).status_code == 403

    operator = {"Authorization": "Bearer demo-operator"}
    assert client.get("/api/v1/shipments", headers=operator).status_code == 200
    assert (
        client.post(
            "/api/v1/ingest/batches/missing/approve",
            headers=operator,
        ).status_code
        == 403
    )

    admin = {"Authorization": "Bearer demo-admin"}
    assert client.get("/api/v1/auth/audit", headers=admin).status_code == 200


def test_org_isolation_on_shipments() -> None:
    client = make_client(auth_enabled=True, default_organization_id="org_demo")
    headers = {"Authorization": "Bearer demo-operator"}
    created = client.post(
        "/api/v1/shipments",
        headers=headers,
        json={
            "title": "Org A case",
            "product_text": "cotton t-shirts",
            "origin": "BD",
            "destination": "IN",
            "invoice_value": "1000",
            "currency": "USD",
            "as_of_date": "2026-01-15",
        },
    )
    assert created.status_code == 200
    ship_id = created.json()["id"]

    # Force shipment into another org via DB, then ensure get is forbidden.
    from backend.app.data.models import Organization, Shipment

    session_factory = client.app.state.session_factory
    with session_factory() as session:
        other = Organization(
            id="org_other",
            name="Other Org",
            created_at=datetime.now(UTC),
        )
        session.merge(other)
        row = session.get(Shipment, ship_id)
        assert row is not None
        row.organization_id = "org_other"
        session.commit()

    denied = client.get(f"/api/v1/shipments/{ship_id}", headers=headers)
    assert denied.status_code == 403


def test_upload_rejects_disallowed_extension() -> None:
    client = make_client(auth_enabled=True)
    headers = {"Authorization": "Bearer demo-operator"}
    created = client.post(
        "/api/v1/shipments",
        headers=headers,
        json={
            "title": "Upload case",
            "product_text": "cotton t-shirts",
            "origin": "BD",
            "destination": "IN",
            "invoice_value": "1000",
            "currency": "USD",
            "as_of_date": "2026-01-15",
        },
    )
    assert created.status_code == 200
    ship_id = created.json()["id"]
    bad = client.post(
        f"/api/v1/shipments/{ship_id}/uploads",
        headers=headers,
        data={"doc_code": "COO"},
        files={"file": ("malware.exe", BytesIO(b"MZ"), "application/octet-stream")},
    )
    assert bad.status_code in {400, 415, 422}


def test_security_headers_and_cors_smoke() -> None:
    client = make_client(cors_origins="http://localhost:5173")
    resp = client.get(
        "/api/v1/health",
        headers={"Origin": "http://localhost:5173"},
    )
    assert resp.status_code == 200
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("x-frame-options") == "DENY"
    assert "strict-origin-when-cross-origin" in (
        resp.headers.get("referrer-policy") or ""
    )
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_production_rejects_demo_tokens() -> None:
    client = make_client(auth_enabled=True, environment="production")
    denied = client.get(
        "/api/v1/auth/whoami",
        headers={"Authorization": "Bearer demo-admin"},
    )
    assert denied.status_code == 401
