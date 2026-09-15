"""IF-11b: promote CBIC fixture → ingest → approve → publish."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.core.errors import AppError
from backend.app.domain.trade import PromoteCbicResult
from backend.app.ingestion import approval, pipeline
from backend.app.services import cost_service


def promote_cbic_fixture(
    session: Session,
    *,
    source_code: str = "CBIC_NOTIFICATION_2026_Q3",
    force: bool = True,
    notes: str | None = None,
) -> PromoteCbicResult:
    """
    Run the full honest demo path:
    curated CBIC fixture → ingest/validate → approve & publish verified rates.
    Approve supersedes active illustrative rates for the same HS/corridor.
    """
    result = pipeline.run(session, source_code, force=force)
    batch = result.batch
    if batch is None:
        raise AppError(
            code="PROMOTE_INGEST_FAILED",
            message="CBIC fixture ingest did not produce a review batch",
            status_code=500,
        )
    if batch.status != "pending_review":
        result = pipeline.run(session, source_code, force=True)
        batch = result.batch
        if batch is None or batch.status != "pending_review":
            raise AppError(
                code="PROMOTE_NO_PENDING_BATCH",
                message=(
                    f"Expected pending_review batch, got "
                    f"{batch.status if batch else None}"
                ),
                status_code=409,
            )

    approved = approval.approve(
        session,
        batch.id,
        notes=notes or "IF-11b promote CBIC fixture to verified",
    )
    rates_published = sum(
        1
        for p in approved.proposals
        if p.kind == "tariff_rate" and p.publish_status == "published"
    )
    return PromoteCbicResult(
        batch_id=approved.id,
        data_version_id=approved.data_version_id,
        published_source_id=approved.published_source_id,
        rates_published=rates_published,
        approved_tariff_rule_count=cost_service.approved_tariff_rule_count(session),
        message=(
            "CBIC fixture approved and published. Tariff lookup now prefers "
            "verified rates. Customs mode is available when freight and insurance "
            "are set on a scenario."
        ),
    )
