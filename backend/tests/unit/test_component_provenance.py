"""Unit tests for per-component duty provenance merge rules."""

from __future__ import annotations

from backend.app.services.component_provenance import (
    applicable_stack_signature,
    flatten_rates,
    merge_duty_components,
    provenance_block,
)


def test_igst_partial_merge_does_not_zero_bcd() -> None:
    existing = {
        "bcd_pct": 20.0,
        "sws_pct_of_bcd": 10.0,
        "igst_pct": 18.0,
        "_provenance": {
            "bcd_pct": provenance_block(
                value=20.0,
                source_key="curated_bcd_ch61_bd_in",
                data_quality="curated_official_backed",
            ),
            "sws_pct_of_bcd": provenance_block(
                value=10.0,
                source_key="curated_sws_finance_act",
                data_quality="curated_official_backed",
            ),
            "igst_pct": provenance_block(
                value=18.0, data_quality="illustrative"
            ),
        },
    }
    incoming = {
        "igst_pct": 5.0,
        "_partial_components": ["igst_pct"],
        "_provenance": {
            "igst_pct": provenance_block(
                value=5.0,
                source_key="live_igst_notif_9_2025",
                source_document_id="src_live_igst",
                data_quality="source_verified",
            ),
            # Malicious / mistaken zero BCD must be ignored for IGST-only packs
            "bcd_pct": provenance_block(value=0.0, data_quality="source_verified"),
        },
    }
    merged = merge_duty_components(existing, incoming, incoming_source_document_id="src_live_igst")
    assert merged["bcd_pct"] == 20.0
    assert merged["sws_pct_of_bcd"] == 10.0
    assert merged["igst_pct"] == 5.0
    assert merged["_provenance"]["bcd_pct"]["data_quality"] == "curated_official_backed"
    assert merged["_provenance"]["igst_pct"]["data_quality"] == "source_verified"
    assert merged["_provenance"]["igst_pct"]["source_document_id"] == "src_live_igst"


def test_sws_missing_when_bcd_missing() -> None:
    merged = merge_duty_components(
        None,
        {
            "igst_pct": 5.0,
            "_partial_components": ["igst_pct"],
            "_provenance": {
                "igst_pct": provenance_block(
                    value=5.0, data_quality="source_verified"
                )
            },
        },
    )
    assert "bcd_pct" not in merged or merged.get("bcd_pct") is None
    assert merged["_provenance"]["bcd_pct"]["data_quality"] == "missing"
    assert merged["_provenance"]["sws_pct_of_bcd"]["data_quality"] == "missing"
    rates = flatten_rates(merged)
    assert rates["bcd_pct"] == 0.0
    assert rates["sws_pct_of_bcd"] == 0.0


def test_stack_signature_ignores_provenance_metadata() -> None:
    a = {
        "bcd_pct": 20,
        "sws_pct_of_bcd": 10,
        "igst_pct": 5,
        "_provenance": {
            "igst_pct": provenance_block(
                value=5, notes="v1 archive", data_quality="source_verified"
            )
        },
    }
    b = {
        "bcd_pct": 20,
        "sws_pct_of_bcd": 10,
        "igst_pct": 5,
        "_provenance": {
            "igst_pct": provenance_block(
                value=5, notes="v2 archive byte churn", data_quality="source_verified"
            )
        },
    }
    c = {
        "bcd_pct": 20,
        "sws_pct_of_bcd": 10,
        "igst_pct": 12,
        "_provenance": {
            "igst_pct": provenance_block(value=12, data_quality="source_verified")
        },
    }
    assert applicable_stack_signature(a) == applicable_stack_signature(b)
    assert applicable_stack_signature(a) != applicable_stack_signature(c)
