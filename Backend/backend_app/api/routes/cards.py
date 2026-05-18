from __future__ import annotations

from fastapi import APIRouter

from ...services.catalog_service import get_cards


router = APIRouter(tags=["cards"])


@router.get("/cards")
def list_cards() -> dict:
    return get_cards()
