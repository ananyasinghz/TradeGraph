"""Corridor and country coverage APIs (IF-3 / IF-10)."""

from __future__ import annotations

from fastapi import APIRouter, Query

from backend.app.api.dependencies import SessionDep
from backend.app.domain.trade import (
    CorridorOut,
    CountryOut,
    OrganizationOut,
    SourceCoverageOut,
)
from backend.app.services import corridor_service, org_service

router = APIRouter(tags=["corridors"])


@router.get("/organizations", response_model=list[OrganizationOut])
def get_organizations(session: SessionDep) -> list[OrganizationOut]:
    return org_service.list_organizations(session)


@router.get("/countries", response_model=list[CountryOut])
def get_countries(session: SessionDep) -> list[CountryOut]:
    corridor_service.ensure_default_corridors(session)
    return corridor_service.list_countries(session)


@router.get("/corridors", response_model=list[CorridorOut])
def get_corridors(session: SessionDep) -> list[CorridorOut]:
    corridor_service.ensure_default_corridors(session)
    return corridor_service.list_corridors(session)


@router.get("/source-coverage", response_model=list[SourceCoverageOut])
def get_source_coverage(
    session: SessionDep,
    corridor_id: str | None = Query(default=None),
    capability: str | None = Query(default=None),
) -> list[SourceCoverageOut]:
    corridor_service.ensure_default_corridors(session)
    return corridor_service.list_coverage(
        session, corridor_id=corridor_id, capability=capability
    )
