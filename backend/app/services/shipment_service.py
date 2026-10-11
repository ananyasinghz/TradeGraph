"""Shipment workspace CRUD and attached calc/checklist actions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.errors import AppError
from backend.app.data.models import (
    CalculationSnapshot,
    CaseComment,
    Evidence,
    LineItem,
    Shipment,
    ShipmentCalculation,
    ShipmentChecklist,
)
from backend.app.domain.trade import (
    AssignReviewerRequest,
    CaseCommentCreate,
    CaseCommentOut,
    ChecklistOut,
    EvidenceCreate,
    EvidenceOut,
    FtaCompareOut,
    LandedCostBreakdown,
    LandedCostInput,
    LineItemCreate,
    LineItemOut,
    LineItemUpdate,
    ShipmentCalculateRequest,
    ShipmentCreate,
    ShipmentOut,
    ShipmentUpdate,
)
from backend.app.services import checklist_service, cost_service, fta_service, pdf_util
from backend.app.services.auth_service import Principal
from backend.app.services.document_service import normalize_checklist_item
from backend.app.services.tariff_service import resolve_applicable_tariff


def _now() -> datetime:
    return datetime.now(UTC)


def _breakdown_from_json(payload: dict[str, Any]) -> LandedCostBreakdown:
    return LandedCostBreakdown.model_validate(payload)


def _line_out(row: LineItem) -> LineItemOut:
    return LineItemOut(
        id=row.id,
        shipment_id=row.shipment_id,
        line_number=row.line_number,
        description=row.description,
        hs_code=row.hs_code,
        qty=row.qty,
        unit_value=row.unit_value,
        currency=row.currency,
        origin=row.origin,
        notes=row.notes,
    )


def _evidence_out(row: Evidence) -> EvidenceOut:
    return EvidenceOut(
        id=row.id,
        shipment_id=row.shipment_id,
        kind=row.kind,
        label=row.label,
        source_document_id=row.source_document_id,
        tariff_rate_id=row.tariff_rate_id,
        excerpt=row.excerpt,
        uri=row.uri,
        checksum=row.checksum,
        status=row.status,
        meta=dict(row.meta_json or {}),
        created_at=row.created_at,
    )


def _lifecycle(status: str | None) -> str:
    s = (status or "open").lower()
    if s in {"closed", "complete", "completed", "done"}:
        return "closed"
    if s in {"discarded", "deleted", "archived"}:
        return "discarded"
    return "open"


def _assert_mutable(row: Shipment, *, action: str = "modify") -> None:
    life = _lifecycle(row.status)
    if life == "discarded":
        raise AppError(
            code="SHIPMENT_DISCARDED",
            message=f"Cannot {action} a discarded case",
            status_code=409,
        )
    if life == "closed":
        raise AppError(
            code="SHIPMENT_CLOSED",
            message=f"Cannot {action} a closed case — reopen it first",
            status_code=409,
        )


def _shipment_out(
    session: Session,
    shipment: Shipment,
    *,
    latest_calculation: LandedCostBreakdown | None = None,
    checklist: ChecklistOut | None = None,
) -> ShipmentOut:
    lines = session.scalars(
        select(LineItem)
        .where(LineItem.shipment_id == shipment.id)
        .order_by(LineItem.line_number, LineItem.id)
    ).all()
    evidence_rows = session.scalars(
        select(Evidence)
        .where(Evidence.shipment_id == shipment.id)
        .order_by(Evidence.created_at.desc())
    ).all()
    snaps = session.scalars(
        select(CalculationSnapshot)
        .where(CalculationSnapshot.shipment_id == shipment.id)
        .order_by(CalculationSnapshot.created_at.desc())
    ).all()
    life = _lifecycle(shipment.status)
    return ShipmentOut(
        id=shipment.id,
        title=shipment.title,
        product_text=shipment.product_text,
        origin=shipment.origin,
        destination=shipment.destination,
        hs_code_working=shipment.hs_code_working,
        as_of_date=shipment.as_of_date,
        incoterm=shipment.incoterm,
        invoice_value=shipment.invoice_value,
        currency=shipment.currency,
        qty=shipment.qty,
        freight=shipment.freight,
        insurance=shipment.insurance,
        regime=getattr(shipment, "regime", None) or "mfn",
        agreement_code=getattr(shipment, "agreement_code", None),
        organization_id=getattr(shipment, "organization_id", None),
        assumptions=dict(getattr(shipment, "assumptions_json", None) or {}),
        hs_confirmed_at=getattr(shipment, "hs_confirmed_at", None),
        status=shipment.status,
        closed_at=getattr(shipment, "closed_at", None),
        archived_at=getattr(shipment, "archived_at", None),
        assign_reviewer_user_id=getattr(shipment, "assign_reviewer_user_id", None),
        lifecycle=life,  # type: ignore[arg-type]
        exporter_party_id=shipment.exporter_party_id,
        importer_party_id=shipment.importer_party_id,
        consignee_party_id=shipment.consignee_party_id,
        created_at=shipment.created_at,
        updated_at=shipment.updated_at,
        latest_calculation=latest_calculation,
        checklist=checklist,
        line_items=[_line_out(r) for r in lines],
        evidence=[_evidence_out(r) for r in evidence_rows],
        calculation_snapshots=[cost_service.snapshot_to_out(r) for r in snaps],
    )


def create_shipment(session: Session, payload: ShipmentCreate) -> ShipmentOut:
    from backend.app.services.org_service import ensure_demo_org

    now = _now()
    org = ensure_demo_org(session)
    org_id = payload.organization_id or org.id
    row = Shipment(
        title=payload.title,
        product_text=payload.product_text,
        origin=payload.origin.upper(),
        destination=payload.destination.upper(),
        hs_code_working=payload.hs_code_working,
        as_of_date=payload.as_of_date,
        incoterm=payload.incoterm.upper(),
        invoice_value=payload.invoice_value,
        currency=payload.currency.upper(),
        qty=payload.qty,
        freight=payload.freight,
        insurance=payload.insurance,
        regime=payload.regime or "mfn",
        agreement_code=payload.agreement_code,
        organization_id=org_id,
        assumptions_json=dict(payload.assumptions or {}),
        hs_confirmed_at=None,
        status="open",
        closed_at=None,
        exporter_party_id=payload.exporter_party_id,
        importer_party_id=payload.importer_party_id,
        consignee_party_id=payload.consignee_party_id,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.flush()
    # Default single line item mirrors shipment header for R2 line-item model.
    session.add(
        LineItem(
            shipment_id=row.id,
            line_number=1,
            description=payload.product_text,
            hs_code=payload.hs_code_working,
            qty=payload.qty,
            unit_value=payload.invoice_value,
            currency=payload.currency.upper(),
            origin=payload.origin.upper(),
        )
    )
    session.flush()
    return _shipment_out(session, row)


def list_shipments(
    session: Session,
    *,
    organization_id: str | None = None,
    lifecycle: str | None = "open",
) -> list[ShipmentOut]:
    """List cases. lifecycle: open (default), closed, discarded, all."""
    stmt = select(Shipment).order_by(Shipment.updated_at.desc())
    if organization_id:
        stmt = stmt.where(Shipment.organization_id == organization_id)
    rows = session.scalars(stmt).all()
    outs = [_shipment_out(session, r) for r in rows]
    filt = (lifecycle or "open").lower()
    if filt == "all":
        # Hide discarded unless explicitly requested.
        outs = [o for o in outs if o.lifecycle != "discarded"]
    elif filt in {"open", "closed", "discarded"}:
        outs = [o for o in outs if o.lifecycle == filt]
    # Closed after open within same group already by updated_at; pin closed lower for "all".
    if filt == "all":
        outs.sort(key=lambda o: (0 if o.lifecycle == "open" else 1, -o.updated_at.timestamp()))
    return outs


def get_shipment(
    session: Session, shipment_id: str, *, organization_id: str | None = None
) -> ShipmentOut:
    row = session.get(Shipment, shipment_id)
    if row is None:
        raise AppError(code="SHIPMENT_NOT_FOUND", message="Shipment not found", status_code=404)
    if (
        organization_id
        and row.organization_id
        and row.organization_id != organization_id
    ):
        raise AppError(
            code="ORG_FORBIDDEN",
            message="Shipment not in your organization",
            status_code=403,
        )

    latest_calc = session.scalars(
        select(ShipmentCalculation)
        .where(ShipmentCalculation.shipment_id == shipment_id)
        .order_by(ShipmentCalculation.created_at.desc())
    ).first()
    latest_checklist = session.scalars(
        select(ShipmentChecklist)
        .where(ShipmentChecklist.shipment_id == shipment_id)
        .order_by(ShipmentChecklist.updated_at.desc())
    ).first()

    calc_out = _breakdown_from_json(latest_calc.outputs_json) if latest_calc else None
    checklist_out = None
    if latest_checklist:
        items = [normalize_checklist_item(i) for i in latest_checklist.items_json or []]
        checklist_out = ChecklistOut(
            origin=row.origin,
            destination=row.destination,
            hs_code=row.hs_code_working,
            items=items,
            progress=latest_checklist.progress,
        )
    return _shipment_out(
        session, row, latest_calculation=calc_out, checklist=checklist_out
    )


def update_shipment(session: Session, shipment_id: str, payload: ShipmentUpdate) -> ShipmentOut:
    row = session.get(Shipment, shipment_id)
    if row is None:
        raise AppError(code="SHIPMENT_NOT_FOUND", message="Shipment not found", status_code=404)
    data = payload.model_dump(exclude_unset=True)
    # Lifecycle transitions go through dedicated helpers.
    if "status" in data:
        data.pop("status")
    _assert_mutable(row, action="update")
    if "assumptions" in data:
        row.assumptions_json = dict(data.pop("assumptions") or {})
    for key, value in data.items():
        if key in {"origin", "destination", "currency", "incoterm"} and isinstance(value, str):
            value = value.upper()
        setattr(row, key, value)
    row.updated_at = _now()
    # Keep primary line item HS in sync when working HS changes.
    if "hs_code_working" in data:
        primary = session.scalars(
            select(LineItem)
            .where(LineItem.shipment_id == shipment_id)
            .order_by(LineItem.line_number)
        ).first()
        if primary is not None:
            primary.hs_code = data["hs_code_working"]
    session.flush()
    if "freight" in data or "insurance" in data:
        from backend.app.services import timeline_service

        timeline_service.record_event(
            session,
            scenario_id=shipment_id,
            organization_id=row.organization_id,
            event_type="valuation_change",
            summary=(
                f"Valuation updated · freight={row.freight} · insurance={row.insurance}"
            ),
            payload={"freight": str(row.freight) if row.freight is not None else None,
                     "insurance": str(row.insurance) if row.insurance is not None else None},
        )
    return get_shipment(session, shipment_id)


def close_shipment(session: Session, shipment_id: str) -> ShipmentOut:
    row = session.get(Shipment, shipment_id)
    if row is None:
        raise AppError(code="SHIPMENT_NOT_FOUND", message="Shipment not found", status_code=404)
    if _lifecycle(row.status) == "discarded":
        raise AppError(
            code="SHIPMENT_DISCARDED",
            message="Cannot close a discarded case",
            status_code=409,
        )
    if _lifecycle(row.status) == "closed":
        return get_shipment(session, shipment_id)
    now = _now()
    row.status = "closed"
    row.closed_at = now
    row.updated_at = now
    session.flush()
    from backend.app.services import timeline_service

    timeline_service.record_event(
        session,
        scenario_id=shipment_id,
        organization_id=row.organization_id,
        event_type="case_closed",
        summary="Case closed",
        payload={"status": "closed"},
    )
    return get_shipment(session, shipment_id)


def reopen_shipment(session: Session, shipment_id: str) -> ShipmentOut:
    row = session.get(Shipment, shipment_id)
    if row is None:
        raise AppError(code="SHIPMENT_NOT_FOUND", message="Shipment not found", status_code=404)
    if _lifecycle(row.status) == "discarded":
        raise AppError(
            code="SHIPMENT_DISCARDED",
            message="Cannot reopen a discarded case",
            status_code=409,
        )
    row.status = "open"
    row.closed_at = None
    row.updated_at = _now()
    session.flush()
    from backend.app.services import timeline_service

    timeline_service.record_event(
        session,
        scenario_id=shipment_id,
        organization_id=row.organization_id,
        event_type="case_reopened",
        summary="Case reopened",
        payload={"status": "open"},
    )
    return get_shipment(session, shipment_id)


def discard_shipment(session: Session, shipment_id: str) -> ShipmentOut:
    """Soft-delete a mistaken or abandoned case."""
    row = session.get(Shipment, shipment_id)
    if row is None:
        raise AppError(code="SHIPMENT_NOT_FOUND", message="Shipment not found", status_code=404)
    now = _now()
    row.status = "discarded"
    row.closed_at = row.closed_at or now
    row.updated_at = now
    session.flush()
    from backend.app.services import timeline_service

    timeline_service.record_event(
        session,
        scenario_id=shipment_id,
        organization_id=row.organization_id,
        event_type="case_discarded",
        summary="Case discarded",
        payload={"status": "discarded"},
    )
    # Return out without get_shipment (which 404s discarded).
    return _shipment_out(session, row)


def _sum_breakdowns(parts: list[LandedCostBreakdown], *, currency: str) -> LandedCostBreakdown:
    if not parts:
        raise AppError(code="CALC_EMPTY", message="No line calculations to roll up", status_code=400)
    if len(parts) == 1:
        return parts[0]
    base = parts[0]
    assessable = sum((p.assessable_value for p in parts), Decimal("0"))
    total_duties = sum((p.total_duties_taxes for p in parts), Decimal("0"))
    landed = sum((p.landed_cost for p in parts), Decimal("0"))
    return base.model_copy(
        update={
            "assessable_value": assessable,
            "bcd": sum((p.bcd for p in parts), Decimal("0")),
            "sws": sum((p.sws for p in parts), Decimal("0")),
            "igst": sum((p.igst for p in parts), Decimal("0")),
            "aidc": sum((p.aidc for p in parts), Decimal("0")),
            "health_cess": sum((p.health_cess for p in parts), Decimal("0")),
            "compensation_cess": sum((p.compensation_cess for p in parts), Decimal("0")),
            "total_duties_taxes": total_duties,
            "landed_cost": landed,
            "currency": currency,
            "title": f"Multi-line rollup ({len(parts)} lines)",
            "assumptions": [
                *base.assumptions,
                f"Rolled up {len(parts)} line-item duty calculations.",
            ],
            "formula_steps": [
                *base.formula_steps,
                f"Sum of {len(parts)} line duties → {total_duties}",
            ],
        }
    )


def calculate_shipment(
    session: Session,
    shipment_id: str,
    payload: ShipmentCalculateRequest | None = None,
) -> ShipmentOut:
    row = session.get(Shipment, shipment_id)
    if row is None:
        raise AppError(code="SHIPMENT_NOT_FOUND", message="Shipment not found", status_code=404)
    _assert_mutable(row, action="calculate")
    req = payload or ShipmentCalculateRequest()
    freight = req.freight if req.freight is not None else row.freight
    insurance = req.insurance if req.insurance is not None else row.insurance
    lines = session.scalars(
        select(LineItem)
        .where(LineItem.shipment_id == shipment_id)
        .order_by(LineItem.line_number, LineItem.id)
    ).all()
    calcable = [
        li
        for li in lines
        if li.hs_code and li.unit_value is not None and Decimal(li.unit_value) > 0
    ]

    if calcable:
        parts: list[LandedCostBreakdown] = []
        for idx, li in enumerate(calcable):
            line_freight = freight if idx == 0 else Decimal("0")
            line_insurance = insurance if idx == 0 else Decimal("0")
            cost_payload = LandedCostInput(
                hs_code=li.hs_code or row.hs_code_working or "",
                origin=(li.origin or row.origin),
                destination=row.destination,
                as_of=row.as_of_date,
                invoice_value=Decimal(li.unit_value) * Decimal(li.qty),
                currency=li.currency or row.currency,
                incoterm=row.incoterm,
                freight=line_freight,
                insurance=line_insurance,
                requested_mode=req.requested_mode,
                shipment_id=row.id,
                persist_snapshot=False,
                selected_exemption_id=req.selected_exemption_id,
            )
            parts.append(cost_service.calculate(session, cost_payload))
        breakdown = _sum_breakdowns(parts, currency=row.currency)
        # Persist one rollup snapshot.
        snap_payload = LandedCostInput(
            hs_code=row.hs_code_working or calcable[0].hs_code or "",
            origin=row.origin,
            destination=row.destination,
            as_of=row.as_of_date,
            invoice_value=row.invoice_value,
            currency=row.currency,
            incoterm=row.incoterm,
            freight=freight,
            insurance=insurance,
            requested_mode=req.requested_mode,
            shipment_id=row.id,
            persist_snapshot=True,
            selected_exemption_id=req.selected_exemption_id,
        )
        cost_service.persist_snapshot(session, payload=snap_payload, breakdown=breakdown)
    else:
        if not row.hs_code_working:
            raise AppError(
                code="HS_REQUIRED",
                message="Set hs_code_working before calculating landed cost",
                status_code=400,
            )
        cost_payload = LandedCostInput(
            hs_code=row.hs_code_working,
            origin=row.origin,
            destination=row.destination,
            as_of=row.as_of_date,
            invoice_value=row.invoice_value,
            currency=row.currency,
            incoterm=row.incoterm,
            freight=freight,
            insurance=insurance,
            requested_mode=req.requested_mode,
            shipment_id=row.id,
            persist_snapshot=True,
            selected_exemption_id=req.selected_exemption_id,
        )
        breakdown = cost_service.calculate(session, cost_payload)

    calc = ShipmentCalculation(
        shipment_id=row.id,
        inputs_json={
            "hs_code": row.hs_code_working,
            "origin": row.origin,
            "destination": row.destination,
            "as_of": row.as_of_date.isoformat(),
            "invoice_value": str(row.invoice_value),
            "currency": row.currency,
            "incoterm": row.incoterm,
            "requested_mode": req.requested_mode,
            "freight": str(freight) if freight is not None else None,
            "insurance": str(insurance) if insurance is not None else None,
            "selected_exemption_id": req.selected_exemption_id,
            "line_rollup": bool(calcable),
            "line_count": len(calcable),
        },
        outputs_json=breakdown.model_dump(mode="json"),
        tariff_rate_id=breakdown.tariff_rate_id,
        created_at=_now(),
    )
    session.add(calc)
    row.updated_at = _now()
    session.flush()
    return get_shipment(session, shipment_id)


def list_calculation_snapshots(
    session: Session, shipment_id: str
) -> list[Any]:
    row = session.get(Shipment, shipment_id)
    if row is None:
        raise AppError(code="SHIPMENT_NOT_FOUND", message="Shipment not found", status_code=404)
    snaps = session.scalars(
        select(CalculationSnapshot)
        .where(CalculationSnapshot.shipment_id == shipment_id)
        .order_by(CalculationSnapshot.created_at.desc())
    ).all()
    return [cost_service.snapshot_to_out(s) for s in snaps]


def add_line_item(session: Session, shipment_id: str, payload: LineItemCreate) -> ShipmentOut:
    row = session.get(Shipment, shipment_id)
    if row is None:
        raise AppError(code="SHIPMENT_NOT_FOUND", message="Shipment not found", status_code=404)
    _assert_mutable(row, action="add line items")
    session.add(
        LineItem(
            shipment_id=shipment_id,
            line_number=payload.line_number,
            description=payload.description,
            hs_code=payload.hs_code,
            qty=payload.qty,
            unit_value=payload.unit_value,
            currency=payload.currency.upper(),
            origin=payload.origin.upper() if payload.origin else None,
            notes=payload.notes,
        )
    )
    row.updated_at = _now()
    session.flush()
    return get_shipment(session, shipment_id)


def add_evidence(session: Session, shipment_id: str, payload: EvidenceCreate) -> ShipmentOut:
    row = session.get(Shipment, shipment_id)
    if row is None:
        raise AppError(code="SHIPMENT_NOT_FOUND", message="Shipment not found", status_code=404)
    _assert_mutable(row, action="add evidence")
    session.add(
        Evidence(
            shipment_id=shipment_id,
            kind=payload.kind,
            label=payload.label,
            source_document_id=payload.source_document_id,
            tariff_rate_id=payload.tariff_rate_id,
            excerpt=payload.excerpt,
            uri=payload.uri,
            checksum=payload.checksum,
            status="recorded",
            meta_json=dict(payload.meta or {}),
            created_at=_now(),
        )
    )
    row.updated_at = _now()
    session.flush()
    return get_shipment(session, shipment_id)


def build_shipment_checklist(session: Session, shipment_id: str) -> ShipmentOut:
    row = session.get(Shipment, shipment_id)
    if row is None:
        raise AppError(code="SHIPMENT_NOT_FOUND", message="Shipment not found", status_code=404)
    _assert_mutable(row, action="build checklist")
    prior = session.scalars(
        select(ShipmentChecklist)
        .where(ShipmentChecklist.shipment_id == shipment_id)
        .order_by(ShipmentChecklist.updated_at.desc())
    ).first()
    checklist = checklist_service.build_checklist(
        session,
        origin=row.origin,
        destination=row.destination,
        hs_code=row.hs_code_working,
        prior_items=list(prior.items_json) if prior else None,
    )
    saved = ShipmentChecklist(
        shipment_id=row.id,
        items_json=[i.model_dump(mode="json") for i in checklist.items],
        progress=checklist.progress,
        updated_at=_now(),
    )
    session.add(saved)
    row.updated_at = _now()
    session.flush()
    return get_shipment(session, shipment_id)


def update_line_item(
    session: Session,
    shipment_id: str,
    line_id: str,
    payload: LineItemUpdate,
) -> ShipmentOut:
    row = session.get(Shipment, shipment_id)
    if row is None:
        raise AppError(code="SHIPMENT_NOT_FOUND", message="Shipment not found", status_code=404)
    _assert_mutable(row, action="update line items")
    line = session.get(LineItem, line_id)
    if line is None or line.shipment_id != shipment_id:
        raise AppError(code="LINE_NOT_FOUND", message="Line item not found", status_code=404)
    data = payload.model_dump(exclude_unset=True)
    if "currency" in data and isinstance(data["currency"], str):
        data["currency"] = data["currency"].upper()
    if "origin" in data and isinstance(data["origin"], str):
        data["origin"] = data["origin"].upper()
    for key, value in data.items():
        setattr(line, key, value)
    row.updated_at = _now()
    session.flush()
    return get_shipment(session, shipment_id)


def delete_line_item(session: Session, shipment_id: str, line_id: str) -> ShipmentOut:
    row = session.get(Shipment, shipment_id)
    if row is None:
        raise AppError(code="SHIPMENT_NOT_FOUND", message="Shipment not found", status_code=404)
    _assert_mutable(row, action="delete line items")
    line = session.get(LineItem, line_id)
    if line is None or line.shipment_id != shipment_id:
        raise AppError(code="LINE_NOT_FOUND", message="Line item not found", status_code=404)
    session.delete(line)
    row.updated_at = _now()
    session.flush()
    return get_shipment(session, shipment_id)


def list_comments(session: Session, shipment_id: str) -> list[CaseCommentOut]:
    if session.get(Shipment, shipment_id) is None:
        raise AppError(code="SHIPMENT_NOT_FOUND", message="Shipment not found", status_code=404)
    rows = session.scalars(
        select(CaseComment)
        .where(CaseComment.shipment_id == shipment_id)
        .order_by(CaseComment.created_at.asc())
    ).all()
    return [
        CaseCommentOut(
            id=r.id,
            shipment_id=r.shipment_id,
            organization_id=r.organization_id,
            author_user_id=r.author_user_id,
            author_actor=r.author_actor,
            body=r.body,
            created_at=r.created_at,
        )
        for r in rows
    ]


def add_comment(
    session: Session,
    shipment_id: str,
    payload: CaseCommentCreate,
    *,
    principal: Principal,
) -> CaseCommentOut:
    row = session.get(Shipment, shipment_id)
    if row is None:
        raise AppError(code="SHIPMENT_NOT_FOUND", message="Shipment not found", status_code=404)
    comment = CaseComment(
        shipment_id=shipment_id,
        organization_id=row.organization_id,
        author_user_id=principal.user_id,
        author_actor=principal.actor,
        body=payload.body.strip(),
        created_at=_now(),
    )
    session.add(comment)
    row.updated_at = _now()
    session.flush()
    return CaseCommentOut(
        id=comment.id,
        shipment_id=comment.shipment_id,
        organization_id=comment.organization_id,
        author_user_id=comment.author_user_id,
        author_actor=comment.author_actor,
        body=comment.body,
        created_at=comment.created_at,
    )


def assign_reviewer(
    session: Session,
    shipment_id: str,
    payload: AssignReviewerRequest,
) -> ShipmentOut:
    row = session.get(Shipment, shipment_id)
    if row is None:
        raise AppError(code="SHIPMENT_NOT_FOUND", message="Shipment not found", status_code=404)
    _assert_mutable(row, action="assign reviewer")
    row.assign_reviewer_user_id = payload.assign_reviewer_user_id
    row.updated_at = _now()
    session.flush()
    return get_shipment(session, shipment_id)


def compare_fta(
    session: Session,
    shipment_id: str,
    *,
    conditions: Any | None = None,
) -> FtaCompareOut:
    from backend.app.domain.trade import FtaConditionInput

    row = session.get(Shipment, shipment_id)
    if row is None:
        raise AppError(code="SHIPMENT_NOT_FOUND", message="Shipment not found", status_code=404)
    if not row.hs_code_working:
        raise AppError(
            code="HS_REQUIRED",
            message="Set hs_code_working before FTA compare",
            status_code=400,
        )
    cond = conditions if isinstance(conditions, FtaConditionInput) else (
        FtaConditionInput.model_validate(conditions) if conditions else None
    )
    base_payload = LandedCostInput(
        hs_code=row.hs_code_working,
        origin=row.origin,
        destination=row.destination,
        as_of=row.as_of_date,
        invoice_value=row.invoice_value,
        currency=row.currency,
        incoterm=row.incoterm,
        freight=row.freight,
        insurance=row.insurance,
        shipment_id=row.id,
        persist_snapshot=True,
    )
    without = cost_service.calculate(session, base_payload)
    without_id = next(
        (a.split("=", 1)[1] for a in without.assumptions if a.startswith("calculation_snapshot_id=")),
        None,
    )
    if without_id is None:
        snaps = list_calculation_snapshots(session, shipment_id)
        without_id = snaps[0].id if snaps else None
    if without_id is None:
        raise AppError(code="SNAPSHOT_MISSING", message="Failed to persist MFN snapshot", status_code=500)

    fta = fta_service.check_fta(
        session,
        hs_code=row.hs_code_working,
        origin=row.origin,
        destination=row.destination,
        as_of=row.as_of_date,
        shipment_id=row.id,
        conditions=cond,
    )
    pref_rate = fta.preferential_rate_pct if fta else None
    pref_status = fta.status if fta else "unknown"
    blocked_reason: str | None = None
    preferential_applied = False
    if pref_status != "eligible":
        blocked_reason = (
            "MFN only — preference not claimed/proven "
            f"(FTA status={pref_status}; CoO and FTA conditions must pass)."
        )
        pref_rate_for_calc = None
    else:
        pref_rate_for_calc = pref_rate

    tariff = resolve_applicable_tariff(
        session,
        hs_code=row.hs_code_working,
        origin=row.origin,
        destination=row.destination,
        as_of=row.as_of_date,
    )
    pref_tariff: Any = tariff
    if pref_rate_for_calc is not None:
        preferential_applied = True
        components = {**dict(tariff.duty_components or {}), "bcd_pct": float(pref_rate_for_calc)}
        # Stamp preferential BCD provenance separately from MFN BCD.
        prov = dict(components.get("_provenance") or {})
        prov["bcd_pct"] = {
            "value": float(pref_rate_for_calc),
            "source_key": "safta_preferential_illustrative",
            "source_document_id": getattr(fta, "agreement_id", None),
            "data_quality": "illustrative",
            "effective_from": str(tariff.effective_from),
            "notes": "Preferential BCD overlay gated on FTA eligible + CoO (illustrative).",
        }
        components["_provenance"] = prov
        pref_tariff = SimpleNamespace(
            id=tariff.id,
            hs_code=tariff.hs_code,
            origin=tariff.origin,
            destination=tariff.destination,
            rate=Decimal(pref_rate_for_calc),
            rate_type=tariff.rate_type,
            duty_components=components,
            agreement_id=getattr(fta, "agreement_id", None),
            effective_from=tariff.effective_from,
            effective_to=tariff.effective_to,
            source_document_id=tariff.source_document_id,
            source_document=getattr(tariff, "source_document", None),
            version=tariff.version,
            status=tariff.status,
            data_quality=tariff.data_quality,
            regime="preferential",
            rule_label=getattr(fta, "agreement_name", None),
            notes=tariff.notes,
        )

    with_breakdown = cost_service.calculate_from_tariff(
        row.invoice_value,
        row.currency,
        pref_tariff,  # type: ignore[arg-type]
        incoterm=row.incoterm,
        payload=base_payload.model_copy(update={"persist_snapshot": False}),
        session=session,
    )
    pref_assumptions = list(with_breakdown.assumptions)
    if preferential_applied:
        pref_assumptions.append(
            "Preferential BCD applied — FTA status eligible with CoO evidence (illustrative)."
        )
        title = "Preferential (FTA) estimate"
    else:
        pref_assumptions.append(blocked_reason or "Preferential path blocked; MFN stack shown.")
        title = "MFN only — preference not claimed/proven"
    with_breakdown = with_breakdown.model_copy(
        update={"title": title, "assumptions": pref_assumptions}
    )
    with_snap = cost_service.persist_snapshot(
        session, payload=base_payload, breakdown=with_breakdown, tariff=tariff
    )

    diff = cost_service.diff_snapshots(session, without_id, with_snap.id)
    return FtaCompareOut(
        shipment_id=shipment_id,
        without_preferential=cost_service.get_snapshot(session, without_id),
        with_preferential=cost_service.snapshot_to_out(with_snap),
        diff=diff,
        preferential_rate_pct=pref_rate,
        preferential_applied=preferential_applied,
        preferential_status=pref_status,
        preferential_blocked_reason=blocked_reason,
        agreement_id=getattr(fta, "agreement_id", None) if fta else None,
        agreement_name=getattr(fta, "agreement_name", None) if fta else None,
    )


def export_summary_pdf(session: Session, shipment_id: str) -> bytes:
    detail = get_shipment(session, shipment_id)
    calc = detail.latest_calculation
    lines = [
        f"Case: {detail.title}",
        f"ID: {detail.id}",
        f"Corridor: {detail.origin} → {detail.destination}",
        f"HS: {detail.hs_code_working or '—'}",
        f"Invoice: {detail.invoice_value} {detail.currency}",
        f"Status: {detail.status}",
        f"Reviewer: {detail.assign_reviewer_user_id or 'unassigned'}",
        "",
        "Latest calculation:",
    ]
    if calc:
        lines.extend(
            [
                f"  Landed cost: {calc.landed_cost} {calc.currency}",
                f"  Total duties: {calc.total_duties_taxes}",
                f"  BCD rate: {calc.bcd_rate_pct}%",
                f"  Mode: {calc.calculation_mode}",
            ]
        )
    else:
        lines.append("  (none)")
    lines.extend(
        [
            "",
            "Illustrative TradeGraph summary — not an official customs document.",
        ]
    )
    return pdf_util.text_to_pdf("Shipment summary", "\n".join(lines))


def export_cost_csv(session: Session, shipment_id: str) -> str:
    detail = get_shipment(session, shipment_id)
    calc = detail.latest_calculation
    headers = [
        "shipment_id",
        "title",
        "hs_code",
        "origin",
        "destination",
        "invoice_value",
        "currency",
        "assessable_value",
        "bcd",
        "sws",
        "igst",
        "total_duties_taxes",
        "landed_cost",
        "bcd_rate_pct",
    ]
    vals = [
        detail.id,
        detail.title,
        detail.hs_code_working or "",
        detail.origin,
        detail.destination,
        str(detail.invoice_value),
        detail.currency,
        str(calc.assessable_value) if calc else "",
        str(calc.bcd) if calc else "",
        str(calc.sws) if calc else "",
        str(calc.igst) if calc else "",
        str(calc.total_duties_taxes) if calc else "",
        str(calc.landed_cost) if calc else "",
        str(calc.bcd_rate_pct) if calc else "",
    ]

    def _csv(v: str) -> str:
        if any(c in v for c in [",", '"', "\n"]):
            return '"' + v.replace('"', '""') + '"'
        return v

    return ",".join(headers) + "\n" + ",".join(_csv(v) for v in vals) + "\n"


def retention_archive(session: Session, *, days: int = 90) -> dict[str, Any]:
    """Mark closed shipments older than N days as archived (sets archived_at)."""
    if days < 1:
        raise AppError(code="INVALID_DAYS", message="days must be >= 1", status_code=400)
    cutoff = _now() - timedelta(days=days)
    rows = session.scalars(
        select(Shipment).where(
            Shipment.status.in_(["closed", "complete", "completed", "done"]),
            Shipment.archived_at.is_(None),
            Shipment.closed_at.is_not(None),
            Shipment.closed_at <= cutoff,
        )
    ).all()
    now = _now()
    for row in rows:
        row.archived_at = now
        row.updated_at = now
    session.flush()
    return {"archived": len(rows), "days": days, "cutoff": cutoff.isoformat()}
