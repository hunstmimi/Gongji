from __future__ import annotations

from fastapi import APIRouter, Depends

from ...dependencies import get_current_admin_user
from ...schemas import AdminCreateMachineRequest, AdminMachineAccessRequest
from ...services.admin_machine_deploy_service import deploy_agent, probe_machine
from ...services.admin_machine_service import create_machine, list_machines
from ...services.admin_service import get_usage_overview


router = APIRouter(tags=["admin"])


@router.get("/admin/usage")
def get_admin_usage_route(_: dict = Depends(get_current_admin_user)) -> dict:
    return get_usage_overview()


@router.get("/admin/machines")
def get_admin_machines_route(_: dict = Depends(get_current_admin_user)) -> dict:
    return list_machines()


@router.post("/admin/machines")
def create_admin_machine_route(payload: AdminCreateMachineRequest, _: dict = Depends(get_current_admin_user)) -> dict:
    return create_machine(payload)


@router.post("/admin/machines/probe")
def probe_admin_machine_route(payload: AdminMachineAccessRequest, _: dict = Depends(get_current_admin_user)) -> dict:
    return probe_machine(payload)


@router.post("/admin/machines/deploy-agent")
def deploy_admin_machine_agent_route(payload: AdminMachineAccessRequest, _: dict = Depends(get_current_admin_user)) -> dict:
    return deploy_agent(payload)
