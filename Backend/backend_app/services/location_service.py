from __future__ import annotations

import math
import re

from ..db import connection_scope
from ..seed import CARD_PRODUCTS, LOCATION_EDGES, LOCATION_LAYOUTS, get_preview_max


AUTO_LAYOUT_SLOTS = [
    {"x_ratio": 0.18, "y_ratio": 0.22},
    {"x_ratio": 0.42, "y_ratio": 0.16},
    {"x_ratio": 0.68, "y_ratio": 0.58},
    {"x_ratio": 0.84, "y_ratio": 0.34},
    {"x_ratio": 0.22, "y_ratio": 0.68},
    {"x_ratio": 0.48, "y_ratio": 0.76},
    {"x_ratio": 0.72, "y_ratio": 0.18},
    {"x_ratio": 0.90, "y_ratio": 0.68},
    {"x_ratio": 0.10, "y_ratio": 0.46},
    {"x_ratio": 0.56, "y_ratio": 0.40},
]


def _node_status(available_cards: int, rented_cabinets: int, total_cabinets: int) -> str:
    if available_cards > 0:
        return "available"
    if rented_cabinets >= total_cabinets and total_cabinets > 0:
        return "rented"
    return "offline"


def _memory_gb(card_type: str, cards: int, reported_mb: int | float | None) -> float:
    if reported_mb:
        return round(float(reported_mb) / 1024, 1)
    product = next((item for item in CARD_PRODUCTS if item["card_type"] == card_type), None)
    raw_vram = product.get("vram") if product else ""
    digits = "".join(ch for ch in raw_vram if ch.isdigit() or ch == ".")
    per_card = float(digits) if digits else 0.0
    return round(per_card * cards, 1)


def _location_sort_key(location: str) -> tuple[str, int, str]:
    match = re.search(r"(\d+)$", location)
    if not match:
        return (location, 10**9, location)
    return (location[: match.start()], int(match.group(1)), location)


def _fallback_grid_layout(index: int, total: int) -> dict:
    columns = max(1, min(5, math.ceil(math.sqrt(total))))
    rows = math.ceil(total / columns)
    column = index % columns
    row = index // columns
    x_ratio = 0.12 if columns == 1 else 0.12 + (0.76 * column / (columns - 1))
    y_ratio = 0.22 if rows == 1 else 0.18 + (0.62 * row / (rows - 1))
    if row % 2 == 1 and columns > 1:
        x_ratio = min(0.90, x_ratio + 0.06)
    return {"x_ratio": round(x_ratio, 3), "y_ratio": round(y_ratio, 3)}


def _build_layouts(locations: list[str]) -> dict[str, dict]:
    layouts: dict[str, dict] = {}
    total = len(locations)
    for index, location in enumerate(locations):
        if index < len(AUTO_LAYOUT_SLOTS):
            layouts[location] = AUTO_LAYOUT_SLOTS[index]
        else:
            layouts[location] = _fallback_grid_layout(index, total)
    return layouts


def _build_edges(locations: list[str]) -> list[dict]:
    location_set = set(locations)
    edges: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for edge in LOCATION_EDGES:
        left = edge["from"]
        right = edge["to"]
        if left not in location_set or right not in location_set:
            continue
        key = (left, right)
        edges.append({"from": left, "to": right})
        seen.add(key)
    for index in range(1, len(locations)):
        left = locations[index - 1]
        right = locations[index]
        key = (left, right)
        reverse_key = (right, left)
        if key in seen or reverse_key in seen:
            continue
        edges.append({"from": left, "to": right})
        seen.add(key)
    return edges


def get_locations_summary() -> dict:
    with connection_scope() as conn:
        rows = conn.execute(
            """
            WITH cabinet_gpu AS (
                SELECT
                    c.id,
                    c.location,
                    c.card_type,
                    c.cabinet_type,
                    c.capacity_cards,
                    SUM(CASE WHEN g.status = 'available' AND COALESCE(g.observed_status, 'unknown') NOT IN ('occupied_unknown', 'unhealthy') THEN 1 ELSE 0 END) AS available_cards,
                    SUM(CASE WHEN g.status = 'rented' THEN 1 ELSE 0 END) AS active_cards,
                    SUM(CASE WHEN g.status != 'disabled' THEN 1 ELSE 0 END) AS managed_cards,
                    SUM(CASE WHEN g.status = 'available' AND COALESCE(g.observed_status, 'unknown') NOT IN ('occupied_unknown', 'unhealthy') THEN COALESCE(g.memory_total_mb, 0) ELSE 0 END) AS available_memory_mb,
                    SUM(CASE WHEN g.status != 'disabled' THEN COALESCE(g.memory_total_mb, 0) ELSE 0 END) AS total_memory_mb
                FROM cabinets c
                LEFT JOIN gpu_devices g ON g.cabinet_id = c.id
                GROUP BY c.id, c.location, c.card_type, c.cabinet_type, c.capacity_cards
            )
            SELECT
                location,
                card_type,
                cabinet_type,
                capacity_cards,
                COUNT(*) AS total_cabinets,
                SUM(CASE WHEN available_cards > 0 THEN 1 ELSE 0 END) AS rentable_cabinets,
                SUM(CASE WHEN available_cards > 0 THEN 1 ELSE 0 END) AS online_available_cabinets,
                SUM(CASE WHEN active_cards >= managed_cards AND managed_cards > 0 THEN 1 ELSE 0 END) AS rented_cabinets,
                SUM(CASE WHEN available_cards = 0 AND active_cards < managed_cards THEN 1 ELSE 0 END) AS offline_cabinets,
                SUM(capacity_cards) AS total_cards,
                SUM(managed_cards) AS managed_cards,
                SUM(available_cards) AS available_cards,
                SUM(active_cards) AS active_cards,
                SUM(available_memory_mb) AS available_memory_mb,
                SUM(total_memory_mb) AS total_memory_mb
            FROM cabinet_gpu
            GROUP BY location, card_type, cabinet_type, capacity_cards
            ORDER BY location ASC, card_type ASC, cabinet_type ASC, capacity_cards ASC
            """
        ).fetchall()

    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["location"], []).append(row)

    items = []
    dynamic_locations = sorted((location for location in grouped if location not in LOCATION_LAYOUTS), key=_location_sort_key)
    ordered_locations = list(dict.fromkeys([*LOCATION_LAYOUTS.keys(), *dynamic_locations]))
    layouts = _build_layouts(ordered_locations)
    for location in ordered_locations:
        breakdown_rows = grouped.get(location, [])
        layout = layouts[location]
        total_cabinets = sum(int(row["total_cabinets"] or 0) for row in breakdown_rows)
        rentable_cabinets = sum(int(row["rentable_cabinets"] or 0) for row in breakdown_rows)
        online_available_cabinets = sum(int(row["online_available_cabinets"] or 0) for row in breakdown_rows)
        rented_cabinets = sum(int(row["rented_cabinets"] or 0) for row in breakdown_rows)
        offline_cabinets = sum(int(row["offline_cabinets"] or 0) for row in breakdown_rows)
        total_cards = sum(int(row["total_cards"] or 0) for row in breakdown_rows)
        managed_cards = sum(int(row["managed_cards"] or 0) for row in breakdown_rows)
        available_cards = sum(int(row["available_cards"] or 0) for row in breakdown_rows)
        active_cards = sum(int(row["active_cards"] or 0) for row in breakdown_rows)
        available_memory_gb = round(
            sum(
                _memory_gb(row["card_type"], int(row["available_cards"] or 0), row["available_memory_mb"])
                for row in breakdown_rows
            ),
            1,
        )
        total_memory_gb = round(
            sum(
                _memory_gb(row["card_type"], int(row["managed_cards"] or 0), row["total_memory_mb"])
                for row in breakdown_rows
            ),
            1,
        )
        items.append(
            {
                "location": location,
                "label": location,
                "total_cabinets": total_cabinets,
                "available_cabinets": rentable_cabinets,
                "online_available_cabinets": online_available_cabinets,
                "rented_cabinets": rented_cabinets,
                "offline_cabinets": offline_cabinets,
                "total_cards": total_cards,
                "managed_cards": managed_cards,
                "available_cards": available_cards,
                "active_cards": active_cards,
                "available_memory_gb": available_memory_gb,
                "total_memory_gb": total_memory_gb,
                "node_status": _node_status(available_cards, rented_cabinets, total_cabinets),
                "x_ratio": layout["x_ratio"],
                "y_ratio": layout["y_ratio"],
                "cabinet_breakdown": [
                    {
                        "card_type": row["card_type"],
                        "cabinet_type": row["cabinet_type"],
                        "capacity_cards": int(row["capacity_cards"]),
                        "total_cabinets": int(row["total_cabinets"] or 0),
                        "available_cabinets": int(row["rentable_cabinets"] or 0),
                        "online_available_cabinets": int(row["online_available_cabinets"] or 0),
                        "rented_cabinets": int(row["rented_cabinets"] or 0),
                        "offline_cabinets": int(row["offline_cabinets"] or 0),
                        "total_cards": int(row["total_cards"] or 0),
                        "managed_cards": int(row["managed_cards"] or 0),
                        "available_cards": int(row["available_cards"] or 0),
                        "active_cards": int(row["active_cards"] or 0),
                        "available_memory_gb": _memory_gb(
                            row["card_type"],
                            int(row["available_cards"] or 0),
                            row["available_memory_mb"],
                        ),
                        "total_memory_gb": _memory_gb(
                            row["card_type"],
                            int(row["managed_cards"] or 0),
                            row["total_memory_mb"],
                        ),
                        "max_card_count": min(
                            get_preview_max(row["card_type"], row["cabinet_type"]),
                            int(row["available_cards"] or 0),
                        ),
                    }
                    for row in breakdown_rows
                ],
            }
        )

    return {"items": items, "edges": _build_edges(ordered_locations)}
