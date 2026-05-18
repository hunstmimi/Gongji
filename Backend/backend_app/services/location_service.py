from __future__ import annotations

from ..db import connection_scope
from ..seed import LOCATION_EDGES, LOCATION_LAYOUTS


def _node_status(available_cards: int, rented_cabinets: int, total_cabinets: int) -> str:
    if available_cards > 0:
        return "available"
    if rented_cabinets >= total_cabinets and total_cabinets > 0:
        return "rented"
    return "offline"


def get_locations_summary() -> dict:
    with connection_scope() as conn:
        rows = conn.execute(
            """
            SELECT
                location,
                card_type,
                cabinet_type,
                capacity_cards,
                COUNT(*) AS total_cabinets,
                SUM(CASE WHEN status IN ('available', 'offline') THEN 1 ELSE 0 END) AS rentable_cabinets,
                SUM(CASE WHEN status = 'available' THEN 1 ELSE 0 END) AS online_available_cabinets,
                SUM(CASE WHEN status = 'rented' THEN 1 ELSE 0 END) AS rented_cabinets,
                SUM(CASE WHEN status = 'offline' THEN 1 ELSE 0 END) AS offline_cabinets,
                SUM(capacity_cards) AS total_cards,
                SUM(CASE WHEN status IN ('available', 'offline') THEN capacity_cards - active_card_count ELSE 0 END) AS available_cards,
                SUM(active_card_count) AS active_cards
            FROM cabinets
            GROUP BY location, card_type, cabinet_type, capacity_cards
            ORDER BY location ASC, card_type ASC, cabinet_type ASC, capacity_cards ASC
            """
        ).fetchall()

    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["location"], []).append(row)

    items = []
    for location, breakdown_rows in grouped.items():
        layout = LOCATION_LAYOUTS.get(location, {"x_ratio": 0.5, "y_ratio": 0.5})
        total_cabinets = sum(int(row["total_cabinets"] or 0) for row in breakdown_rows)
        rentable_cabinets = sum(int(row["rentable_cabinets"] or 0) for row in breakdown_rows)
        online_available_cabinets = sum(int(row["online_available_cabinets"] or 0) for row in breakdown_rows)
        rented_cabinets = sum(int(row["rented_cabinets"] or 0) for row in breakdown_rows)
        offline_cabinets = sum(int(row["offline_cabinets"] or 0) for row in breakdown_rows)
        total_cards = sum(int(row["total_cards"] or 0) for row in breakdown_rows)
        available_cards = sum(int(row["available_cards"] or 0) for row in breakdown_rows)
        active_cards = sum(int(row["active_cards"] or 0) for row in breakdown_rows)
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
                "available_cards": available_cards,
                "active_cards": active_cards,
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
                        "available_cards": int(row["available_cards"] or 0),
                        "active_cards": int(row["active_cards"] or 0),
                    }
                    for row in breakdown_rows
                ],
            }
        )

    return {"items": items, "edges": LOCATION_EDGES}
