from __future__ import annotations

from pydantic import BaseModel, Field


class CreateRentalRequest(BaseModel):
    card_type: str
    cabinet_type: str
    card_count: int = Field(ge=1)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    phone: str | None = Field(default=None, max_length=32)
    nickname: str | None = Field(default=None, max_length=64)


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)


class RechargeRequest(BaseModel):
    amount: float = Field(gt=0)
