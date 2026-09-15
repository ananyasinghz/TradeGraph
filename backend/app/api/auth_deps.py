"""Shared FastAPI auth dependency aliases."""

from typing import Annotated

from fastapi import Depends

from backend.app.services.auth_service import Principal, require_role

ViewerDep = Annotated[Principal, Depends(require_role("viewer"))]
OperatorDep = Annotated[Principal, Depends(require_role("operator"))]
ReviewerDep = Annotated[Principal, Depends(require_role("reviewer"))]
AdminDep = Annotated[Principal, Depends(require_role("admin"))]
