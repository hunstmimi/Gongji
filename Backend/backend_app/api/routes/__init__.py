from fastapi import APIRouter

from .auth import router as auth_router
from .cards import router as cards_router
from .dev import router as dev_router
from .locations import router as locations_router
from .me import router as me_router
from .rentals import router as rentals_router


api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(me_router)
api_router.include_router(locations_router)
api_router.include_router(cards_router)
api_router.include_router(rentals_router)
api_router.include_router(dev_router)
