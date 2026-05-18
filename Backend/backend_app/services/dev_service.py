from __future__ import annotations

from ..db import transaction
from ..errors import AppError
def release_cabinets(
    card_type: str | None = None,
    cabinet_type: str | None = None,
    count: int = 1,
    from_statuses: list[str] | None = None,
) -> dict:
    if count < 1:
        raise AppError("INVALID_RELEASE_COUNT", "count 必须大于等于 1", 400)

    allowed_statuses = from_statuses or ["rented", "offline"]
    invalid_statuses = [status for status in allowed_statuses if status not in {"available", "rented", "offline"}]
    if invalid_statuses:
        raise AppError("INVALID_RELEASE_STATUS", "from_statuses 包含非法状态", 400)

    where_clauses = ["status IN ({})".format(",".join("?" for _ in allowed_statuses))]
    params: list[object] = list(allowed_statuses)
    if card_type:
        where_clauses.append("card_type = ?")
        params.append(card_type)
    if cabinet_type:
        where_clauses.append("cabinet_type = ?")
        params.append(cabinet_type)

    sql = f"""
        SELECT id, cabinet_code, location, card_type, cabinet_type, status
        FROM cabinets
        WHERE {" AND ".join(where_clauses)}
        ORDER BY
            CASE status WHEN 'rented' THEN 1 WHEN 'offline' THEN 2 ELSE 3 END,
            cabinet_code ASC
        LIMIT ?
    """
    params.append(count)

    with transaction() as conn:
        cabinets = conn.execute(sql, params).fetchall()
        if not cabinets:
            raise AppError("NO_MATCHING_CABINETS", "没有可释放的机柜", 404)

        released_ids = [cabinet["id"] for cabinet in cabinets]
        conn.execute(
            f"UPDATE cabinets SET active_card_count = 0, status = 'offline', last_idle_at = NULL WHERE id IN ({','.join('?' for _ in released_ids)})",
            released_ids,
        )

        return {
            "success": True,
            "released_count": len(cabinets),
            "released_cabinets": [
                {
                    "cabinet_code": cabinet["cabinet_code"],
                    "location": cabinet["location"],
                    "card_type": cabinet["card_type"],
                    "cabinet_type": cabinet["cabinet_type"],
                    "previous_status": cabinet["status"],
                    "current_status": "offline",
                }
                for cabinet in cabinets
            ],
        }
