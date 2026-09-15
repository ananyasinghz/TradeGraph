"""HS classification candidate routes."""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.api.auth_deps import ViewerDep
from backend.app.api.dependencies import SessionDep
from backend.app.domain.trade import (
    ClassificationCandidatesOut,
    ClassificationSuggestRequest,
)
from backend.app.services import classification_service

router = APIRouter(prefix="/classification", tags=["classification"])


@router.post("/candidates", response_model=ClassificationCandidatesOut)
def suggest_candidates(
    payload: ClassificationSuggestRequest,
    session: SessionDep,
    _principal: ViewerDep,
) -> ClassificationCandidatesOut:
    return classification_service.suggest_candidates(
        session,
        product_text=payload.product_text,
        chapter=payload.chapter,
        limit=payload.limit,
    )
