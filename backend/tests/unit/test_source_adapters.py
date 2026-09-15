"""Unit tests for Phase C source adapters."""

from __future__ import annotations

import pytest

from backend.app.core.errors import AppError
from backend.app.services import source_adapters


def test_curated_json_mirror_reads_local_archive() -> None:
    payload = source_adapters.resolve_payload(
        adapter="curated_json_mirror",
        fetch_mode="curated_mirror",
        local_path="config/trade/fixtures/cbic/cbic_notification_2026_q3.json",
        source_url=None,
    )
    assert payload.content_type == "application/json"
    assert b"source_key" in payload.content or b"tariff" in payload.content.lower()
    assert payload.resolved_from.endswith(".json")


def test_local_archive_missing_raises() -> None:
    with pytest.raises(AppError) as exc:
        source_adapters.resolve_payload(
            adapter="local_archive",
            fetch_mode="local_archive",
            local_path="config/trade/sources/does_not_exist.json",
            source_url=None,
        )
    assert exc.value.code == "SOURCE_LOCAL_MISSING"


def test_unknown_adapter_raises() -> None:
    with pytest.raises(AppError) as exc:
        source_adapters.resolve_payload(
            adapter="mystery",
            fetch_mode="mystery",
            local_path=None,
            source_url=None,
        )
    assert exc.value.code == "SOURCE_ADAPTER_UNKNOWN"
