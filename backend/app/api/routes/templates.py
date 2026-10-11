"""Product template CRUD (clearance R8)."""

from __future__ import annotations

from fastapi import APIRouter, Header

from backend.app.api.auth_deps import OperatorDep
from backend.app.api.dependencies import SessionDep, SettingsDep
from backend.app.domain.trade import (
    ProductTemplateCreate,
    ProductTemplateOut,
    ProductTemplateUpdate,
)
from backend.app.services import product_template_service
from backend.app.services.auth_service import resolve_organization_id

router = APIRouter(prefix="/product-templates", tags=["product-templates"])


@router.get("", response_model=list[ProductTemplateOut])
def list_templates(
    session: SessionDep,
    settings: SettingsDep,
    principal: OperatorDep,
    x_organization_id: str | None = Header(default=None),
) -> list[ProductTemplateOut]:
    org = resolve_organization_id(settings, principal, x_organization_id)
    return product_template_service.list_templates(session, organization_id=org)


@router.post("", response_model=ProductTemplateOut)
def create_template(
    payload: ProductTemplateCreate,
    session: SessionDep,
    settings: SettingsDep,
    principal: OperatorDep,
    x_organization_id: str | None = Header(default=None),
) -> ProductTemplateOut:
    org = resolve_organization_id(settings, principal, x_organization_id)
    return product_template_service.create_template(
        session, payload, organization_id=org
    )


@router.patch("/{template_id}", response_model=ProductTemplateOut)
def patch_template(
    template_id: str,
    payload: ProductTemplateUpdate,
    session: SessionDep,
    settings: SettingsDep,
    principal: OperatorDep,
    x_organization_id: str | None = Header(default=None),
) -> ProductTemplateOut:
    org = resolve_organization_id(settings, principal, x_organization_id)
    return product_template_service.update_template(
        session, template_id, payload, organization_id=org
    )
