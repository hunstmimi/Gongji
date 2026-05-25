from __future__ import annotations

from datetime import datetime

from ..config import TIMEZONE
from ..db import connection_scope
from ..utils import now_dt, parse_iso, round2


def _month_start(current: datetime) -> datetime:
    local = current.astimezone(TIMEZONE)
    return local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _overlap_seconds(started_at: str | None, ended_at: str | None, window_start: datetime, window_end: datetime) -> int:
    start = parse_iso(started_at)
    if not start:
        return 0
    end = parse_iso(ended_at) if ended_at else window_end
    if not end:
        end = window_end
    start = start.astimezone(TIMEZONE)
    end = end.astimezone(TIMEZONE)
    left = max(start, window_start)
    right = min(end, window_end)
    return max(0, int((right - left).total_seconds()))


def get_usage_overview() -> dict:
    current = now_dt()
    window_start = _month_start(current)

    with connection_scope() as conn:
        users = conn.execute(
            """
            SELECT id, username, nickname, phone, balance, status, created_at
            FROM users
            ORDER BY id ASC
            """
        ).fetchall()
        rentals = conn.execute(
            """
            SELECT
                r.id,
                r.user_id,
                r.card_type,
                r.cabinet_type,
                r.card_count,
                r.started_at,
                r.ended_at,
                r.status,
                r.stop_reason,
                r.hourly_user_price_total
            FROM rentals r
            WHERE r.user_id IS NOT NULL
              AND (
                r.status = 'active'
                OR (r.ended_at IS NOT NULL AND r.ended_at >= ?)
              )
            ORDER BY r.started_at DESC, r.id DESC
            """,
            (window_start.isoformat(timespec="seconds"),),
        ).fetchall()

    stats: dict[int, dict] = {
        int(user["id"]): {
            "user_id": user["id"],
            "username": user["username"],
            "nickname": user["nickname"],
            "phone": user.get("phone"),
            "balance": round2(float(user["balance"])),
            "status": user["status"],
            "current_card_count": 0,
            "current_rental_count": 0,
            "month_card_hours": 0.0,
            "month_rental_count": 0,
            "active_rentals": [],
        }
        for user in users
    }

    for rental in rentals:
        user_id = int(rental["user_id"])
        if user_id not in stats:
            continue
        card_count = int(rental["card_count"] or 0)
        overlap = _overlap_seconds(rental["started_at"], rental["ended_at"], window_start, current)
        if overlap > 0:
            stats[user_id]["month_card_hours"] += card_count * overlap / 3600
            stats[user_id]["month_rental_count"] += 1

        if rental["status"] == "active":
            stats[user_id]["current_card_count"] += card_count
            stats[user_id]["current_rental_count"] += 1
            stats[user_id]["active_rentals"].append(
                {
                    "rental_id": rental["id"],
                    "card_type": rental["card_type"],
                    "cabinet_type": rental["cabinet_type"],
                    "card_count": card_count,
                    "started_at": rental["started_at"],
                    "hourly_user_price_total": round2(float(rental["hourly_user_price_total"])),
                }
            )

    users_usage = []
    for item in stats.values():
        item["month_card_hours"] = round2(item["month_card_hours"]) or 0.0
        users_usage.append(item)
    users_usage.sort(
        key=lambda item: (
            -float(item["current_card_count"]),
            -float(item["month_card_hours"]),
            item["username"],
        )
    )

    ranking = sorted(
        [item for item in users_usage if float(item["month_card_hours"]) > 0],
        key=lambda item: (-float(item["month_card_hours"]), item["username"]),
    )[:3]

    total_current_cards = sum(int(item["current_card_count"]) for item in users_usage)
    total_month_card_hours = round2(sum(float(item["month_card_hours"]) for item in users_usage)) or 0.0

    return {
        "success": True,
        "month": window_start.strftime("%Y-%m"),
        "generated_at": current.isoformat(timespec="seconds"),
        "summary": {
            "total_users": len(users_usage),
            "active_users": sum(1 for item in users_usage if item["current_card_count"] > 0),
            "total_current_cards": total_current_cards,
            "total_month_card_hours": total_month_card_hours,
        },
        "ranking": ranking,
        "users": users_usage,
    }
