from __future__ import annotations

from ..db import connection_scope
from ..seed import (
    CARD_TYPE_ORDER,
    PRICE_RULES,
    get_allocation_policy,
    get_min_card_count,
    get_preview_max,
    get_pricing_preview,
)


def _card_type_order_sql() -> str:
    clauses = " ".join(f"WHEN '{card_type}' THEN {rank}" for card_type, rank in CARD_TYPE_ORDER.items())
    return f"CASE card_type {clauses} ELSE 99 END"


def get_cards() -> dict:
    with connection_scope() as conn:
        items = conn.execute(
            f"""
            SELECT card_type, title, cabinet_desc, vram, cpu, memory, display_price
            FROM card_products
            ORDER BY {_card_type_order_sql()}
            """
        ).fetchall()
        inventory_rows = conn.execute(
            """
            SELECT
                card_type,
                cabinet_type,
                MAX(capacity_cards) AS capacity_cards,
                COUNT(*) AS total_cabinets,
                SUM(CASE WHEN status IN ('available', 'offline') THEN capacity_cards - active_card_count ELSE 0 END) AS available_cards
            FROM cabinets
            GROUP BY card_type, cabinet_type
            """
        ).fetchall()
        cabinet_rows = conn.execute(
            """
            SELECT
                card_type,
                cabinet_type,
                capacity_cards,
                CASE WHEN status IN ('available', 'offline') THEN capacity_cards - active_card_count ELSE 0 END AS available_cards
            FROM cabinets
            """
        ).fetchall()
        inventory = {
            (row["card_type"], row["cabinet_type"]): {
                "capacity_cards": int(row["capacity_cards"] or 1),
                "total_cabinets": int(row["total_cabinets"] or 0),
                "available_cards": int(row["available_cards"] or 0),
            }
            for row in inventory_rows
        }
        cabinet_inventory: dict[tuple[str, str], list[int]] = {}
        for row in cabinet_rows:
            cabinet_inventory.setdefault((row["card_type"], row["cabinet_type"]), []).append(
                int(row["available_cards"] or 0)
            )

        result = []
        for item in items:
            pricing_options = []
            for card_type, cabinet_type in PRICE_RULES:
                if card_type != item["card_type"]:
                    continue
                option_inventory = inventory.get((card_type, cabinet_type), {})
                available_cards = int(option_inventory.get("available_cards", 0))
                allocation_policy = get_allocation_policy(card_type, cabinet_type)
                min_card_count = get_min_card_count(card_type, cabinet_type)
                configured_max = get_preview_max(card_type, cabinet_type)
                max_available_cards = (
                    sum(
                        cards
                        for cards in cabinet_inventory.get((card_type, cabinet_type), [])
                        if cards >= min_card_count
                    )
                    if allocation_policy == "same_cabinet_required"
                    else available_cards
                )
                max_card_count = min(configured_max, max_available_cards) if max_available_cards else configured_max
                pricing_options.append(
                    {
                        "cabinet_type": cabinet_type,
                        "capacity_cards": int(option_inventory.get("capacity_cards", configured_max)),
                        "total_cabinets": int(option_inventory.get("total_cabinets", 0)),
                        "available_cards": available_cards,
                        "max_available_cards": max_available_cards,
                        "min_card_count": min_card_count,
                        "max_card_count": max_card_count,
                        "disabled": available_cards < min_card_count,
                        "allocation_policy": allocation_policy,
                        "pricing_preview": get_pricing_preview(card_type, cabinet_type),
                    }
                )
            result.append(
                {
                    **item,
                    "pricing_options": pricing_options,
                }
            )
        return {"items": result}
