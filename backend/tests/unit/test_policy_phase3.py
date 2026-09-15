"""Unit tests for complexity + adaptive policy."""

from __future__ import annotations

from backend.app.orchestration.complexity import estimate_complexity
from backend.app.orchestration.policy import decide_policy


def test_simple_tariff_query_is_simple() -> None:
    estimate = estimate_complexity(
        "What is the import duty for HS 6109.10 from Bangladesh to India?"
    )
    assert estimate.label == "simple"
    assert estimate.intents[0] == "tariff_lookup"
    decision = decide_policy(mode="adaptive", estimate=estimate, query="duty HS 6109.10")
    assert decision.tools == ("tariff_lookup",)
    assert decision.route == "direct_lookup"


def test_fixed_multi_always_fans_out() -> None:
    estimate = estimate_complexity("What is the import duty for HS 6109.10?")
    decision = decide_policy(mode="fixed_multi", estimate=estimate, query="duty")
    assert len(decision.tools) >= 5
    assert decision.route == "multi_agent"
