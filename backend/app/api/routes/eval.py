"""Evaluation / benchmark API."""

from __future__ import annotations

from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, Query

from backend.app.api.auth_deps import AdminDep
from backend.app.api.dependencies import SessionDep
from backend.app.domain.trade import BenchmarkRunResult
from backend.app.evaluation.benchmark import run_benchmark
from backend.app.orchestration.policy import OrchestrationMode
from backend.app.services.hs_eval_service import evaluate_hs_classify

router = APIRouter(prefix="/eval", tags=["evaluation"])


@router.post("/run", response_model=BenchmarkRunResult)
def eval_run(
    session: SessionDep,
    _principal: AdminDep,
    modes: Annotated[
        list[Literal["adaptive", "direct_lookup", "fixed_multi", "always_llm"]] | None,
        Query(),
    ] = None,
) -> BenchmarkRunResult:
    selected: list[OrchestrationMode] | None = cast(
        list[OrchestrationMode] | None, modes
    )
    return run_benchmark(session, modes=selected)


@router.post("/hs-classify")
def eval_hs_classify(session: SessionDep, _principal: AdminDep) -> dict[str, Any]:
    return evaluate_hs_classify(session)
