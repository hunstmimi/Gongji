from __future__ import annotations

import json

from ..db import transaction
from ..schemas import NodeHeartbeatRequest
from ..utils import now_iso


def _json_dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _observed_status(db_status: str | None, health: str | None, process_count: int) -> str:
    if db_status == "disabled":
        return "disabled"
    if health and health.upper() not in {"OK", "HEALTHY"}:
        return "unhealthy"
    if process_count > 0:
        return "platform_rented" if db_status == "rented" else "occupied_unknown"
    return "idle"


def ingest_node_heartbeat(payload: NodeHeartbeatRequest) -> dict:
    seen_at = now_iso()
    raw_payload = payload.model_dump()

    with transaction() as conn:
        conn.execute(
            """
            INSERT INTO node_heartbeats (
                node_id, host_ip, accelerator_type, status, reported_at, last_seen_at, raw, updated_at
            ) VALUES (?, ?, ?, 'online', ?, ?, ?, ?)
            ON CONFLICT(node_id) DO UPDATE SET
                host_ip = excluded.host_ip,
                accelerator_type = excluded.accelerator_type,
                status = 'online',
                reported_at = excluded.reported_at,
                last_seen_at = excluded.last_seen_at,
                raw = excluded.raw,
                updated_at = excluded.updated_at
            """,
            (
                payload.node_id,
                payload.host_ip,
                payload.accelerator_type,
                payload.reported_at,
                seen_at,
                _json_dump(raw_payload),
                seen_at,
            ),
        )

        updated_devices = 0
        for device in payload.devices:
            gpu_row = conn.execute(
                """
                SELECT g.id, g.status
                FROM gpu_devices g
                JOIN cabinets c ON c.id = g.cabinet_id
                WHERE c.host_ip = ? AND g.gpu_index = ?
                """,
                (payload.host_ip, device.index),
            ).fetchone()
            db_status = gpu_row["status"] if gpu_row else None
            observed_status = _observed_status(db_status, device.health, int(device.process_count or 0))

            conn.execute(
                """
                INSERT INTO node_device_reports (
                    node_id, device_index, name, health, usage_percent,
                    memory_used_mb, memory_total_mb, hbm_used_mb, hbm_total_mb,
                    process_count, observed_status, raw, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(node_id, device_index) DO UPDATE SET
                    name = excluded.name,
                    health = excluded.health,
                    usage_percent = excluded.usage_percent,
                    memory_used_mb = excluded.memory_used_mb,
                    memory_total_mb = excluded.memory_total_mb,
                    hbm_used_mb = excluded.hbm_used_mb,
                    hbm_total_mb = excluded.hbm_total_mb,
                    process_count = excluded.process_count,
                    observed_status = excluded.observed_status,
                    raw = excluded.raw,
                    updated_at = excluded.updated_at
                """,
                (
                    payload.node_id,
                    device.index,
                    device.name,
                    device.health,
                    device.usage_percent,
                    device.memory_used_mb,
                    device.memory_total_mb,
                    device.hbm_used_mb,
                    device.hbm_total_mb,
                    device.process_count,
                    observed_status,
                    device.raw,
                    seen_at,
                ),
            )

            if gpu_row:
                conn.execute(
                    """
                    UPDATE gpu_devices
                    SET
                        observed_status = ?,
                        health = ?,
                        usage_percent = ?,
                        memory_used_mb = ?,
                        memory_total_mb = ?,
                        process_count = ?,
                        last_seen_at = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        observed_status,
                        device.health,
                        device.usage_percent,
                        device.hbm_used_mb if device.hbm_used_mb is not None else device.memory_used_mb,
                        device.hbm_total_mb if device.hbm_total_mb is not None else device.memory_total_mb,
                        device.process_count,
                        seen_at,
                        seen_at,
                        gpu_row["id"],
                    ),
                )
                updated_devices += 1

        return {
            "success": True,
            "node_id": payload.node_id,
            "updated_devices": updated_devices,
            "reported_devices": len(payload.devices),
        }
