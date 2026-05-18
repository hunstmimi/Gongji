from __future__ import annotations

from fastapi import APIRouter

from ...services.location_service import get_locations_summary


router = APIRouter(tags=["locations"])


@router.get("/locations/summary")
def locations_summary() -> dict:
    return get_locations_summary()
