from __future__ import annotations

from fastapi import APIRouter, Depends

from ...dependencies import get_current_user
from ...schemas import CreateRentalRequest
from ...services.rental_service import cancel_rental, create_rental, get_rental


router = APIRouter(tags=["rentals"])


@router.post("/rentals")
def create_rental_route(payload: CreateRentalRequest, user: dict = Depends(get_current_user)) -> dict:
    return create_rental(
        user_id=user["id"],
        card_type=payload.card_type,
        cabinet_type=payload.cabinet_type,
        card_count=payload.card_count,
    )


@router.get("/rentals/{rental_id}")
def get_rental_route(rental_id: int, user: dict = Depends(get_current_user)) -> dict:
    return get_rental(rental_id, user["id"])


@router.post("/rentals/{rental_id}/cancel")
def cancel_rental_route(rental_id: int, user: dict = Depends(get_current_user)) -> dict:
    return cancel_rental(rental_id, user["id"])
