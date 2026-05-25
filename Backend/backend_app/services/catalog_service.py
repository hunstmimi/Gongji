from __future__ import annotations

import re

from ..db import connection_scope
from ..seed import (
    CARD_TYPE_ORDER,
    PRICE_RULES,
    get_allocation_policy,
    get_min_card_count,
    get_preview_max,
    get_pricing_preview,
)


BLOCKING_OBSERVED_STATUSES = {"occupied_unknown", "unhealthy"}


def _card_type_order_sql() -> str:
    clauses = " ".join(f"WHEN '{card_type}' THEN {rank}" for card_type, rank in CARD_TYPE_ORDER.items())
    return f"CASE card_type {clauses} ELSE 99 END"


def _parse_memory_gb(value: str | None) -> float | None:
    if not value:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:G|GB)", value, flags=re.IGNORECASE)
    return float(match.group(1)) if match else None


def _mb_to_gb(value: int | float | None) -> float | None:
    if value is None:
        return None
    return round(float(value) / 1024, 1)


def _round_gb(value: float) -> float:
    return round(value, 1)


def _build_machine_inventory(conn, products_by_type: dict[str, dict]) -> dict[tuple[str, str], list[dict]]:
    rows = conn.execute(
        """
        SELECT
            c.id AS cabinet_id,
            c.cabinet_code,
            c.location,
            c.card_type,
            c.cabinet_type,
            c.capacity_cards,
            c.status AS cabinet_status,
            c.host_ip,
            g.gpu_index,
            g.status AS device_status,
            COALESCE(g.observed_status, 'unknown') AS observed_status,
            g.health,
            g.usage_percent,
            g.memory_used_mb,
            g.memory_total_mb,
            g.process_count,
            g.last_seen_at
        FROM cabinets c
        LEFT JOIN gpu_devices g ON g.cabinet_id = c.id
        ORDER BY c.card_type, c.cabinet_code, g.gpu_index
        """
    ).fetchall()

    machines: dict[int, dict] = {}
    for row in rows:
        cabinet_id = int(row["cabinet_id"])
        product = products_by_type.get(row["card_type"], {})
        fallback_memory_gb = _parse_memory_gb(product.get("vram"))
        if cabinet_id not in machines:
            machines[cabinet_id] = {
                "cabinet_id": cabinet_id,
                "cabinet_code": row["cabinet_code"],
                "location": row["location"],
                "card_type": row["card_type"],
                "card_title": product.get("title") or row["card_type"],
                "cabinet_type": row["cabinet_type"],
                "capacity_cards": int(row["capacity_cards"] or 0),
                "total_cards": int(row["capacity_cards"] or 0),
                "managed_cards": 0,
                "available_cards": 0,
                "rented_cards": 0,
                "disabled_cards": 0,
                "blocked_cards": 0,
                "available_memory_gb": 0.0,
                "total_memory_gb": 0.0,
                "per_card_memory_gb": fallback_memory_gb,
                "cpu": product.get("cpu"),
                "memory": product.get("memory"),
                "vram": product.get("vram"),
                "status": row["cabinet_status"],
                "host_ip": row["host_ip"],
                "devices": [],
            }

        if row["gpu_index"] is None:
            continue

        device_status = row["device_status"] or "available"
        observed_status = row["observed_status"] or "unknown"
        memory_total_gb = _mb_to_gb(row["memory_total_mb"]) or fallback_memory_gb or 0.0
        memory_used_gb = _mb_to_gb(row["memory_used_mb"]) or 0.0
        memory_free_gb = max(0.0, memory_total_gb - memory_used_gb)
        is_disabled = device_status == "disabled"
        is_blocked = observed_status in BLOCKING_OBSERVED_STATUSES
        is_available = device_status == "available" and not is_blocked

        machine = machines[cabinet_id]
        machine["devices"].append(
            {
                "index": int(row["gpu_index"]),
                "status": device_status,
                "observed_status": observed_status,
                "health": row["health"],
                "usage_percent": row["usage_percent"],
                "memory_used_gb": _round_gb(memory_used_gb),
                "memory_total_gb": _round_gb(memory_total_gb),
                "memory_free_gb": _round_gb(memory_free_gb),
                "process_count": int(row["process_count"] or 0),
                "last_seen_at": row["last_seen_at"],
            }
        )

        if is_disabled:
            machine["disabled_cards"] += 1
            continue

        machine["managed_cards"] += 1
        machine["total_memory_gb"] += memory_total_gb
        if device_status == "rented":
            machine["rented_cards"] += 1
        if is_blocked:
            machine["blocked_cards"] += 1
        if is_available:
            machine["available_cards"] += 1
            machine["available_memory_gb"] += memory_free_gb

    grouped: dict[tuple[str, str], list[dict]] = {}
    for machine in machines.values():
        machine["available_memory_gb"] = _round_gb(machine["available_memory_gb"])
        machine["total_memory_gb"] = _round_gb(machine["total_memory_gb"])
        machine["devices"] = sorted(machine["devices"], key=lambda item: item["index"])
        grouped.setdefault((machine["card_type"], machine["cabinet_type"]), []).append(machine)

    for machine_rows in grouped.values():
        machine_rows.sort(key=lambda item: (-item["available_cards"], item["cabinet_code"]))
    return grouped


def get_cards() -> dict:
    with connection_scope() as conn:
        items = conn.execute(
            f"""
            SELECT card_type, title, cabinet_desc, vram, cpu, memory, display_price
            FROM card_products
            ORDER BY {_card_type_order_sql()}
            """
        ).fetchall()
        products_by_type = {item["card_type"]: item for item in items}
        machine_inventory = _build_machine_inventory(conn, products_by_type)

        result = []
        for item in items:
            pricing_options = []
            for card_type, cabinet_type in PRICE_RULES:
                if card_type != item["card_type"]:
                    continue
                machines = machine_inventory.get((card_type, cabinet_type), [])
                available_cards = sum(int(machine["available_cards"] or 0) for machine in machines)
                managed_cards = sum(int(machine["managed_cards"] or 0) for machine in machines)
                total_cards = sum(int(machine["total_cards"] or 0) for machine in machines)
                available_memory_gb = _round_gb(sum(float(machine["available_memory_gb"] or 0) for machine in machines))
                total_memory_gb = _round_gb(sum(float(machine["total_memory_gb"] or 0) for machine in machines))
                allocation_policy = get_allocation_policy(card_type, cabinet_type)
                min_card_count = get_min_card_count(card_type, cabinet_type)
                configured_max = get_preview_max(card_type, cabinet_type)
                max_available_cards = (
                    sum(
                        cards
                        for cards in [int(machine["available_cards"] or 0) for machine in machines]
                        if cards >= min_card_count
                    )
                    if allocation_policy == "same_cabinet_required"
                    else available_cards
                )
                max_card_count = min(configured_max, max_available_cards) if max_available_cards else configured_max
                pricing_options.append(
                    {
                        "cabinet_type": cabinet_type,
                        "capacity_cards": max([int(machine["capacity_cards"] or 1) for machine in machines], default=configured_max),
                        "total_cabinets": len(machines),
                        "total_cards": total_cards,
                        "managed_cards": managed_cards,
                        "available_cards": available_cards,
                        "available_memory_gb": available_memory_gb,
                        "total_memory_gb": total_memory_gb,
                        "max_available_cards": max_available_cards,
                        "min_card_count": min_card_count,
                        "max_card_count": max_card_count,
                        "disabled": available_cards < min_card_count,
                        "allocation_policy": allocation_policy,
                        "pricing_preview": get_pricing_preview(card_type, cabinet_type),
                        "machines": machines,
                    }
                )
            result.append(
                {
                    **item,
                    "per_card_memory_gb": _parse_memory_gb(item.get("vram")),
                    "pricing_options": pricing_options,
                }
            )
        return {"items": result}
