"""Allowlist gating for official CBIC hosts (SSRF-safe)."""

from __future__ import annotations

import pytest

from backend.app.core.errors import AppError
from backend.app.core.config import Settings
from backend.app.services.source_adapters import host_allowed, validate_url_for_fetch
from backend.tests.helpers.db import make_client


def test_courier_cbic_allowed_with_default_settings_allowlist() -> None:
    settings = Settings.model_validate(
        {
            "environment": "test",
            "app_name": "Test",
            "database_url": "sqlite:///:memory:",
        }
    )
    assert "courier.cbic.gov.in" in settings.http_source_allowlist
    url = "https://courier.cbic.gov.in/advisory/2025/NOTIFICATION.pdf"
    assert host_allowed(url, settings.http_source_allowlist) is True
    validate_url_for_fetch(url, allowlist=settings.http_source_allowlist, require_https=True)


def test_courier_cbic_rejected_when_not_on_allowlist() -> None:
    allow = "localhost,127.0.0.1,example.invalid"
    url = "https://courier.cbic.gov.in/notification.jsp"
    assert host_allowed(url, allow) is False
    with pytest.raises(AppError) as exc:
        validate_url_for_fetch(url, allowlist=allow, require_https=True)
    assert exc.value.code == "SOURCE_HTTP_HOST_NOT_ALLOWLISTED"


def test_feed_status_live_enabled_when_configured() -> None:
    client = make_client(
        live_feed_enabled=True,
        http_source_allowlist="localhost,127.0.0.1,courier.cbic.gov.in",
    )
    feed = client.get("/api/v1/source-connections/feed-status").json()
    assert feed["live_feed_enabled_setting"] is True
    rows = client.get("/api/v1/source-connections").json()
    verified = next(r for r in rows if r["key"] == "cbic_ch61_igst_notif_9_2025")
    assert "courier.cbic.gov.in" in (verified.get("source_url") or "")
    assert verified.get("document_url")
