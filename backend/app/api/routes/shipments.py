"""Shipment workspace routes (operator+; org-scoped when auth on)."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, Header, Request, UploadFile

from backend.app.api.dependencies import SessionDep, SettingsDep
from backend.app.domain.trade import (
    CalculationSnapshotOut,
    ChecklistItemStatusUpdate,
    ClassificationCandidatesOut,
    ClassificationConfirmRequest,
    DocumentFormOut,
    DocumentUploadOut,
    DraftExportOut,
    EvidenceCreate,
    LineItemCreate,
    ReadinessOut,
    ShipmentCalculateRequest,
    ShipmentCreate,
    ShipmentOut,
    ShipmentUpdate,
    ShipmentWorkspaceOut,
)
from backend.app.services import (
    classification_service,
    document_service,
    readiness_service,
    shipment_service,
    workspace_service,
)
from backend.app.services.auth_service import (
    Principal,
    audit_from_request,
    require_role,
    resolve_organization_id,
)

router = APIRouter(prefix="/shipments", tags=["shipments"])

OperatorDep = Annotated[Principal, Depends(require_role("operator"))]


def _org(
    settings: SettingsDep,
    principal: Principal,
    x_organization_id: str | None,
) -> str:
    return resolve_organization_id(settings, principal, x_organization_id)


@router.get("", response_model=list[ShipmentOut])
def list_shipments(
    session: SessionDep,
    settings: SettingsDep,
    principal: OperatorDep,
    x_organization_id: str | None = Header(default=None),
) -> list[ShipmentOut]:
    org = _org(settings, principal, x_organization_id) if settings.auth_enabled else None
    return shipment_service.list_shipments(session, organization_id=org)


@router.post("", response_model=ShipmentOut)
def create_shipment(
    payload: ShipmentCreate,
    session: SessionDep,
    settings: SettingsDep,
    principal: OperatorDep,
    request: Request,
    x_organization_id: str | None = Header(default=None),
) -> ShipmentOut:
    org = _org(settings, principal, x_organization_id)
    data = payload.model_copy(update={"organization_id": payload.organization_id or org})
    out = shipment_service.create_shipment(session, data)
    audit_from_request(
        session,
        request,
        principal,
        action="shipment.create",
        resource_type="shipment",
        resource_id=out.id,
    )
    return out


@router.get("/{shipment_id}/workspace", response_model=ShipmentWorkspaceOut)
def shipment_workspace(
    shipment_id: str,
    session: SessionDep,
    settings: SettingsDep,
    principal: OperatorDep,
    x_organization_id: str | None = Header(default=None),
) -> ShipmentWorkspaceOut:
    org = _org(settings, principal, x_organization_id) if settings.auth_enabled else None
    shipment_service.get_shipment(session, shipment_id, organization_id=org)
    return workspace_service.get_workspace(session, shipment_id)


@router.get("/{shipment_id}/readiness", response_model=ReadinessOut)
def shipment_readiness(
    shipment_id: str,
    session: SessionDep,
    settings: SettingsDep,
    principal: OperatorDep,
    x_organization_id: str | None = Header(default=None),
) -> ReadinessOut:
    org = _org(settings, principal, x_organization_id) if settings.auth_enabled else None
    shipment_service.get_shipment(session, shipment_id, organization_id=org)
    return readiness_service.score_shipment(session, shipment_id)


@router.get("/{shipment_id}", response_model=ShipmentOut)
def get_shipment(
    shipment_id: str,
    session: SessionDep,
    settings: SettingsDep,
    principal: OperatorDep,
    x_organization_id: str | None = Header(default=None),
) -> ShipmentOut:
    org = _org(settings, principal, x_organization_id) if settings.auth_enabled else None
    return shipment_service.get_shipment(session, shipment_id, organization_id=org)


@router.patch("/{shipment_id}", response_model=ShipmentOut)
def update_shipment(
    shipment_id: str,
    payload: ShipmentUpdate,
    session: SessionDep,
    settings: SettingsDep,
    principal: OperatorDep,
    request: Request,
    x_organization_id: str | None = Header(default=None),
) -> ShipmentOut:
    org = _org(settings, principal, x_organization_id) if settings.auth_enabled else None
    shipment_service.get_shipment(session, shipment_id, organization_id=org)
    out = shipment_service.update_shipment(session, shipment_id, payload)
    audit_from_request(
        session,
        request,
        principal,
        action="shipment.update",
        resource_type="shipment",
        resource_id=shipment_id,
    )
    return out


@router.post("/{shipment_id}/calculate", response_model=ShipmentOut)
def calculate_shipment(
    shipment_id: str,
    session: SessionDep,
    settings: SettingsDep,
    principal: OperatorDep,
    payload: ShipmentCalculateRequest | None = None,
    x_organization_id: str | None = Header(default=None),
) -> ShipmentOut:
    org = _org(settings, principal, x_organization_id) if settings.auth_enabled else None
    shipment_service.get_shipment(session, shipment_id, organization_id=org)
    return shipment_service.calculate_shipment(session, shipment_id, payload)


@router.get(
    "/{shipment_id}/calculation-snapshots",
    response_model=list[CalculationSnapshotOut],
)
def list_calculation_snapshots(
    shipment_id: str,
    session: SessionDep,
    settings: SettingsDep,
    principal: OperatorDep,
    x_organization_id: str | None = Header(default=None),
) -> list[CalculationSnapshotOut]:
    org = _org(settings, principal, x_organization_id) if settings.auth_enabled else None
    shipment_service.get_shipment(session, shipment_id, organization_id=org)
    return shipment_service.list_calculation_snapshots(session, shipment_id)


@router.get(
    "/{shipment_id}/classification/candidates",
    response_model=ClassificationCandidatesOut,
)
def shipment_classification_candidates(
    shipment_id: str,
    session: SessionDep,
    settings: SettingsDep,
    principal: OperatorDep,
    x_organization_id: str | None = Header(default=None),
) -> ClassificationCandidatesOut:
    org = _org(settings, principal, x_organization_id) if settings.auth_enabled else None
    shipment_service.get_shipment(session, shipment_id, organization_id=org)
    return classification_service.candidates_for_shipment(session, shipment_id)


@router.post("/{shipment_id}/classification/confirm", response_model=ShipmentOut)
def confirm_classification(
    shipment_id: str,
    payload: ClassificationConfirmRequest,
    session: SessionDep,
    settings: SettingsDep,
    principal: OperatorDep,
    request: Request,
    x_organization_id: str | None = Header(default=None),
) -> ShipmentOut:
    org = _org(settings, principal, x_organization_id) if settings.auth_enabled else None
    shipment_service.get_shipment(session, shipment_id, organization_id=org)
    out = classification_service.confirm_classification(session, shipment_id, payload)
    audit_from_request(
        session,
        request,
        principal,
        action="shipment.confirm_hs",
        resource_type="shipment",
        resource_id=shipment_id,
        detail={"hs_code": payload.hs_code},
    )
    return out


@router.post("/{shipment_id}/line-items", response_model=ShipmentOut)
def add_line_item(
    shipment_id: str,
    payload: LineItemCreate,
    session: SessionDep,
    settings: SettingsDep,
    principal: OperatorDep,
    x_organization_id: str | None = Header(default=None),
) -> ShipmentOut:
    org = _org(settings, principal, x_organization_id) if settings.auth_enabled else None
    shipment_service.get_shipment(session, shipment_id, organization_id=org)
    return shipment_service.add_line_item(session, shipment_id, payload)


@router.post("/{shipment_id}/evidence", response_model=ShipmentOut)
def add_evidence(
    shipment_id: str,
    payload: EvidenceCreate,
    session: SessionDep,
    settings: SettingsDep,
    principal: OperatorDep,
    x_organization_id: str | None = Header(default=None),
) -> ShipmentOut:
    org = _org(settings, principal, x_organization_id) if settings.auth_enabled else None
    shipment_service.get_shipment(session, shipment_id, organization_id=org)
    return shipment_service.add_evidence(session, shipment_id, payload)


@router.post("/{shipment_id}/checklist", response_model=ShipmentOut)
def checklist_shipment(
    shipment_id: str,
    session: SessionDep,
    settings: SettingsDep,
    principal: OperatorDep,
    x_organization_id: str | None = Header(default=None),
) -> ShipmentOut:
    org = _org(settings, principal, x_organization_id) if settings.auth_enabled else None
    shipment_service.get_shipment(session, shipment_id, organization_id=org)
    return shipment_service.build_shipment_checklist(session, shipment_id)


@router.patch("/{shipment_id}/documents/{doc_code}", response_model=ShipmentOut)
def update_document_status(
    shipment_id: str,
    doc_code: str,
    payload: ChecklistItemStatusUpdate,
    session: SessionDep,
    settings: SettingsDep,
    principal: OperatorDep,
    x_organization_id: str | None = Header(default=None),
) -> ShipmentOut:
    org = _org(settings, principal, x_organization_id) if settings.auth_enabled else None
    shipment_service.get_shipment(session, shipment_id, organization_id=org)
    return document_service.update_document_status(session, shipment_id, doc_code, payload)


@router.get("/{shipment_id}/forms/{kind}", response_model=DocumentFormOut)
def get_document_form(
    shipment_id: str,
    kind: Literal["commercial_invoice", "packing_list", "certificate_of_origin"],
    session: SessionDep,
    settings: SettingsDep,
    principal: OperatorDep,
    x_organization_id: str | None = Header(default=None),
) -> DocumentFormOut:
    org = _org(settings, principal, x_organization_id) if settings.auth_enabled else None
    shipment_service.get_shipment(session, shipment_id, organization_id=org)
    return document_service.document_form(session, shipment_id, kind)


@router.get("/{shipment_id}/uploads", response_model=list[DocumentUploadOut])
def list_shipment_uploads(
    shipment_id: str,
    session: SessionDep,
    settings: SettingsDep,
    principal: OperatorDep,
    x_organization_id: str | None = Header(default=None),
) -> list[DocumentUploadOut]:
    org = _org(settings, principal, x_organization_id) if settings.auth_enabled else None
    shipment_service.get_shipment(session, shipment_id, organization_id=org)
    return document_service.list_uploads(session, shipment_id)


@router.post("/{shipment_id}/uploads", response_model=DocumentUploadOut)
async def upload_shipment_document(
    shipment_id: str,
    session: SessionDep,
    settings: SettingsDep,
    principal: OperatorDep,
    request: Request,
    doc_code: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
    notes: Annotated[str | None, Form()] = None,
    x_organization_id: str | None = Header(default=None),
) -> DocumentUploadOut:
    org = _org(settings, principal, x_organization_id) if settings.auth_enabled else None
    shipment_service.get_shipment(session, shipment_id, organization_id=org)
    content = await file.read()
    out = document_service.upload_document(
        session,
        shipment_id,
        doc_code=doc_code,
        filename=file.filename or "upload.bin",
        content=content,
        content_type=file.content_type or "application/octet-stream",
        notes=notes,
        uploaded_by=principal.actor,
    )
    audit_from_request(
        session,
        request,
        principal,
        action="shipment.upload",
        resource_type="shipment",
        resource_id=shipment_id,
        detail={"doc_code": doc_code, "filename": out.filename},
    )
    return out


@router.get("/{shipment_id}/drafts/{kind}", response_model=DraftExportOut)
def export_shipment_draft(
    shipment_id: str,
    kind: Literal["commercial_invoice", "packing_list", "checklist"],
    session: SessionDep,
    settings: SettingsDep,
    principal: OperatorDep,
    as_pdf: bool = False,
    x_organization_id: str | None = Header(default=None),
) -> DraftExportOut:
    org = _org(settings, principal, x_organization_id) if settings.auth_enabled else None
    shipment_service.get_shipment(session, shipment_id, organization_id=org)
    return document_service.export_draft(session, shipment_id, kind, as_pdf=as_pdf)
