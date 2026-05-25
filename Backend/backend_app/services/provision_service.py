from __future__ import annotations

import hashlib
import json
from urllib import request as urllib_request

from ..config import (
    resolve_agent_base_url,
    resolve_agent_ascend_image,
    resolve_agent_default_image,
    resolve_agent_dry_run,
    resolve_agent_nvidia_image,
    resolve_agent_port,
    resolve_agent_token,
    resolve_cpu_per_card,
    resolve_memory_per_card_gb,
    resolve_rental_ssh_password_seed,
    resolve_rental_ssh_port_base,
    resolve_rental_ssh_username_prefix,
    resolve_shm_per_card_gb,
)
from ..errors import AppError


def _environment_id(rental_id: int, allocation_index: int) -> str:
    return f"rental-{rental_id}-{allocation_index + 1}"


def _username(rental_id: int, allocation_index: int) -> str:
    return f"{resolve_rental_ssh_username_prefix()}_{rental_id}_{allocation_index + 1}"


def _password(rental_id: int, cabinet_code: str, visible_devices: str, allocation_index: int) -> str:
    digest = hashlib.sha256(
        "|".join(
            [
                resolve_rental_ssh_password_seed(),
                str(rental_id),
                str(allocation_index + 1),
                cabinet_code,
                visible_devices,
            ]
        ).encode("utf-8")
    ).hexdigest()
    return f"Cr-{digest[:6]}-{digest[6:14]}"


def _port(rental_id: int, allocation_index: int) -> int:
    return resolve_rental_ssh_port_base() + ((rental_id * 16 + allocation_index) % 4000)


def _agent_base_url(host_ip: str | None = None) -> str | None:
    configured = resolve_agent_base_url()
    if configured:
        return configured
    if not host_ip:
        return None
    return f"http://{host_ip}:{resolve_agent_port()}"


def _image_for_allocation(allocation: dict) -> str:
    card_type = str(allocation.get("card_type") or "").lower()
    if "910" in card_type or "ascend" in card_type:
        return resolve_agent_ascend_image()
    if card_type in {"3090", "4090"} or "nvidia" in card_type:
        return resolve_agent_nvidia_image()
    return resolve_agent_default_image()


def create_instance(rental_id: int, allocation: dict, allocation_index: int = 0) -> dict:
    gpu_indices = allocation.get("device_indices") or []
    allocated_cards = int(allocation.get("allocated_cards") or len(gpu_indices) or 1)
    visible_devices = ",".join(str(item) for item in gpu_indices)
    username = _username(rental_id, allocation_index)
    password = _password(rental_id, allocation["cabinet_code"], visible_devices, allocation_index)
    port = _port(rental_id, allocation_index)
    payload = {
        "rental_id": rental_id,
        "instance_id": _environment_id(rental_id, allocation_index),
        "container_name": _environment_id(rental_id, allocation_index),
        "gpu_indices": gpu_indices,
        "image": _image_for_allocation(allocation),
        "username": username,
        "password": password,
        "ssh_port": port,
        "cpu_limit": round(resolve_cpu_per_card() * allocated_cards, 2),
        "memory_limit_gb": resolve_memory_per_card_gb() * allocated_cards,
        "shm_size": f"{resolve_shm_per_card_gb() * allocated_cards}g",
    }

    agent_base_url = _agent_base_url(allocation.get("host_ip"))
    if resolve_agent_dry_run():
        return _dry_run_instance(allocation, payload)
    if not agent_base_url:
        raise AppError("AGENT_NOT_CONFIGURED", "节点 Agent 未配置", 500)

    provisioned = _request_agent(agent_base_url, "POST", "/api/instances", payload)
    provisioned["agent_base_url"] = agent_base_url
    return provisioned


def stop_instance(instance_id: str | None, host_ip: str | None = None, agent_base_url: str | None = None) -> None:
    if not instance_id or resolve_agent_dry_run():
        return
    base_url = agent_base_url or _agent_base_url(host_ip)
    if not base_url:
        raise AppError("AGENT_NOT_CONFIGURED", "节点 Agent 未配置", 500)
    _request_agent(base_url, "POST", f"/api/instances/{instance_id}/stop", {})


def _dry_run_instance(allocation: dict, payload: dict) -> dict:
    host = allocation["host_ip"]
    command = f"ssh {payload['username']}@{host} -p {payload['ssh_port']}"
    return {
        "success": True,
        "instance_id": payload["instance_id"],
        "container_name": payload["container_name"],
        "host": host,
        "ssh_port": payload["ssh_port"],
        "username": payload["username"],
        "password": payload["password"],
        "command": command,
        "gpu_indices": payload["gpu_indices"],
        "cpu_limit": payload["cpu_limit"],
        "memory_limit_gb": payload["memory_limit_gb"],
        "shm_size": payload["shm_size"],
        "status": "running",
        "provisioning_status": "ready",
        "agent_base_url": _agent_base_url(host),
    }


def _request_agent(base_url: str, method: str, path: str, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib_request.Request(
        f"{base_url}{path}",
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {resolve_agent_token()}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib_request.urlopen(req, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise AppError("AGENT_REQUEST_FAILED", "节点 Agent 调用失败", 502) from exc
