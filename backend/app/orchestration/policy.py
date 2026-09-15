"""Adaptive / baseline orchestration policy (Phase 3)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from backend.app.orchestration.complexity import ComplexityEstimate, IntentName

OrchestrationMode = Literal["adaptive", "direct_lookup", "fixed_multi", "always_llm"]

ToolName = Literal[
    "tariff_lookup",
    "landed_cost",
    "checklist_build",
    "fta_check",
    "graph_expand",
    "regulation_retrieve",
    "llm_explain",
]

INTENT_TO_TOOLS: dict[IntentName, tuple[ToolName, ...]] = {
    "tariff_lookup": ("tariff_lookup",),
    "landed_cost": ("landed_cost",),
    "checklist": ("checklist_build",),
    "fta_check": ("fta_check", "graph_expand"),
    "regulation_retrieve": ("regulation_retrieve",),
}

FIXED_MULTI_TOOLS: tuple[ToolName, ...] = (
    "tariff_lookup",
    "landed_cost",
    "checklist_build",
    "fta_check",
    "graph_expand",
    "regulation_retrieve",
)


@dataclass(frozen=True)
class PolicyDecision:
    mode: OrchestrationMode
    route: str
    tools: tuple[ToolName, ...]
    primary_intent: IntentName
    estimated_tokens_in: int
    estimated_tokens_out: int
    rationale: str


def _unique(tools: list[ToolName]) -> tuple[ToolName, ...]:
    seen: set[ToolName] = set()
    out: list[ToolName] = []
    for tool in tools:
        if tool not in seen:
            seen.add(tool)
            out.append(tool)
    return tuple(out)


def _token_proxy(
    mode: OrchestrationMode,
    tools: tuple[ToolName, ...],
    query_len: int,
) -> tuple[int, int]:
    base_in = max(20, query_len // 4)
    if mode == "always_llm":
        # Research proxy: always-LLM path burns tokens even when tools are deterministic.
        return base_in + 180 + 40 * len(tools), 120 + 35 * len(tools)
    if mode == "fixed_multi":
        return base_in + 10 * len(tools), 20 + 8 * len(tools)
    if "llm_explain" in tools:
        return base_in + 60, 80
    return base_in + 5 * len(tools), 12 + 6 * len(tools)


def decide_policy(
    *,
    mode: OrchestrationMode,
    estimate: ComplexityEstimate,
    query: str,
) -> PolicyDecision:
    primary = estimate.intents[0]

    if mode == "direct_lookup":
        tools: tuple[ToolName, ...] = ("tariff_lookup",)
        tin, tout = _token_proxy(mode, tools, len(query))
        return PolicyDecision(
            mode=mode,
            route="direct_lookup",
            tools=tools,
            primary_intent=primary,
            estimated_tokens_in=tin,
            estimated_tokens_out=tout,
            rationale="Baseline: always structured tariff lookup only.",
        )

    if mode == "fixed_multi":
        tools = FIXED_MULTI_TOOLS
        tin, tout = _token_proxy(mode, tools, len(query))
        return PolicyDecision(
            mode=mode,
            route="multi_agent",
            tools=tools,
            primary_intent=primary,
            estimated_tokens_in=tin,
            estimated_tokens_out=tout,
            rationale="Baseline: fixed multi-tool workflow for every query.",
        )

    if mode == "always_llm":
        tools = _unique([*FIXED_MULTI_TOOLS, "llm_explain"])
        tin, tout = _token_proxy(mode, tools, len(query))
        return PolicyDecision(
            mode=mode,
            route="always_llm",
            tools=tools,
            primary_intent=primary,
            estimated_tokens_in=tin,
            estimated_tokens_out=tout,
            rationale=(
                "Baseline: always-LLM proxy with full tool fan-out "
                "(numbers still deterministic)."
            ),
        )

    # adaptive
    tools_list: list[ToolName] = []
    for intent in estimate.intents:
        tools_list.extend(INTENT_TO_TOOLS[intent])
    # Complexity gate: only escalate to retrieval/graph extras when needed
    if estimate.label == "simple":
        tools_list = list(INTENT_TO_TOOLS[primary])
    elif estimate.label == "moderate" and len(estimate.intents) > 1:
        tools_list = []
        for intent in estimate.intents[:2]:
            tools_list.extend(INTENT_TO_TOOLS[intent])
    tools = _unique(tools_list)

    if tools == ("tariff_lookup",):
        route = "direct_lookup"
    elif len(tools) == 1 and tools[0] in {"landed_cost", "checklist_build"}:
        route = "single_tool"
    elif "fta_check" in tools or "regulation_retrieve" in tools:
        route = "graph_vector"
    else:
        route = "multi_agent"

    tin, tout = _token_proxy(mode, tools, len(query))
    return PolicyDecision(
        mode=mode,
        route=route,
        tools=tools,
        primary_intent=primary,
        estimated_tokens_in=tin,
        estimated_tokens_out=tout,
        rationale=(
            f"Adaptive: complexity={estimate.label}({estimate.score}) "
            f"intents={list(estimate.intents)}"
        ),
    )
