"""Duty structure + exemption Sl. No. APIs (ICEGATE-style panel)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Query

from backend.app.api.auth_deps import ViewerDep
from backend.app.api.dependencies import SessionDep
from backend.app.domain.trade import DutyStructureOut, ExemptionRuleOut, TariffCoverageOut
from backend.app.services import cost_service, exemption_service, tariff_coverage_service

router = APIRouter(tags=["duty"])


@router.get("/duty/structure", response_model=DutyStructureOut)
def get_duty_structure(
    session: SessionDep,
    _principal: ViewerDep,
    hs: str = Query(..., min_length=4, max_length=16),
    origin: str = Query(..., min_length=2, max_length=2),
    destination: str = Query(default="IN", min_length=2, max_length=2),
    as_of: date = Query(...),
    assessable_value: Decimal = Query(default=Decimal("100000"), gt=0),
    currency: str = Query(default="INR", min_length=3, max_length=3),
    selected_exemption_id: str | None = Query(default=None),
    shipment_id: str | None = Query(default=None),
) -> DutyStructureOut:
    """Full duty stack + applicable notification Sl. Nos. for a confirmed HS."""
    return cost_service.build_duty_structure(
        session,
        hs_code=hs,
        origin=origin,
        destination=destination,
        as_of=as_of,
        assessable_value=assessable_value,
        currency=currency,
        selected_exemption_id=selected_exemption_id,
        shipment_id=shipment_id,
    )


@router.get("/duty/exemptions", response_model=list[ExemptionRuleOut])
def list_duty_exemptions(
    session: SessionDep,
    _principal: ViewerDep,
    hs: str = Query(..., min_length=4, max_length=16),
    origin: str = Query(..., min_length=2, max_length=2),
    destination: str = Query(default="IN", min_length=2, max_length=2),
    as_of: date = Query(...),
    shipment_id: str | None = Query(default=None),
) -> list[ExemptionRuleOut]:
    return exemption_service.list_applicable_exemptions(
        session,
        hs_code=hs,
        origin=origin,
        destination=destination,
        as_of=as_of,
        shipment_id=shipment_id,
    )


@router.get("/duty/coverage", response_model=TariffCoverageOut)
def get_duty_coverage(
    session: SessionDep,
    _principal: ViewerDep,
    origin: str = Query(default="BD", min_length=2, max_length=2),
    destination: str = Query(default="IN", min_length=2, max_length=2),
) -> TariffCoverageOut:
    """Per-chapter inventory of classification / BCD / IGST / exemptions / preferential."""
    return tariff_coverage_service.chapter_coverage(
        session, origin=origin, destination=destination
    )
