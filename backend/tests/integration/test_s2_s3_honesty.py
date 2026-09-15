"""PRODUCT_USABILITY_PLAN S2/S3: coverage miss + Ask/FTA honesty."""

from __future__ import annotations

from backend.tests.helpers.db import make_client


def test_calculate_coverage_miss_for_unknown_hs() -> None:
    client = make_client()
    response = client.post(
        "/api/v1/calculate/landed-cost",
        json={
            "hs_code": "9999.99",
            "origin": "BD",
            "destination": "IN",
            "as_of": "2026-06-01",
            "invoice_value": "1000",
            "currency": "USD",
        },
    )
    assert response.status_code == 404
    err = response.json()["error"]
    assert err["code"] == "COVERAGE_MISS"
    details = err["details"]
    assert details["hs_code"] == "9999.99"
    assert details["possible_reasons"]
    assert details["next_actions"]
    assert "dataset_coverage" in details


def test_fta_unsupported_corridor_is_coverage_miss() -> None:
    client = make_client()
    response = client.post(
        "/api/v1/fta/check",
        json={
            "hs_code": "6109.10",
            "origin": "CN",
            "destination": "US",
            "as_of": "2026-06-01",
        },
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "COVERAGE_MISS"


def test_fta_status_is_honest_not_bare_eligible() -> None:
    client = make_client()
    body = client.post(
        "/api/v1/fta/check",
        json={
            "hs_code": "6109.10",
            "origin": "BD",
            "destination": "IN",
            "as_of": "2026-06-01",
        },
    ).json()
    assert body["status"] in {
        "potentially_eligible",
        "needs_evidence",
        "eligible",
        "not_covered",
    }
    assert body["status"] != "conditional"
    assert body["reasons"]


def test_ask_response_includes_decision_contract() -> None:
    client = make_client()
    body = client.post(
        "/api/v1/ask",
        json={
            "query": "What is the import duty for HS 6109.10 from Bangladesh to India?",
            "as_of": "2026-06-01",
            "orchestration_mode": "adaptive",
        },
    ).json()
    assert body["decision"] in {
        "confirmed",
        "likely",
        "estimated",
        "needs_information",
        "not_supported",
        "no_approved_source",
    }
    assert isinstance(body["assumptions"], list)
    assert body["next_action"]
    assert body["source_status"] in {"illustrative", "demo_verified", "source_verified", "none"}


def test_ask_unknown_hs_reports_no_approved_source() -> None:
    client = make_client()
    body = client.post(
        "/api/v1/ask",
        json={
            "query": "What is the duty for HS 9999.99 BD to IN?",
            "as_of": "2026-06-01",
            "hs_code": "9999.99",
            "orchestration_mode": "direct_lookup",
        },
    ).json()
    assert body["decision"] == "no_approved_source"
    assert "cannot verify" in body["answer"].lower()
    assert body["result"].get("coverage_miss")


def test_landed_cost_labeled_estimate() -> None:
    client = make_client()
    body = client.post(
        "/api/v1/calculate/landed-cost",
        json={
            "hs_code": "6109.10",
            "origin": "BD",
            "destination": "IN",
            "as_of": "2026-06-01",
            "invoice_value": "1000",
            "currency": "USD",
            "incoterm": "CIF",
        },
    ).json()
    assert body["calculation_mode"] == "estimate"
    assert "Estimated" in body["title"]
    assert body["assumptions"]
