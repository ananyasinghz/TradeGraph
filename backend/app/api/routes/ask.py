"""Ask co-pilot route (LangGraph + adaptive/baseline modes + focus actions)."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Request

from backend.app.api.auth_deps import OperatorDep
from backend.app.api.dependencies import SessionDep, SettingsDep
from backend.app.core.errors import AppError
from backend.app.data.models import Shipment
from backend.app.domain.trade import AskRequest, AskResponse
from backend.app.orchestration.ask_graph import run_ask
from backend.app.orchestration.focus import build_focus_query
from backend.app.orchestration.policy import OrchestrationMode
from backend.app.services.auth_service import audit_from_request

router = APIRouter(tags=["ask"])


@router.post("/ask", response_model=AskResponse)
def ask(
    payload: AskRequest,
    session: SessionDep,
    settings: SettingsDep,
    request: Request,
    principal: OperatorDep,
) -> AskResponse:
    origin = payload.origin or settings.default_origin
    destination = payload.destination or settings.default_destination
    hs_code = payload.hs_code
    invoice_value = None
    currency = "USD"
    as_of = payload.as_of or date.today()
    mode: OrchestrationMode = payload.orchestration_mode or settings.orchestration_mode
    product_text = None

    if payload.shipment_id:
        shipment = session.get(Shipment, payload.shipment_id)
        if shipment is None:
            raise AppError(code="SHIPMENT_NOT_FOUND", message="Shipment not found", status_code=404)
        if (
            principal.organization_id
            and shipment.organization_id
            and shipment.organization_id != principal.organization_id
        ):
            raise AppError(
                code="ORG_FORBIDDEN",
                message="Shipment not in your organization",
                status_code=403,
            )
        origin = shipment.origin
        destination = shipment.destination
        hs_code = shipment.hs_code_working or hs_code
        invoice_value = shipment.invoice_value
        currency = shipment.currency
        product_text = shipment.product_text
        if payload.as_of is None:
            as_of = shipment.as_of_date

    query = (payload.query or "").strip()
    if payload.focus is not None:
        query = build_focus_query(
            payload.focus,
            hs_code=hs_code,
            origin=origin.upper(),
            destination=destination.upper(),
            as_of=as_of.isoformat(),
            product_text=product_text,
        )

    result = run_ask(
        session,
        query=query,
        as_of=as_of,
        origin=origin.upper(),
        destination=destination.upper(),
        hs_code=hs_code,
        invoice_value=invoice_value,
        currency=currency,
        product_text=product_text,
        shipment_id=payload.shipment_id,
        mode=mode,
        settings=settings,
    )
    audit_from_request(
        session,
        request,
        principal,
        action="ask.query",
        resource_type="ask",
        resource_id=payload.shipment_id,
        detail={"mode": mode},
    )
    return result
