from __future__ import annotations

from ..db import connection_scope, transaction
from ..errors import AppError
from ..services.auth_service import serialize_user
from ..services.rental_service import settle_rental_if_balance_exhausted
from ..utils import card_label, duration_hours_from_seconds, now_iso, parse_iso, round2


def _serialize_rental_summary(row: dict, active: bool) -> dict:
    duration_seconds = row["duration_seconds"]
    if active:
        started_dt = parse_iso(row["started_at"])
        ended_dt = parse_iso(now_iso())
        duration_seconds = 0
        if started_dt and ended_dt:
            duration_seconds = max(0, int((ended_dt - started_dt).total_seconds()))

    item = {
        "rental_id": row["id"],
        "card_type": row["card_type"],
        "card_label": card_label(row["card_type"], row["cabinet_type"]),
        "hourly_price": round2(float(row["hourly_user_price_total"])),
        "started_at": row["started_at"],
        "duration_hours": duration_hours_from_seconds(duration_seconds),
        "current_amount": round2(float(row["hourly_user_price_total"]) * duration_hours_from_seconds(duration_seconds)),
        "status": row["status"],
        "stop_reason": row.get("stop_reason"),
    }
    if not active:
        item["ended_at"] = row["ended_at"]
        item["total_amount"] = round2(row["user_total_amount"])
    return item


def get_active_rentals(user_id: int) -> list[dict]:
    with transaction() as conn:
        _settle_user_active_rentals(conn, user_id)
        rows = conn.execute(
            """
            SELECT *
            FROM rentals
            WHERE user_id = ? AND status = 'active'
            ORDER BY started_at DESC, id DESC
            """,
            (user_id,),
        ).fetchall()
    return [_serialize_rental_summary(row, active=True) for row in rows]


def get_history_rentals(user_id: int) -> list[dict]:
    with transaction() as conn:
        _settle_user_active_rentals(conn, user_id)
        rows = conn.execute(
            """
            SELECT *
            FROM rentals
            WHERE user_id = ? AND status = 'cancelled'
            ORDER BY ended_at DESC, id DESC
            """,
            (user_id,),
        ).fetchall()
    return [_serialize_rental_summary(row, active=False) for row in rows]


def get_dashboard(user: dict) -> dict:
    with transaction() as conn:
        _settle_user_active_rentals(conn, user["id"])
        fresh_user = conn.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
    active_rentals = get_active_rentals(user["id"])
    history_rentals = get_history_rentals(user["id"])

    pending_settlement = round2(
        sum(item["hourly_price"] * item["duration_hours"] for item in active_rentals)
    )
    return {
        "success": True,
        "user": serialize_user(fresh_user),
        "wallet": {
            "balance": round2(float(fresh_user["balance"])),
            "currency": "CNY",
            "recharge_entry_enabled": True,
            "pending_settlement": pending_settlement,
        },
        "active_rentals_count": len(active_rentals),
        "history_rentals_count": len(history_rentals),
        "active_rentals": active_rentals,
        "history_rentals": history_rentals,
    }


def _settle_user_active_rentals(conn, user_id: int) -> None:
    rows = conn.execute(
        """
        SELECT *
        FROM rentals
        WHERE user_id = ? AND status = 'active'
        ORDER BY started_at ASC, id ASC
        """,
        (user_id,),
    ).fetchall()
    for row in rows:
        settle_rental_if_balance_exhausted(conn, row)


def recharge_balance(user_id: int, amount: float) -> dict:
    with transaction() as conn:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            raise AppError("USER_NOT_FOUND", "用户不存在", 404)

        new_balance = round2(float(user["balance"]) + amount)
        conn.execute(
            "UPDATE users SET balance = ?, updated_at = ? WHERE id = ?",
            (new_balance, now_iso(), user_id),
        )
        conn.execute(
            """
            INSERT INTO user_balance_transactions (
                user_id, type, amount, balance_after, reference_type, reference_id, remark
            ) VALUES (?, 'recharge', ?, ?, 'manual_recharge', NULL, ?)
            """,
            (user_id, round2(amount), new_balance, "前端充值"),
        )
        return {"success": True, "balance": new_balance}
