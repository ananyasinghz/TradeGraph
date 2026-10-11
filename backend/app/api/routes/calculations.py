"""Calculation snapshot APIs (IF-11d)."""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.api.auth_deps import ViewerDep
from backend.app.api.dependencies import SessionDep
from backend.app.domain.trade import CalculationSnapshotOut, SnapshotDiffOut
from backend.app.services import cost_service

router = APIRouter(tags=["calculations"])


@router.get("/calculations/{calculation_id}", response_model=CalculationSnapshotOut)
def get_calculation(
    calculation_id: str, session: SessionDep, _principal: ViewerDep
) -> CalculationSnapshotOut:
    return cost_service.get_snapshot(session, calculation_id)


@router.get("/calculations/{left_id}/diff/{right_id}", response_model=SnapshotDiffOut)
def diff_calculations(
    left_id: str, right_id: str, session: SessionDep, _principal: ViewerDep
) -> SnapshotDiffOut:
    return cost_service.diff_snapshots(session, left_id, right_id)
