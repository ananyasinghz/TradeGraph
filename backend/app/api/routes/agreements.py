"""Agreements and FTA check routes."""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.api.auth_deps import ViewerDep
from backend.app.api.dependencies import SessionDep
from backend.app.domain.trade import FtaCheckRequest, FtaCheckResult, TradeAgreementOut
from backend.app.services import fta_service, graph_service

router = APIRouter(tags=["agreements"])


@router.get("/agreements", response_model=list[TradeAgreementOut])
def list_agreements(session: SessionDep, _principal: ViewerDep) -> list[TradeAgreementOut]:
    return fta_service.list_agreements(session)


@router.post("/fta/check", response_model=FtaCheckResult)
def fta_check(
    payload: FtaCheckRequest, session: SessionDep, _principal: ViewerDep
) -> FtaCheckResult:
    return fta_service.check_fta(
        session,
        hs_code=payload.hs_code,
        origin=payload.origin,
        destination=payload.destination,
        as_of=payload.as_of,
        agreement_id=payload.agreement_id,
        shipment_id=payload.shipment_id,
        conditions=payload.conditions,
    )


@router.get("/graph/summary")
def graph_summary(session: SessionDep, _principal: ViewerDep) -> dict[str, object]:
    graph = graph_service.build_trade_graph(session)
    return graph_service.graph_summary(graph)
