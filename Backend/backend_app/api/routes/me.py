from __future__ import annotations

from fastapi import APIRouter, Depends

from ...dependencies import get_current_user
from ...schemas import RechargeRequest
from ...services.auth_service import serialize_user
from ...services.profile_service import (
    get_active_rentals,
    get_dashboard,
    get_history_rentals,
    recharge_balance,
)


router = APIRouter(tags=["me"])


@router.get("/me")
def get_me_route(user: dict = Depends(get_current_user)) -> dict:
    return {"success": True, "user": serialize_user(user)}


@router.get("/me/dashboard")
def get_dashboard_route(user: dict = Depends(get_current_user)) -> dict:
    return get_dashboard(user)


@router.get("/me/rentals/active")
def get_active_rentals_route(user: dict = Depends(get_current_user)) -> dict:
    return {"success": True, "items": get_active_rentals(user["id"])}


@router.get("/me/rentals/history")
def get_history_rentals_route(user: dict = Depends(get_current_user)) -> dict:
    return {"success": True, "items": get_history_rentals(user["id"])}


@router.post("/me/balance/recharge")
def recharge_balance_route(
    payload: RechargeRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    return recharge_balance(user["id"], payload.amount)
