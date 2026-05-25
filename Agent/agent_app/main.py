from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException

from .auth import require_agent_token
from .config import resolve_dry_run
from .heartbeat import start_heartbeat_loop
from .runtime import RuntimeErrorResponse, get_runtime, validate_payload
from .schemas import ApiResponse, CreateInstanceRequest


app = FastAPI(title="GongJi Node Agent", version="0.1.0")
runtime = get_runtime()


@app.on_event("startup")
def startup() -> None:
    start_heartbeat_loop(runtime)


@app.get("/api/health")
def health() -> dict:
    return {
        "success": True,
        "service": "gongji-agent",
        "dry_run": resolve_dry_run(),
    }


@app.post("/api/instances", dependencies=[Depends(require_agent_token)])
def create_instance(payload: CreateInstanceRequest) -> dict:
    try:
        validate_payload(payload)
        record = runtime.create_instance(payload)
    except RuntimeErrorResponse as exc:
        raise HTTPException(status_code=400, detail={"code": "INSTANCE_CREATE_FAILED", "message": str(exc)}) from exc
    return {"success": True, **record.model_dump()}


@app.get("/api/instances/{instance_id}", dependencies=[Depends(require_agent_token)])
def get_instance(instance_id: str) -> dict:
    record = runtime.get_instance(instance_id)
    if not record:
        raise HTTPException(status_code=404, detail={"code": "INSTANCE_NOT_FOUND", "message": "instance not found"})
    return {"success": True, **record.model_dump()}


@app.post("/api/instances/{instance_id}/stop", dependencies=[Depends(require_agent_token)])
def stop_instance(instance_id: str) -> dict:
    try:
        record = runtime.stop_instance(instance_id)
    except RuntimeErrorResponse as exc:
        raise HTTPException(status_code=400, detail={"code": "INSTANCE_STOP_FAILED", "message": str(exc)}) from exc
    return {"success": True, **record.model_dump()}


@app.get("/api/gpus", dependencies=[Depends(require_agent_token)])
def list_gpus() -> dict:
    return {"success": True, **runtime.list_devices()}
