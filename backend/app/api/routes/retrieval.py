"""Regulatory retrieval route."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from backend.app.api.dependencies import SessionDep
from backend.app.domain.trade import RetrievalHit
from backend.app.services import retrieval_service

router = APIRouter(tags=["retrieval"])


@router.get("/retrieve", response_model=list[RetrievalHit])
def retrieve(
    session: SessionDep,
    q: Annotated[str, Query(min_length=1)],
    hs: Annotated[str | None, Query()] = None,
    top_k: Annotated[int, Query(ge=1, le=20)] = 5,
) -> list[RetrievalHit]:
    return retrieval_service.search_chunks(session, query=q, hs_code=hs, top_k=top_k)
