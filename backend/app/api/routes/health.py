"""Service health and readiness endpoints."""

from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text

from backend.app.api.dependencies import settings_from_request
from backend.app.core.config import Settings
from backend.app.domain.base import ContractModel

router = APIRouter(tags=["system"])


class HealthResponse(ContractModel):
    """Stable health-check response."""

    status: Literal["ok"] = "ok"
    service: str
    version: str
    environment: str
    contract_version: Literal["trade.v1"]
    timestamp: datetime
    prototype_corridor: str


class ReadinessResponse(ContractModel):
    status: Literal["ready", "not_ready"]
    database: Literal["ok", "error"]
    detail: str | None = None


@router.get("/health", response_model=HealthResponse)
async def health(
    settings: Annotated[Settings, Depends(settings_from_request)],
) -> HealthResponse:
    """Report process health without touching data dependencies."""
    return HealthResponse(
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        contract_version=settings.contract_version,
        timestamp=datetime.now(UTC),
        prototype_corridor=(
            f"{settings.default_origin}->{settings.default_destination} "
            f"HS ch.{settings.prototype_hs_chapter}"
        ),
    )


@router.get("/ready", response_model=ReadinessResponse)
def ready(request: Request) -> ReadinessResponse:
    """DB readiness probe for Compose / orchestration."""
    try:
        engine = request.app.state.engine
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return ReadinessResponse(status="ready", database="ok")
    except Exception as exc:
        return ReadinessResponse(
            status="not_ready",
            database="error",
            detail=str(exc.__class__.__name__),
        )
