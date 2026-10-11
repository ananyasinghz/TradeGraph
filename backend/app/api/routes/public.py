"""Unauthenticated public share endpoints (clearance R11)."""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.api.dependencies import SessionDep
from backend.app.domain.trade import PublicShareOut
from backend.app.services import share_service

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/share/{token}", response_model=PublicShareOut)
def public_share(token: str, session: SessionDep) -> PublicShareOut:
    return share_service.get_public_share(session, token)
