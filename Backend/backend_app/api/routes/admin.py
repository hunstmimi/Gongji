from __future__ import annotations

from fastapi import APIRouter, Depends

from ...dependencies import get_current_admin_user
from ...services.admin_service import get_usage_overview


router = APIRouter(tags=["admin"])


@router.get("/admin/usage")
def get_admin_usage_route(_: dict = Depends(get_current_admin_user)) -> dict:
    return get_usage_overview()
