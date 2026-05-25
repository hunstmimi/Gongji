from __future__ import annotations

from pydantic import BaseModel, Field


class CreateRentalRequest(BaseModel):
    card_type: str
    cabinet_type: str
    card_count: int = Field(ge=1)
    preferred_cabinet_code: str | None = Field(default=None, max_length=128)
    preferred_location: str | None = Field(default=None, max_length=128)


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


class NodeDeviceReport(BaseModel):
    index: int = Field(ge=0)
    name: str | None = None
    health: str | None = None
    usage_percent: float | None = None
    memory_used_mb: int | None = None
    memory_total_mb: int | None = None
    hbm_used_mb: int | None = None
    hbm_total_mb: int | None = None
    process_count: int = Field(default=0, ge=0)
    raw: str | None = None


class NodeContainerReport(BaseModel):
    instance_id: str | None = None
    container_name: str | None = None
    status: str | None = None
    device_indices: list[int] = Field(default_factory=list)
    ssh_port: int | None = None


class NodeHeartbeatRequest(BaseModel):
    node_id: str = Field(min_length=1, max_length=128)
    host_ip: str = Field(min_length=1, max_length=128)
    accelerator_type: str = Field(default="ascend", max_length=32)
    reported_at: str | None = None
    devices: list[NodeDeviceReport] = Field(default_factory=list)
    containers: list[NodeContainerReport] = Field(default_factory=list)
    raw: str | None = None
