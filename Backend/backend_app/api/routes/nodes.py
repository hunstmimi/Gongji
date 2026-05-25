from __future__ import annotations

from fastapi import APIRouter, Header

from ...config import resolve_agent_token
from ...errors import AppError
from ...schemas import NodeHeartbeatRequest
from ...services.node_status_service import ingest_node_heartbeat


router = APIRouter(tags=["nodes"])


def _require_agent_token(authorization: str | None) -> None:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or token != resolve_agent_token():
        raise AppError("UNAUTHORIZED_AGENT", "节点 Agent 认证失败", 401)


@router.post("/nodes/heartbeat")
def node_heartbeat_route(payload: NodeHeartbeatRequest, authorization: str | None = Header(default=None)) -> dict:
    _require_agent_token(authorization)
    return ingest_node_heartbeat(payload)
