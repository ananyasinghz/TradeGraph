"""Tariff and HS code routes."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from backend.app.api.auth_deps import ViewerDep
from backend.app.api.dependencies import SessionDep
from backend.app.domain.trade import HsCodeOut, TariffLookupOut, TariffRateOut
from backend.app.services import tariff_service

router = APIRouter(tags=["tariffs"])


@router.get("/hs-codes", response_model=list[HsCodeOut])
def list_hs_codes(
    session: SessionDep,
    _principal: ViewerDep,
    q: Annotated[str | None, Query()] = None,
    chapter: Annotated[str | None, Query()] = None,
) -> list[HsCodeOut]:
    return tariff_service.search_hs_codes(session, q=q, chapter=chapter)


@router.get("/tariffs/lookup", response_model=TariffLookupOut)
def lookup_tariff(
    session: SessionDep,
    _principal: ViewerDep,
    hs: Annotated[str, Query()],
    as_of: Annotated[date, Query()],
    origin: Annotated[str, Query()] = "BD",
    destination: Annotated[str, Query()] = "IN",
    regime: Annotated[str | None, Query()] = None,
) -> TariffLookupOut:
    return tariff_service.lookup_tariff(
        session,
        hs_code=hs,
        origin=origin,
        destination=destination,
        as_of=as_of,
        regime=regime,
    )


@router.get("/tariffs", response_model=list[TariffRateOut])
def list_tariffs(
    session: SessionDep,
    _principal: ViewerDep,
    hs: Annotated[str | None, Query()] = None,
    origin: Annotated[str | None, Query()] = None,
    destination: Annotated[str | None, Query()] = None,
    as_of: Annotated[date | None, Query()] = None,
    include_history: Annotated[bool, Query()] = False,
    agreement_id: Annotated[str | None, Query()] = None,
) -> list[TariffRateOut]:
    return tariff_service.list_tariffs(
        session,
        hs_code=hs,
        origin=origin,
        destination=destination,
        as_of=as_of,
        include_history=include_history,
        agreement_id=agreement_id,
    )


@router.get("/tariffs/{tariff_id}", response_model=TariffRateOut)
def get_tariff(
    tariff_id: str, session: SessionDep, _principal: ViewerDep
) -> TariffRateOut:
    return tariff_service.get_tariff(session, tariff_id)


@router.get("/tariffs/{tariff_id}/history", response_model=list[TariffRateOut])
def tariff_history(
    tariff_id: str, session: SessionDep, _principal: ViewerDep
) -> list[TariffRateOut]:
    return tariff_service.get_tariff_history(session, tariff_id)
