from __future__ import annotations

import re
from datetime import timedelta

from ..config import TIMEZONE
from ..db import connection_scope, transaction
from ..errors import AppError
from ..schemas import AdminCreateMachineRequest
from ..seed import CARD_PRODUCTS, LOCATION_LAYOUTS, PRICE_RULES
from ..utils import now_dt, parse_iso


BLOCKING_OBSERVED_STATUSES = {"occupied_unknown", "unhealthy"}
STALE_HEARTBEAT_SECONDS = 120


def _clean(value: str) -> str:
    return " ".join(value.strip().split())


def _parse_memory_mb(card_type: str) -> int | None:
    product = next((item for item in CARD_PRODUCTS if item["card_type"] == card_type), None)
    raw = product.get("vram") if product else ""
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:G|GB)", raw, flags=re.IGNORECASE)
    if not match:
        return None
    return int(float(match.group(1)) * 1024)


def _agent_state(last_seen_at: str | None) -> str:
    if not last_seen_at:
        return "waiting"
    seen = parse_iso(last_seen_at)
    if not seen:
        return "waiting"
    current = now_dt()
    if seen.tzinfo is None:
        seen = seen.replace(tzinfo=TIMEZONE)
    if current - seen.astimezone(TIMEZONE) > timedelta(seconds=STALE_HEARTBEAT_SECONDS):
        return "stale"
    return "online"


def _card_options() -> list[dict]:
    product_by_type = {item["card_type"]: item for item in CARD_PRODUCTS}
    result = []
    for card_type, cabinet_type in PRICE_RULES:
        product = product_by_type.get(card_type, {})
        result.append(
            {
                "card_type": card_type,
                "cabinet_type": cabinet_type,
                "title": product.get("title") or card_type,
                "default_capacity_cards": 8 if "8" in cabinet_type else 1,
            }
        )
    return result


def _device_summary(devices: list[dict]) -> dict:
    available = 0
    rented = 0
    disabled = 0
    blocked = 0
    for item in devices:
        status = item["status"]
        observed_status = item.get("observed_status") or "unknown"
        if status == "disabled":
            disabled += 1
            continue
        if status == "rented":
            rented += 1
        if observed_status in BLOCKING_OBSERVED_STATUSES:
            blocked += 1
        if status == "available" and observed_status not in BLOCKING_OBSERVED_STATUSES:
            available += 1
    return {
        "available_cards": available,
        "rented_cards": rented,
        "disabled_cards": disabled,
        "blocked_cards": blocked,
    }


def _load_heartbeats(conn) -> dict[str, dict]:
    rows = conn.execute(
        """
        SELECT host_ip, accelerator_type, status, last_seen_at
        FROM node_heartbeats
        ORDER BY last_seen_at DESC
        """
    ).fetchall()
    heartbeats: dict[str, dict] = {}
    for row in rows:
        heartbeats.setdefault(row["host_ip"], row)
    return heartbeats


def _serialize_machines(cabinets: list[dict], devices_by_cabinet: dict[int, list[dict]], heartbeats: dict[str, dict]) -> list[dict]:
    machines = []
    for cabinet in cabinets:
        cabinet_id = int(cabinet["id"])
        devices = sorted(devices_by_cabinet.get(cabinet_id, []), key=lambda item: int(item["gpu_index"]))
        heartbeat = heartbeats.get(cabinet.get("host_ip") or "")
        summary = _device_summary(devices)
        machines.append(
            {
                "id": cabinet_id,
                "cabinet_code": cabinet["cabinet_code"],
                "location": cabinet["location"],
                "host_ip": cabinet.get("host_ip"),
                "ssh_port": cabinet.get("ssh_port") or 22,
                "card_type": cabinet["card_type"],
                "cabinet_type": cabinet["cabinet_type"],
                "capacity_cards": int(cabinet["capacity_cards"]),
                "day_hourly_power_cost": float(cabinet["day_hourly_power_cost"]),
                "night_hourly_power_cost": float(cabinet["night_hourly_power_cost"]),
                "status": cabinet["status"],
                "agent_status": _agent_state(heartbeat.get("last_seen_at") if heartbeat else None),
                "agent_last_seen_at": heartbeat.get("last_seen_at") if heartbeat else None,
                "accelerator_type": heartbeat.get("accelerator_type") if heartbeat else None,
                **summary,
                "devices": [
                    {
                        "index": int(device["gpu_index"]),
                        "name": device["gpu_name"],
                        "status": device["status"],
                        "observed_status": device.get("observed_status") or "unknown",
                        "health": device.get("health"),
                        "memory_used_mb": device.get("memory_used_mb"),
                        "memory_total_mb": device.get("memory_total_mb"),
                        "process_count": int(device.get("process_count") or 0),
                        "last_seen_at": device.get("last_seen_at"),
                    }
                    for device in devices
                ],
            }
        )
    return machines


def list_machines() -> dict:
    with connection_scope() as conn:
        cabinets = conn.execute(
            """
            SELECT
                id, cabinet_code, location, card_type, cabinet_type, capacity_cards,
                day_hourly_power_cost, night_hourly_power_cost, status, host_ip, ssh_port
            FROM cabinets
            ORDER BY location ASC, card_type ASC, cabinet_code ASC
            """
        ).fetchall()
        device_rows = conn.execute(
            """
            SELECT
                cabinet_id, gpu_index, gpu_name, status, observed_status, health,
                memory_used_mb, memory_total_mb, process_count, last_seen_at
            FROM gpu_devices
            ORDER BY cabinet_id ASC, gpu_index ASC
            """
        ).fetchall()
        heartbeats = _load_heartbeats(conn)

    devices_by_cabinet: dict[int, list[dict]] = {}
    for row in device_rows:
        devices_by_cabinet.setdefault(int(row["cabinet_id"]), []).append(row)

    machines = _serialize_machines(cabinets, devices_by_cabinet, heartbeats)
    return {
        "success": True,
        "summary": {
            "total_machines": len(machines),
            "online_agents": sum(1 for item in machines if item["agent_status"] == "online"),
            "available_cards": sum(int(item["available_cards"]) for item in machines),
            "blocked_cards": sum(int(item["blocked_cards"]) for item in machines),
        },
        "locations": list(dict.fromkeys([*LOCATION_LAYOUTS.keys(), *(item["location"] for item in machines)])),
        "card_options": _card_options(),
        "machines": machines,
    }


def create_machine(payload: AdminCreateMachineRequest) -> dict:
    cabinet_code = _clean(payload.cabinet_code)
    location = _clean(payload.location)
    host_ip = _clean(payload.host_ip)
    card_type = _clean(payload.card_type)
    cabinet_type = _clean(payload.cabinet_type)

    if (card_type, cabinet_type) not in PRICE_RULES:
        raise AppError("UNSUPPORTED_MACHINE_TYPE", "当前卡型和机型还没有配置售卖规则", 400)
    if cabinet_type == "单卡机柜" and payload.capacity_cards != 1:
        raise AppError("INVALID_MACHINE_CAPACITY", "单卡机柜只能配置 1 张卡", 400)

    memory_total_mb = _parse_memory_mb(card_type)

    with transaction() as conn:
        existing_code = conn.execute(
            "SELECT id FROM cabinets WHERE cabinet_code = ?",
            (cabinet_code,),
        ).fetchone()
        if existing_code:
            raise AppError("MACHINE_EXISTS", "机器编号已存在", 409)

        existing_host = conn.execute(
            "SELECT cabinet_code FROM cabinets WHERE host_ip = ?",
            (host_ip,),
        ).fetchone()
        if existing_host:
            raise AppError("HOST_EXISTS", f"该 IP 已接入为 {existing_host['cabinet_code']}", 409)

        cabinet_id = conn.execute_insert(
            """
            INSERT INTO cabinets (
                cabinet_code, location, card_type, cabinet_type, capacity_cards,
                day_hourly_power_cost, night_hourly_power_cost, status, last_idle_at,
                active_card_count, host_ip, ssh_port
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'offline', NULL, 0, ?, ?)
            """,
            (
                cabinet_code,
                location,
                card_type,
                cabinet_type,
                int(payload.capacity_cards),
                float(payload.day_hourly_power_cost),
                float(payload.night_hourly_power_cost),
                host_ip,
                int(payload.ssh_port),
            ),
        )

        for index in range(int(payload.capacity_cards)):
            conn.execute(
                """
                INSERT INTO gpu_devices (
                    cabinet_id, gpu_index, gpu_name, status, observed_status,
                    memory_total_mb, process_count
                ) VALUES (?, ?, ?, 'available', 'occupied_unknown', ?, 0)
                """,
                (cabinet_id, index, card_type, memory_total_mb),
            )

    return {
        "success": True,
        "message": "机器已添加，等待 Agent 心跳确认后进入可租状态",
        "machine": next(
            item for item in list_machines()["machines"]
            if item["cabinet_code"] == cabinet_code
        ),
    }
