from __future__ import annotations

import hashlib
from datetime import timedelta

from ..config import (
    resolve_rental_ssh_password_seed,
    resolve_rental_ssh_port_base,
    resolve_rental_ssh_username_prefix,
)
from ..db import transaction
from ..errors import AppError
from ..seed import (
    CardCountRuleError,
    PriceRuleNotFoundError,
    get_allocation_policy,
    get_hourly_user_price_total,
    get_min_card_count,
)
from ..utils import card_label, cabinet_status_from_active_cards, now_iso, parse_iso, resolve_timeslot, round2


ACTIVE_STATUS = "active"
STOPPED_STATUS = "cancelled"
MANUAL_STOP_REASON = "manual"
BALANCE_EXHAUSTED_REASON = "balance_exhausted"


def _select_spread_allocations(candidate_rows: list[dict], card_count: int) -> list[dict]:
    remaining_cards = card_count
    selected: list[dict] = []
    for row in candidate_rows:
        if remaining_cards <= 0:
            break
        allocated_cards = min(remaining_cards, int(row["available_cards"]))
        if allocated_cards <= 0:
            continue
        selected.append({**row, "allocated_cards": allocated_cards})
        remaining_cards -= allocated_cards
    return selected if remaining_cards == 0 else []


def _select_grouped_allocations(candidate_rows: list[dict], card_count: int, min_cards_per_machine: int) -> list[dict]:
    usable_rows = [row for row in candidate_rows if int(row["available_cards"]) >= min_cards_per_machine]
    capacities = [int(row["available_cards"]) for row in usable_rows]
    selected_counts: list[tuple[int, int]] | None = None

    def search(index: int, remaining: int, counts: list[tuple[int, int]]) -> bool:
        nonlocal selected_counts
        if remaining == 0:
            selected_counts = counts[:]
            return True
        if index >= len(usable_rows):
            return False
        if sum(capacities[index:]) < remaining:
            return False

        max_take = min(capacities[index], remaining)
        for take in range(max_take, min_cards_per_machine - 1, -1):
            if remaining - take and remaining - take < min_cards_per_machine:
                continue
            if search(index + 1, remaining - take, counts + [(index, take)]):
                return True
        return search(index + 1, remaining, counts)

    if not search(0, card_count, []):
        return []

    return [
        {**usable_rows[row_index], "allocated_cards": allocated_cards}
        for row_index, allocated_cards in (selected_counts or [])
    ]


def _calculate_duration_seconds(started_at: str, ended_at: str) -> int:
    started_dt = parse_iso(started_at)
    ended_dt = parse_iso(ended_at)
    if started_dt is None or ended_dt is None:
        raise AppError("INVALID_RENTAL_TIMESTAMPS", "租单时间戳无效", 500)
    return max(0, int((ended_dt - started_dt).total_seconds()))


def _calculate_amounts(rental: dict, duration_seconds: int) -> tuple[float, float]:
    user_total_amount = float(rental["hourly_user_price_total"]) * duration_seconds / 3600
    power_cost_total = float(rental["hourly_power_cost_total"]) * duration_seconds / 3600
    return round2(user_total_amount), round2(power_cost_total)


def _release_rental_cabinets(conn, rental_id: int) -> None:
    conn.execute(
        """
        UPDATE cabinets
        SET
            active_card_count = CASE
                WHEN active_card_count - COALESCE(
                    (
                        SELECT allocated_cards
                        FROM rental_allocations
                        WHERE rental_id = ? AND cabinet_id = cabinets.id
                    ),
                    0
                ) < 0 THEN 0
                ELSE active_card_count - COALESCE(
                    (
                        SELECT allocated_cards
                        FROM rental_allocations
                        WHERE rental_id = ? AND cabinet_id = cabinets.id
                    ),
                    0
                )
            END
        WHERE id IN (SELECT cabinet_id FROM rental_allocations WHERE rental_id = ?)
        """,
        (rental_id, rental_id, rental_id),
    )
    rows = conn.execute(
        """
        SELECT id, active_card_count, capacity_cards
        FROM cabinets
        WHERE id IN (SELECT cabinet_id FROM rental_allocations WHERE rental_id = ?)
        """,
        (rental_id,),
    ).fetchall()
    for row in rows:
        conn.execute(
            "UPDATE cabinets SET status = ?, last_idle_at = NULL WHERE id = ?",
            (
                cabinet_status_from_active_cards(int(row["active_card_count"]), int(row["capacity_cards"])),
                row["id"],
            ),
        )


def _write_rental_charge(conn, user_id: int, rental_id: int, amount: float, balance_after: float, remark: str) -> None:
    if amount <= 0:
        return
    conn.execute(
        """
        INSERT INTO user_balance_transactions (
            user_id, type, amount, balance_after, reference_type, reference_id, remark
        ) VALUES (?, 'rental_charge', ?, ?, 'rental', ?, ?)
        """,
        (user_id, -round2(amount), round2(balance_after), rental_id, remark),
    )


def _finish_active_rental(conn, rental: dict, ended_at: str, stop_reason: str, charge_amount: float) -> dict:
    duration_seconds = _calculate_duration_seconds(rental["started_at"], ended_at)
    user_total_amount, power_cost_total = _calculate_amounts(rental, duration_seconds)
    conn.execute(
        """
        UPDATE rentals
        SET ended_at = ?, duration_seconds = ?, user_total_amount = ?, power_cost_total = ?, status = ?, stop_reason = ?
        WHERE id = ?
        """,
        (ended_at, duration_seconds, user_total_amount, power_cost_total, STOPPED_STATUS, stop_reason, rental["id"]),
    )
    _release_rental_cabinets(conn, rental["id"])
    user = conn.execute("SELECT * FROM users WHERE id = ?", (rental["user_id"],)).fetchone()
    if user and charge_amount > 0:
        new_balance = round2(max(0, float(user["balance"]) - charge_amount))
        conn.execute(
            "UPDATE users SET balance = ?, updated_at = ? WHERE id = ?",
            (new_balance, now_iso(), rental["user_id"]),
        )
        remark = "余额耗尽自动停机" if stop_reason == BALANCE_EXHAUSTED_REASON else "租赁关机结算"
        _write_rental_charge(conn, rental["user_id"], rental["id"], charge_amount, new_balance, remark)
    return conn.execute("SELECT * FROM rentals WHERE id = ?", (rental["id"],)).fetchone()


def settle_rental_if_balance_exhausted(conn, rental: dict) -> dict:
    if rental["status"] != ACTIVE_STATUS:
        return rental

    user = conn.execute("SELECT * FROM users WHERE id = ?", (rental["user_id"],)).fetchone()
    if not user:
        return rental

    current_duration = _calculate_duration_seconds(rental["started_at"], now_iso())
    current_amount, _ = _calculate_amounts(rental, current_duration)
    balance = float(user["balance"])
    if current_amount < balance:
        return rental

    hourly_price = float(rental["hourly_user_price_total"])
    payable_seconds = int(balance / hourly_price * 3600) if hourly_price > 0 else 0
    started_dt = parse_iso(rental["started_at"])
    if started_dt is None:
        raise AppError("INVALID_RENTAL_TIMESTAMPS", "租单时间戳无效", 500)
    ended_iso = (started_dt + timedelta(seconds=max(0, payable_seconds))).isoformat(timespec="seconds")
    return _finish_active_rental(conn, rental, ended_iso, BALANCE_EXHAUSTED_REASON, balance)


def _serialize_allocation(row: dict) -> dict:
    raw_device_indices = row.get("device_indices") or ""
    device_indices = [int(item) for item in raw_device_indices.split(",") if item != ""]
    return {
        "cabinet_code": row["cabinet_code"],
        "location": row["location"],
        "cabinet_type": row["cabinet_type"],
        "capacity_cards": row["capacity_cards"],
        "allocated_cards": row["allocated_cards"],
        "device_indices": device_indices,
        "visible_devices": ",".join(str(item) for item in device_indices),
        "hourly_user_price": round2(row["hourly_user_price"]),
        "hourly_power_cost": round2(row["hourly_power_cost"]),
        "host_ip": row["host_ip"],
        "ssh_port": row["ssh_port"],
    }


def _rental_environment_id(rental_id: int, allocation_index: int) -> str:
    return f"rental-{rental_id}-{allocation_index + 1}"


def _rental_connection_username(rental_id: int, allocation_index: int) -> str:
    prefix = resolve_rental_ssh_username_prefix()
    return f"{prefix}_{rental_id}_{allocation_index + 1}"


def _rental_connection_password(rental_id: int, allocation: dict, allocation_index: int) -> str:
    digest = hashlib.sha256(
        "|".join(
            [
                resolve_rental_ssh_password_seed(),
                str(rental_id),
                str(allocation_index + 1),
                allocation["cabinet_code"],
                allocation.get("visible_devices", ""),
            ]
        ).encode("utf-8")
    ).hexdigest()
    return f"Cr-{digest[:6]}-{digest[6:14]}"


def _rental_connection_port(rental_id: int, allocation_index: int) -> int:
    base_port = resolve_rental_ssh_port_base()
    return base_port + ((rental_id * 16 + allocation_index) % 4000)


def _build_connection_for_allocation(rental_id: int, allocation: dict, allocation_index: int) -> dict:
    ip = allocation["host_ip"]
    port = _rental_connection_port(rental_id, allocation_index)
    username = _rental_connection_username(rental_id, allocation_index)
    password = _rental_connection_password(rental_id, allocation, allocation_index)
    login = f"{username}@{ip}"
    return {
        "connection_type": "rental_environment",
        "provisioning_status": "ready",
        "environment_id": _rental_environment_id(rental_id, allocation_index),
        "username": username,
        "password": password,
        "ip": ip,
        "port": port,
        "login": login,
        "command": f"ssh {login} -p {port}",
        "cabinet_code": allocation["cabinet_code"],
        "allocated_cards": allocation["allocated_cards"],
        "visible_devices": allocation.get("visible_devices", ""),
        "device_indices": allocation.get("device_indices", []),
        "internal_host_ip": allocation["host_ip"],
        "internal_ssh_port": allocation.get("ssh_port") or 22,
    }


def _build_connection_payload(rental_id: int, allocations: list[dict]) -> dict:
    primary = allocations[0] if allocations else None
    if not primary:
        username = _rental_connection_username(rental_id, 0)
        port = _rental_connection_port(rental_id, 0)
        return {
            "connection_type": "rental_environment",
            "provisioning_status": "pending",
            "environment_id": _rental_environment_id(rental_id, 0),
            "username": username,
            "password": "",
            "ip": "",
            "port": port,
            "login": f"{username}@",
            "command": f"ssh {username}@ -p {port}",
        }
    return _build_connection_for_allocation(rental_id, primary, 0)


def _build_connections_payload(rental_id: int, allocations: list[dict]) -> list[dict]:
    return [_build_connection_for_allocation(rental_id, item, index) for index, item in enumerate(allocations)]


def fetch_rental_detail(conn, rental_id: int, user_id: int | None = None) -> dict | None:
    if user_id is None:
        rental = conn.execute("SELECT * FROM rentals WHERE id = ?", (rental_id,)).fetchone()
    else:
        rental = conn.execute(
            "SELECT * FROM rentals WHERE id = ? AND user_id = ?",
            (rental_id, user_id),
        ).fetchone()
    if not rental:
        return None
    rental = settle_rental_if_balance_exhausted(conn, rental)
    live_duration_seconds = rental["duration_seconds"]
    live_user_total_amount = rental["user_total_amount"]
    if rental["status"] == ACTIVE_STATUS:
        live_duration_seconds = _calculate_duration_seconds(rental["started_at"], now_iso())
        live_user_total_amount, _ = _calculate_amounts(rental, live_duration_seconds)

    allocations = conn.execute(
        """
        SELECT
            ra.hourly_user_price,
            ra.hourly_power_cost,
            ra.allocated_cards,
            ra.device_indices,
            c.cabinet_code,
            c.location,
            c.cabinet_type,
            c.capacity_cards,
            c.host_ip,
            c.ssh_port
        FROM rental_allocations ra
        JOIN cabinets c ON c.id = ra.cabinet_id
        WHERE ra.rental_id = ?
        ORDER BY c.cabinet_code ASC
        """,
        (rental_id,),
    ).fetchall()
    serialized_allocations = [_serialize_allocation(row) for row in allocations]
    return {
        "success": True,
        "rental_id": rental["id"],
        "user_id": rental["user_id"],
        "card_type": rental["card_type"],
        "card_label": card_label(rental["card_type"], rental["cabinet_type"]),
        "cabinet_type": rental["cabinet_type"],
        "card_count": rental["card_count"],
        "status": rental["status"],
        "stop_reason": rental.get("stop_reason"),
        "started_at": rental["started_at"],
        "ended_at": rental["ended_at"],
        "duration_seconds": live_duration_seconds,
        "hourly_user_price_total": round2(rental["hourly_user_price_total"]),
        "hourly_power_cost_total": round2(rental["hourly_power_cost_total"]),
        "power_cost_mode": "estimated",
        "power_cost_label": "预估电费成本",
        "user_total_amount": round2(live_user_total_amount),
        "power_cost_total": round2(rental["power_cost_total"]),
        "allocations": serialized_allocations,
        "connection": _build_connection_payload(rental["id"], serialized_allocations),
        "connections": _build_connections_payload(rental["id"], serialized_allocations),
        "provisioning_status": "ready" if serialized_allocations else "pending",
    }


def get_rental(rental_id: int, user_id: int) -> dict:
    with transaction() as conn:
        detail = fetch_rental_detail(conn, rental_id, user_id=user_id)
        if detail is None:
            raise AppError("RENTAL_NOT_FOUND", "租单不存在", 404)
        return detail


def create_rental(
    user_id: int,
    card_type: str,
    cabinet_type: str,
    card_count: int,
) -> dict:
    started_at = now_iso()
    current_pricing_period = resolve_timeslot(parse_iso(started_at))
    cost_column = "day_hourly_power_cost" if current_pricing_period == "day" else "night_hourly_power_cost"

    with transaction() as conn:
        try:
            hourly_user_price_total = get_hourly_user_price_total(card_type, cabinet_type, card_count)
            allocation_policy = get_allocation_policy(card_type, cabinet_type)
            min_card_count = get_min_card_count(card_type, cabinet_type)
        except PriceRuleNotFoundError as exc:
            raise AppError("USER_PRICE_CONFIG_NOT_FOUND", str(exc), 400) from exc
        except CardCountRuleError as exc:
            raise AppError("INVALID_CARD_COUNT", str(exc), 400) from exc
        lock_clause = " FOR UPDATE SKIP LOCKED" if conn.backend == "postgres" else ""
        candidate_rows = conn.execute(
            f"""
            SELECT *,
                ({cost_column} * 1.0 / capacity_cards) AS unit_power_cost,
                (capacity_cards - active_card_count) AS available_cards
            FROM cabinets
            WHERE card_type = ? AND cabinet_type = ? AND status IN ('available', 'offline')
              AND active_card_count < capacity_cards
            ORDER BY
                ({cost_column} * 1.0 / capacity_cards) ASC,
                CASE status WHEN 'available' THEN 1 WHEN 'offline' THEN 2 ELSE 3 END,
                active_card_count DESC,
                cabinet_code ASC
            {lock_clause}
            """,
            (card_type, cabinet_type),
        ).fetchall()

        if allocation_policy == "same_cabinet_required":
            selected = _select_grouped_allocations(
                candidate_rows,
                card_count,
                min_cards_per_machine=min_card_count,
            )
        else:
            selected = _select_spread_allocations(candidate_rows, card_count)

        if not selected:
            raise AppError("NO_AVAILABLE_CARDS", "当前时段该卡型可租卡数不足", 409)

        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            raise AppError("USER_NOT_FOUND", "用户不存在", 404)
        if float(user["balance"]) < hourly_user_price_total:
            raise AppError(
                "INSUFFICIENT_BALANCE",
                f"余额不足，至少需要覆盖 1 小时费用 {round2(hourly_user_price_total)} 元",
                402,
            )

        hourly_power_cost_total = 0.0
        for index, row in enumerate(selected):
            allocated_cards = int(row["allocated_cards"])
            first_device_index = int(row["active_card_count"])
            device_indices = list(range(first_device_index, first_device_index + allocated_cards))
            allocation_power_cost = float(row["unit_power_cost"]) * allocated_cards
            selected[index] = {
                **row,
                "allocated_cards": allocated_cards,
                "device_indices": device_indices,
                "allocation_power_cost": allocation_power_cost,
            }
            hourly_power_cost_total += allocation_power_cost

        unit_user_price = hourly_user_price_total / card_count
        primary_ip = selected[0]["host_ip"] if selected else ""

        rental_id = conn.execute_insert(
            """
            INSERT INTO rentals (
                user_id, card_type, cabinet_type, cabinet_count, card_count,
                started_at, ended_at, duration_seconds,
                hourly_user_price_total, hourly_power_cost_total,
                user_total_amount, power_cost_total,
                status, ip, password
            ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, NULL, NULL, 'active', ?, ?)
            """,
            (
                user_id,
                card_type,
                cabinet_type,
                len(selected),
                card_count,
                started_at,
                hourly_user_price_total,
                hourly_power_cost_total,
                primary_ip,
                "managed-by-platform",
            ),
        )

        remaining_user_price = hourly_user_price_total
        for index, row in enumerate(selected):
            allocation_user_price = (
                remaining_user_price
                if index == len(selected) - 1
                else round2(unit_user_price * row["allocated_cards"])
            )
            remaining_user_price -= allocation_user_price
            conn.execute(
                """
                INSERT INTO rental_allocations (
                    rental_id, cabinet_id, allocated_cards, device_indices, hourly_user_price, hourly_power_cost
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    rental_id,
                    row["id"],
                    row["allocated_cards"],
                    ",".join(str(item) for item in row["device_indices"]),
                    round2(allocation_user_price),
                    round2(row["allocation_power_cost"]),
                ),
            )
            updated_active_card_count = int(row["active_card_count"]) + int(row["allocated_cards"])
            conn.execute(
                "UPDATE cabinets SET active_card_count = ?, status = ?, last_idle_at = NULL WHERE id = ?",
                (
                    updated_active_card_count,
                    cabinet_status_from_active_cards(updated_active_card_count, int(row["capacity_cards"])),
                    row["id"],
                ),
            )

        detail = fetch_rental_detail(conn, rental_id, user_id=user_id)
        if detail is None:
            raise AppError("RENTAL_CREATE_FAILED", "租单创建失败", 500)
        return detail


def cancel_rental(rental_id: int, user_id: int) -> dict:
    with transaction() as conn:
        rental = conn.execute(
            "SELECT * FROM rentals WHERE id = ? AND user_id = ?",
            (rental_id, user_id),
        ).fetchone()
        if not rental:
            raise AppError("RENTAL_NOT_FOUND", "租单不存在", 404)

        rental = settle_rental_if_balance_exhausted(conn, rental)

        if rental["status"] != ACTIVE_STATUS:
            return {
                "success": True,
                "rental_id": rental["id"],
                "status": rental["status"],
                "started_at": rental["started_at"],
                "ended_at": rental["ended_at"],
                "duration_seconds": rental["duration_seconds"],
                "hourly_user_price_total": round2(rental["hourly_user_price_total"]),
                "hourly_power_cost_total": round2(rental["hourly_power_cost_total"]),
                "user_total_amount": round2(rental["user_total_amount"]),
                "power_cost_total": round2(rental["power_cost_total"]),
            }

        ended_at = now_iso()
        duration_seconds = _calculate_duration_seconds(rental["started_at"], ended_at)
        user_total_amount, _ = _calculate_amounts(rental, duration_seconds)
        user = conn.execute("SELECT balance FROM users WHERE id = ?", (user_id,)).fetchone()
        available_balance = float(user["balance"]) if user else 0.0
        charge_amount = min(user_total_amount, available_balance)
        updated = _finish_active_rental(conn, rental, ended_at, MANUAL_STOP_REASON, charge_amount)
        return {
            "success": True,
            "rental_id": updated["id"],
            "status": updated["status"],
            "stop_reason": updated.get("stop_reason"),
            "started_at": updated["started_at"],
            "ended_at": updated["ended_at"],
            "duration_seconds": updated["duration_seconds"],
            "hourly_user_price_total": round2(updated["hourly_user_price_total"]),
            "hourly_power_cost_total": round2(updated["hourly_power_cost_total"]),
            "user_total_amount": round2(updated["user_total_amount"]),
            "power_cost_total": round2(updated["power_cost_total"]),
        }
