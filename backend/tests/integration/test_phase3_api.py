"""Phase 3 adaptive orchestration and benchmark tests."""

from __future__ import annotations

from backend.tests.helpers.db import make_client


def test_adaptive_uses_fewer_tools_than_fixed_on_simple_tariff() -> None:
    client = make_client(ollama_enabled=False)
    query = {
        "query": "What is the import duty for HS 6109.10 from Bangladesh to India?",
        "as_of": "2026-06-01",
    }
    adaptive = client.post(
        "/api/v1/ask",
        json={**query, "orchestration_mode": "adaptive"},
    ).json()
    fixed = client.post(
        "/api/v1/ask",
        json={**query, "orchestration_mode": "fixed_multi"},
    ).json()
    assert adaptive["tool_count"] < fixed["tool_count"]
    assert adaptive["tokens_in"] + adaptive["tokens_out"] < fixed["tokens_in"] + fixed["tokens_out"]
    assert float(adaptive["result"]["tariffs"][0]["rate"]) == 20.0
    assert float(fixed["result"]["tariffs"][0]["rate"]) == 20.0


def test_always_llm_uses_more_tokens_than_adaptive() -> None:
    client = make_client(ollama_enabled=False)
    query = {
        "query": "What is the import duty for HS 6109.10 from Bangladesh to India?",
        "as_of": "2026-06-01",
    }
    adaptive = client.post(
        "/api/v1/ask",
        json={**query, "orchestration_mode": "adaptive"},
    ).json()
    always = client.post(
        "/api/v1/ask",
        json={**query, "orchestration_mode": "always_llm"},
    ).json()
    assert always["tokens_in"] > adaptive["tokens_in"]
    assert always["route"] == "always_llm"


def test_benchmark_run_compares_modes() -> None:
    client = make_client()
    response = client.post(
        "/api/v1/eval/run",
        params=[
            ("modes", "adaptive"),
            ("modes", "fixed_multi"),
            ("modes", "direct_lookup"),
        ],
    )
    assert response.status_code == 200
    body = response.json()
    modes = {row["mode"]: row for row in body["summaries"]}
    assert "adaptive" in modes
    assert "fixed_multi" in modes
    assert modes["adaptive"]["avg_tool_count"] < modes["fixed_multi"]["avg_tool_count"]
    assert modes["adaptive"]["accuracy"] >= 0.5
