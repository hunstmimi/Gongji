from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter

from ...services.dev_service import release_cabinets


router = APIRouter(tags=["dev"])


class ReleaseCabinetsRequest(BaseModel):
    card_type: str | None = None
    cabinet_type: str | None = None
    count: int = Field(default=1, ge=1)
    from_statuses: list[str] | None = None


@router.post("/dev/release-cabinets")
def release_cabinets_route(payload: ReleaseCabinetsRequest) -> dict:
    return release_cabinets(
        card_type=payload.card_type,
        cabinet_type=payload.cabinet_type,
        count=payload.count,
        from_statuses=payload.from_statuses,
    )
