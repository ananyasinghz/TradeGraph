"""Live HTTP adapter allowlist + fetch honesty."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.core.errors import AppError
from backend.app.services import source_adapters
from backend.app.services.source_connection_service import ensure_default_connections
from backend.tests.helpers.db import make_client, make_seeded_engine


def test_host_allowlist() -> None:
    assert source_adapters.host_allowed("http://127.0.0.1:9/x", "localhost,127.0.0.1")
    assert not source_adapters.host_allowed("https://evil.example/x", "localhost")


def test_http_fetch_rejects_non_allowlisted() -> None:
    with pytest.raises(AppError) as exc:
        source_adapters.fetch_http_get(
            source_url="https://not-allowed.example/pack.json",
            allowlist="localhost,127.0.0.1",
        )
    assert exc.value.code == "SOURCE_HTTP_HOST_NOT_ALLOWLISTED"


def test_default_connections_include_pdf_sources() -> None:
    _engine, factory = make_seeded_engine()
    with factory() as session:
        ensure_default_connections(session)
        session.commit()
        from sqlalchemy import select

        from backend.app.data.models import SourceConnection

        keys = set(session.scalars(select(SourceConnection.key)).all())
    assert "itc_hs_2022_pdf" in keys
    assert "hs_code_mapping_pdf" in keys
    assert "cbic_notification_2026_q3" in keys
    assert Path("config/trade/source/ITC-HS_2022.pdf").is_file()


def test_sources_list_api_includes_pdfs() -> None:
    client = make_client()
    resp = client.get("/api/v1/source-connections")
    assert resp.status_code == 200, resp.text
    keys = {r["key"] for r in resp.json()}
    assert "itc_hs_2022_pdf" in keys
    assert "hs_code_mapping_pdf" in keys
