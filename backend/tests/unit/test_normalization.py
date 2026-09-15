"""IF-4 normalization helpers."""

from __future__ import annotations

from backend.app.ingestion.normalization import (
    normalize_hs_code,
    normalize_percent,
    normalize_tariff_record,
)


def test_normalize_hs_variants() -> None:
    assert normalize_hs_code("610910") == "6109.10"
    assert normalize_hs_code("6109.10") == "6109.10"
    assert normalize_hs_code("6109 10") == "6109.10"


def test_normalize_percent_strips_suffix() -> None:
    assert normalize_percent("10%") == normalize_percent(10)


def test_normalize_tariff_icegate_shaped_record() -> None:
    rule, errors = normalize_tariff_record(
        {
            "tariffHead": "610910",
            "basicDuty": "10%",
            "validFrom": "01/07/2026",
            "origin_country": "BD",
            "destination_country": "IN",
        },
        source_document_id="doc_test",
    )
    assert errors == []
    assert rule is not None
    assert rule.hs_code == "6109.10"
    assert float(rule.duty_rate) == 10.0
    assert rule.effective_from.isoformat() == "2026-07-01"
