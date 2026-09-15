"""Shipment workspace CRUD and attached calc/checklist actions."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.errors import AppError
from backend.app.data.models import (
    CalculationSnapshot,
    Evidence,
    LineItem,
    Shipment,
    ShipmentCalculation,
    ShipmentChecklist,
)
from backend.app.domain.trade import (
    ChecklistOut,
    EvidenceCreate,
    EvidenceOut,
    LandedCostBreakdown,
    LandedCostInput,
    LineItemCreate,
    LineItemOut,
    ShipmentCalculateRequest,
    ShipmentCreate,
    ShipmentOut,
    ShipmentUpdate,
)
from backend.app.services import checklist_service, cost_service
from backend.app.services.document_service import normalize_checklist_item


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
        status="draft",
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
    session: Session, *, organization_id: str | None = None
) -> list[ShipmentOut]:
    stmt = select(Shipment).order_by(Shipment.updated_at.desc())
    if organization_id:
        stmt = stmt.where(Shipment.organization_id == organization_id)
    rows = session.scalars(stmt).all()
    return [_shipment_out(session, r) for r in rows]


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


def calculate_shipment(
    session: Session,
    shipment_id: str,
    payload: ShipmentCalculateRequest | None = None,
) -> ShipmentOut:
    row = session.get(Shipment, shipment_id)
    if row is None:
        raise AppError(code="SHIPMENT_NOT_FOUND", message="Shipment not found", status_code=404)
    if not row.hs_code_working:
        raise AppError(
            code="HS_REQUIRED",
            message="Set hs_code_working before calculating landed cost",
            status_code=400,
        )
    req = payload or ShipmentCalculateRequest()
    # Prefer request overrides, else persisted scenario freight/insurance (IF-11c).
    freight = req.freight if req.freight is not None else row.freight
    insurance = req.insurance if req.insurance is not None else row.insurance
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
