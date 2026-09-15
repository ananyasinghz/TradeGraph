"""Benchmark evaluation for adaptive vs baseline orchestration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from backend.app.domain.trade import (
    BenchmarkCaseResult,
    BenchmarkModeSummary,
    BenchmarkRunResult,
)
from backend.app.orchestration.ask_graph import run_ask
from backend.app.orchestration.policy import OrchestrationMode

DEFAULT_BENCHMARK = (
    Path(__file__).resolve().parents[3] / "config" / "evaluation" / "benchmark.v1.json"
)


@dataclass(frozen=True)
class CaseSpec:
    id: str
    query: str
    as_of: date
    expected_primary_intent: str
    expected_rate: float | None
    expected_min_evidence_score: float
    expected_tools_contains: tuple[str, ...]


def load_benchmark(path: Path | None = None) -> list[CaseSpec]:
    payload = json.loads((path or DEFAULT_BENCHMARK).read_text(encoding="utf-8"))
    cases: list[CaseSpec] = []
    for item in payload["cases"]:
        cases.append(
            CaseSpec(
                id=str(item["id"]),
                query=str(item["query"]),
                as_of=date.fromisoformat(str(item["as_of"])),
                expected_primary_intent=str(item["expected_primary_intent"]),
                expected_rate=(
                    float(item["expected_rate"]) if item.get("expected_rate") is not None else None
                ),
                expected_min_evidence_score=float(item.get("expected_min_evidence_score", 0.4)),
                expected_tools_contains=tuple(item.get("expected_tools_contains") or []),
            )
        )
    return cases


def _extract_rate(result: dict[str, Any]) -> float | None:
    tariffs = result.get("tariffs")
    if isinstance(tariffs, list) and tariffs:
        rate = tariffs[0].get("rate")
        if rate is not None:
            return float(rate)
    landed = result.get("landed_cost")
    if isinstance(landed, dict) and landed.get("bcd_rate_pct") is not None:
        return float(landed["bcd_rate_pct"])
    fta = result.get("fta")
    if isinstance(fta, dict) and fta.get("mfn_rate_pct") is not None:
        return float(fta["mfn_rate_pct"])
    for item in result.get("evidence") or []:
        if isinstance(item, dict) and item.get("kind") == "tariff_rate" and "rate" in item:
            return float(item["rate"])
    return None


def score_case(case: CaseSpec, response: Any) -> BenchmarkCaseResult:
    correct = True
    notes: list[str] = []

    if response.orchestration_mode == "direct_lookup":
        # Lookup baseline may miss FTA/checklist tools; score on rate when expected.
        pass
    elif case.expected_tools_contains:
        missing = [t for t in case.expected_tools_contains if t not in response.tools_invoked]
        if missing and response.orchestration_mode == "adaptive":
            correct = False
            notes.append(f"missing_tools={missing}")

    if case.expected_rate is not None:
        got = _extract_rate(response.result)
        # Also check evidence rate
        if got is None:
            for item in response.evidence:
                if item.get("kind") == "tariff_rate" and "rate" in item:
                    got = float(item["rate"])
                    break
        if got is None or abs(got - case.expected_rate) > 1e-6:
            # For FTA cases, preferential may be primary narrative but MFN still expected
            lookup_skip = (
                response.orchestration_mode == "direct_lookup"
                and case.expected_primary_intent != "tariff_lookup"
            )
            if lookup_skip:
                notes.append("direct_lookup_skipped_specialized_intent")
            else:
                correct = False
                notes.append(f"rate_got={got}")

    if response.evidence_score < case.expected_min_evidence_score:
        lookup_skip = (
            response.orchestration_mode == "direct_lookup"
            and case.expected_primary_intent != "tariff_lookup"
        )
        if lookup_skip:
            notes.append("low_evidence_tolerated_for_lookup_baseline")
        else:
            correct = False
            notes.append(f"evidence_score={response.evidence_score}")

    return BenchmarkCaseResult(
        case_id=case.id,
        mode=response.orchestration_mode,
        correct=correct,
        route=response.route,
        tools_invoked=list(response.tools_invoked),
        tool_count=response.tool_count,
        latency_ms=response.latency_ms,
        tokens_in=response.tokens_in,
        tokens_out=response.tokens_out,
        evidence_score=response.evidence_score,
        complexity_score=response.complexity_score,
        notes="; ".join(notes),
    )


def run_benchmark(
    session: Session,
    *,
    modes: list[OrchestrationMode] | None = None,
    path: Path | None = None,
) -> BenchmarkRunResult:
    cases = load_benchmark(path)
    selected = modes or ["adaptive", "direct_lookup", "fixed_multi", "always_llm"]
    case_results: list[BenchmarkCaseResult] = []

    for mode in selected:
        for case in cases:
            response = run_ask(
                session,
                query=case.query,
                as_of=case.as_of,
                orchestration_mode=mode,
            )
            case_results.append(score_case(case, response))

    summaries: list[BenchmarkModeSummary] = []
    for mode in selected:
        subset = [r for r in case_results if r.mode == mode]
        n = max(len(subset), 1)
        summaries.append(
            BenchmarkModeSummary(
                mode=mode,
                cases=len(subset),
                accuracy=sum(1 for r in subset if r.correct) / n,
                avg_latency_ms=sum(r.latency_ms for r in subset) / n,
                avg_tokens_in=sum(r.tokens_in for r in subset) / n,
                avg_tokens_out=sum(r.tokens_out for r in subset) / n,
                avg_tool_count=sum(r.tool_count for r in subset) / n,
                avg_evidence_score=sum(r.evidence_score for r in subset) / n,
            )
        )

    return BenchmarkRunResult(summaries=summaries, cases=case_results)
