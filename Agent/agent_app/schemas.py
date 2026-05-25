from __future__ import annotations

from pydantic import BaseModel, Field


class CreateInstanceRequest(BaseModel):
    rental_id: int
    instance_id: str
    container_name: str | None = None
    gpu_indices: list[int] = Field(min_length=1)
    image: str
    username: str = "root"
    password: str
    ssh_port: int
    cpu_limit: float | None = None
    memory_limit_gb: int | None = None
    shm_size: str = "16g"


class InstanceRecord(BaseModel):
    instance_id: str
    container_name: str
    host: str
    ssh_port: int
    username: str
    password: str
    command: str
    gpu_indices: list[int]
    image: str
    status: str
    provisioning_status: str


class ApiResponse(BaseModel):
    success: bool = True

