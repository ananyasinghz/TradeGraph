"""Shipment document statuses, draft exports, uploads, and why-required."""

from __future__ import annotations

import base64
import hashlib
import io
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from backend.app.core.config import Settings, get_settings
from backend.app.core.errors import AppError
from backend.app.data.models import DocumentRequirement, DocumentUpload, Shipment, ShipmentChecklist
from backend.app.domain.trade import (
    ChecklistItemOut,
    ChecklistItemStatusUpdate,
    DocStatus,
    DocumentFormField,
    DocumentFormOut,
    DocumentUploadOut,
    DocWhyRequiredOut,
    DraftExportOut,
    ShipmentOut,
)
from backend.app.services import pdf_util, retrieval_service

DraftKind = Literal["commercial_invoice", "packing_list", "checklist"]
_VALID_STATUS: set[str] = {"not_started", "draft", "needs_review", "ready"}
_DOC_CODE_SAFE = re.compile(r"[^a-zA-Z0-9._-]+")


def _safe_doc_code(doc_code: str) -> str:
    cleaned = _DOC_CODE_SAFE.sub("_", (doc_code or "").strip())
    return cleaned[:64] or "document"


def _now() -> datetime:
    return datetime.now(UTC)


def _progress(items: list[ChecklistItemOut]) -> str:
    ready = sum(1 for i in items if i.status == "ready" or i.done)
    return f"{ready}/{len(items)}"


def normalize_checklist_item(raw: dict[str, Any]) -> ChecklistItemOut:
    status_raw = raw.get("status")
    done = bool(raw.get("done", False))
    status: DocStatus
    if isinstance(status_raw, str) and status_raw in _VALID_STATUS:
        status = status_raw  # type: ignore[assignment]
    else:
        status = "ready" if done else "not_started"
    done = status == "ready"
    return ChecklistItemOut(
        doc_code=str(raw.get("doc_code") or ""),
        doc_label=str(raw.get("doc_label") or raw.get("doc_code") or ""),
        required=bool(raw.get("required", True)),
        notes=raw.get("notes"),
        done=done,
        status=status,
    )


def _latest_checklist(session: Session, shipment_id: str) -> ShipmentChecklist | None:
    return session.scalars(
        select(ShipmentChecklist)
        .where(ShipmentChecklist.shipment_id == shipment_id)
        .order_by(ShipmentChecklist.updated_at.desc())
    ).first()


def _upload_out(row: DocumentUpload) -> DocumentUploadOut:
    return DocumentUploadOut(
        id=row.id,
        shipment_id=row.shipment_id,
        doc_code=row.doc_code,
        filename=row.filename,
        content_type=row.content_type,
        checksum=row.checksum,
        uploaded_at=row.uploaded_at,
        uploaded_by=row.uploaded_by,
        notes=row.notes,
        storage_path=row.storage_path,
    )


def list_uploads(session: Session, shipment_id: str) -> list[DocumentUploadOut]:
    rows = session.scalars(
        select(DocumentUpload)
        .where(DocumentUpload.shipment_id == shipment_id)
        .order_by(DocumentUpload.uploaded_at.desc())
    ).all()
    return [_upload_out(r) for r in rows]


def upload_document(
    session: Session,
    shipment_id: str,
    *,
    doc_code: str,
    filename: str,
    content: bytes,
    content_type: str = "application/octet-stream",
    uploaded_by: str | None = None,
    notes: str | None = None,
    mark_ready: bool = True,
    settings: Settings | None = None,
) -> DocumentUploadOut:
    row = session.get(Shipment, shipment_id)
    if row is None:
        raise AppError(code="SHIPMENT_NOT_FOUND", message="Shipment not found", status_code=404)
    # Any non-empty doc_code is accepted (checklist membership is optional).
    raw_code = (doc_code or "").strip()
    if not raw_code:
        raise AppError(
            code="DOC_CODE_REQUIRED",
            message="doc_code is required for uploads",
            status_code=400,
        )
    path_code = _safe_doc_code(raw_code)
    resolved = settings or get_settings()
    max_bytes = resolved.upload_max_bytes
    if len(content) > max_bytes:
        raise AppError(
            code="UPLOAD_TOO_LARGE",
            message=f"Upload exceeds max size of {max_bytes} bytes",
            status_code=413,
        )
    from backend.app.services import av_scan

    av_scan.scan_upload(content, filename=filename, settings=resolved)
    safe_name = filename.replace("/", "_").replace("\\", "_")
    ext = Path(safe_name).suffix.lower().lstrip(".")
    allowed = {
        e.strip().lower()
        for e in (resolved.upload_allowed_extensions or "").split(",")
        if e.strip()
    }
    if allowed and ext not in allowed:
        raise AppError(
            code="UPLOAD_TYPE_NOT_ALLOWED",
            message=f"File type .{ext or '?'} not allowed. Allowed: {', '.join(sorted(allowed))}",
            status_code=415,
        )
    dest_dir = Path(resolved.data_dir) / "uploads" / shipment_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    checksum = hashlib.sha256(content).hexdigest()
    storage = dest_dir / f"{path_code}_{checksum[:12]}_{safe_name}"
    storage.write_bytes(content)
    upload = DocumentUpload(
        shipment_id=shipment_id,
        doc_code=raw_code,
        filename=safe_name,
        content_type=content_type or "application/octet-stream",
        storage_path=str(storage),
        checksum=checksum,
        uploaded_at=_now(),
        uploaded_by=uploaded_by,
        notes=notes,
    )
    session.add(upload)
    if mark_ready:
        checklist = _latest_checklist(session, shipment_id)
        if checklist is not None:
            items = [normalize_checklist_item(i) for i in checklist.items_json or []]
            updated: list[ChecklistItemOut] = []
            for item in items:
                if item.doc_code == raw_code:
                    updated.append(
                        ChecklistItemOut(
                            doc_code=item.doc_code,
                            doc_label=item.doc_label,
                            required=item.required,
                            notes=item.notes,
                            status="ready",
                            done=True,
                        )
                    )
                else:
                    updated.append(item)
            checklist.items_json = [i.model_dump(mode="json") for i in updated]
            checklist.progress = _progress(updated)
            checklist.updated_at = _now()
    row.updated_at = _now()
    session.flush()
    return _upload_out(upload)


def document_form(session: Session, shipment_id: str, kind: str) -> DocumentFormOut:
    from backend.app.services import shipment_service

    detail = shipment_service.get_shipment(session, shipment_id)
    disclaimer = "Prototype form only — not an official customs filing."
    if kind == "commercial_invoice":
        return DocumentFormOut(
            kind="commercial_invoice",
            title="Commercial invoice form",
            fields=[
                DocumentFormField(name="title", label="Shipment", value=detail.title),
                DocumentFormField(name="origin", label="Origin", value=detail.origin),
                DocumentFormField(
                    name="destination", label="Destination", value=detail.destination
                ),
                DocumentFormField(
                    name="product_text",
                    label="Product",
                    value=detail.product_text,
                    required=True,
                ),
                DocumentFormField(
                    name="hs_code_working",
                    label="HS",
                    value=detail.hs_code_working,
                    required=True,
                ),
                DocumentFormField(
                    name="invoice_value",
                    label="Invoice value",
                    value=str(detail.invoice_value),
                    required=True,
                ),
                DocumentFormField(name="currency", label="Currency", value=detail.currency),
                DocumentFormField(name="incoterm", label="Incoterm", value=detail.incoterm),
            ],
            disclaimer=disclaimer,
        )
    if kind == "packing_list":
        return DocumentFormOut(
            kind="packing_list",
            title="Packing list form",
            fields=[
                DocumentFormField(name="title", label="Shipment", value=detail.title),
                DocumentFormField(
                    name="product_text", label="Description", value=detail.product_text
                ),
                DocumentFormField(name="qty", label="Quantity", value=str(detail.qty)),
                DocumentFormField(name="marks", label="Carton marks", value="TBD"),
            ],
            disclaimer=disclaimer,
        )
    if kind == "certificate_of_origin":
        return DocumentFormOut(
            kind="certificate_of_origin",
            title="Certificate of origin (placeholder form)",
            fields=[
                DocumentFormField(name="exporter", label="Exporter", value="TBD", required=True),
                DocumentFormField(name="importer", label="Importer", value="TBD", required=True),
                DocumentFormField(
                    name="hs_code_working",
                    label="HS",
                    value=detail.hs_code_working,
                    required=True,
                ),
                DocumentFormField(
                    name="origin_criteria",
                    label="Origin criteria",
                    value="Wholly obtained / CTSH (assert in FTA check)",
                    required=True,
                ),
            ],
            disclaimer=disclaimer,
        )
    raise AppError(
        code="FORM_KIND_UNKNOWN", message=f"Unknown form kind: {kind}", status_code=400
    )


def update_document_status(
    session: Session,
    shipment_id: str,
    doc_code: str,
    payload: ChecklistItemStatusUpdate,
) -> ShipmentOut:
    from backend.app.services import shipment_service

    row = session.get(Shipment, shipment_id)
    if row is None:
        raise AppError(code="SHIPMENT_NOT_FOUND", message="Shipment not found", status_code=404)
    checklist = _latest_checklist(session, shipment_id)
    if checklist is None:
        raise AppError(
            code="CHECKLIST_NOT_FOUND",
            message="Build a checklist before updating document status",
            status_code=404,
        )

    items = [normalize_checklist_item(i) for i in checklist.items_json or []]
    found = False
    updated: list[ChecklistItemOut] = []
    for item in items:
        if item.doc_code == doc_code:
            found = True
            updated.append(
                ChecklistItemOut(
                    doc_code=item.doc_code,
                    doc_label=item.doc_label,
                    required=item.required,
                    notes=item.notes,
                    status=payload.status,
                    done=payload.status == "ready",
                )
            )
        else:
            updated.append(item)
    if not found:
        raise AppError(
            code="DOCUMENT_NOT_FOUND",
            message=f"Document {doc_code} not on this shipment checklist",
            status_code=404,
        )

    checklist.items_json = [i.model_dump(mode="json") for i in updated]
    checklist.progress = _progress(updated)
    checklist.updated_at = _now()
    row.updated_at = _now()
    session.flush()
    return shipment_service.get_shipment(session, shipment_id)


def why_required(
    session: Session,
    *,
    doc_code: str,
    origin: str = "BD",
    destination: str = "IN",
    hs_code: str | None = None,
) -> DocWhyRequiredOut:
    filters = [
        DocumentRequirement.origin == origin.upper(),
        DocumentRequirement.destination == destination.upper(),
        DocumentRequirement.doc_code == doc_code,
    ]
    if hs_code:
        filters.append(
            or_(DocumentRequirement.hs_code.is_(None), DocumentRequirement.hs_code == hs_code)
        )
    row = session.scalars(select(DocumentRequirement).where(*filters)).first()
    if row is None:
        row = session.scalars(
            select(DocumentRequirement).where(
                DocumentRequirement.origin == origin.upper(),
                DocumentRequirement.destination == destination.upper(),
                DocumentRequirement.doc_code == doc_code,
            )
        ).first()
    if row is None:
        raise AppError(
            code="DOCUMENT_REQUIREMENT_NOT_FOUND",
            message=f"No requirement template for {doc_code}",
            status_code=404,
        )

    notes = row.notes or ""
    why_parts = [
        f"“{row.doc_label}” is listed for the {row.origin}→{row.destination} corridor"
        + (f" (HS {row.hs_code})" if row.hs_code else " (corridor-wide)")
        + (" as required." if row.required else " as optional/recommended.")
    ]
    if notes:
        why_parts.append(notes)
    else:
        why_parts.append(
            "Keep a complete file so clearance can proceed without last-minute document gaps."
        )

    query = f"{row.doc_label} {row.doc_code} required documents {notes}".strip()
    hits = retrieval_service.search_chunks(
        session, query=query, hs_code=hs_code or row.hs_code, top_k=1
    )
    excerpt = hits[0].text if hits else None
    source_id = hits[0].source_document_id if hits else None
    source_tip = (
        f"Related excerpt from {source_id}."
        if source_id
        else "No retrieval hit yet — rely on the template notes and official sources."
    )

    return DocWhyRequiredOut(
        doc_code=row.doc_code,
        doc_label=row.doc_label,
        required=bool(row.required),
        notes=row.notes,
        why=" ".join(why_parts),
        source_tip=source_tip,
        retrieval_excerpt=excerpt,
        retrieval_source_id=source_id,
    )


def export_draft(
    session: Session,
    shipment_id: str,
    kind: DraftKind,
    *,
    as_pdf: bool = False,
) -> DraftExportOut:
    from backend.app.services import shipment_service

    detail = shipment_service.get_shipment(session, shipment_id)
    stamp = detail.as_of_date.isoformat()
    if kind == "commercial_invoice":
        text = "\n".join(
            [
                "COMMERCIAL INVOICE (DRAFT — illustrative)",
                f"Shipment: {detail.title}",
                f"Date / as-of: {stamp}",
                f"Seller origin: {detail.origin}",
                f"Buyer destination: {detail.destination}",
                f"Incoterm: {detail.incoterm}",
                f"Product: {detail.product_text}",
                f"HS (working): {detail.hs_code_working or 'TBD'}",
                f"Quantity: {detail.qty}",
                f"Invoice value: {detail.invoice_value} {detail.currency}",
                "",
                "Notes: Prototype draft only. Not a customs filing.",
            ]
        )
        filename = f"invoice-{detail.id[:8]}.txt"
        title = "Commercial Invoice Draft"
    elif kind == "packing_list":
        text = "\n".join(
            [
                "PACKING LIST (DRAFT — illustrative)",
                f"Shipment: {detail.title}",
                f"Date / as-of: {stamp}",
                f"Corridor: {detail.origin} → {detail.destination}",
                f"Product description: {detail.product_text}",
                f"HS (working): {detail.hs_code_working or 'TBD'}",
                f"Packages / qty: {detail.qty}",
                f"Declared value reference: {detail.invoice_value} {detail.currency}",
                "",
                "Carton marks: TBD",
                "Gross / net weight: TBD",
                "",
                "Notes: Prototype draft only. Confirm weights and marks before use.",
            ]
        )
        filename = f"packing-list-{detail.id[:8]}.txt"
        title = "Packing List Draft"
    else:
        if detail.checklist is None:
            raise AppError(
                code="CHECKLIST_NOT_FOUND",
                message="Build a checklist before exporting it",
                status_code=404,
            )
        lines = [
            "DOCUMENT CHECKLIST (DRAFT EXPORT)",
            f"Shipment: {detail.title}",
            f"Corridor: {detail.origin} → {detail.destination}",
            f"HS: {detail.hs_code_working or 'TBD'}",
            f"Progress: {detail.checklist.progress}",
            "",
        ]
        for item in detail.checklist.items:
            mark = "[x]" if item.status == "ready" or item.done else "[ ]"
            req = "required" if item.required else "optional"
            lines.append(
                f"{mark} {item.doc_label} ({item.doc_code}) — {item.status} · {req}"
            )
            if item.notes:
                lines.append(f"    notes: {item.notes}")
        lines.append("")
        lines.append("Notes: Statuses are workspace tracking only.")
        text = "\n".join(lines)
        filename = f"checklist-{detail.id[:8]}.txt"
        title = "Checklist Draft"

    if as_pdf:
        pdf_bytes = pdf_util.text_to_pdf(title, text)
        return DraftExportOut(
            kind=kind,
            filename=filename.replace(".txt", ".pdf"),
            text=text,
            content_type="application/pdf",
            pdf_base64=base64.b64encode(pdf_bytes).decode("ascii"),
        )
    return DraftExportOut(kind=kind, filename=filename, text=text)


_PACK_DISCLAIMER = """\
TradeGraph clearance pack — DISCLAIMER

This ZIP contains prototype drafts and uploaded workspace files only.
It is not an official customs filing and must not be treated as a
government-approved submission package.

Verify all HS codes, duty rates, FTA evidence, and document originals
with a licensed broker or competent authority before use.
"""


def build_clearance_pack(session: Session, shipment_id: str) -> bytes:
    """Build a ZIP with draft forms, checklist, uploads, and DISCLAIMER.txt."""
    row = session.get(Shipment, shipment_id)
    if row is None:
        raise AppError(code="SHIPMENT_NOT_FOUND", message="Shipment not found", status_code=404)

    checklist = _latest_checklist(session, shipment_id)
    if checklist is None:
        from backend.app.services import shipment_service

        shipment_service.build_shipment_checklist(session, shipment_id)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("DISCLAIMER.txt", _PACK_DISCLAIMER)
        for kind in ("commercial_invoice", "packing_list", "checklist"):
            draft = export_draft(session, shipment_id, kind, as_pdf=False)  # type: ignore[arg-type]
            zf.writestr(f"drafts/{draft.filename}", draft.text or "")
        uploads = session.scalars(
            select(DocumentUpload)
            .where(DocumentUpload.shipment_id == shipment_id)
            .order_by(DocumentUpload.uploaded_at.asc())
        ).all()
        for upload in uploads:
            path = Path(upload.storage_path) if upload.storage_path else None
            arcname = f"uploads/{upload.doc_code}_{upload.filename}"
            if path is not None and path.is_file():
                zf.write(path, arcname=arcname)
            else:
                zf.writestr(
                    arcname + ".missing.txt",
                    f"Upload {upload.id} referenced but file not found on disk.\n",
                )
    return buf.getvalue()
