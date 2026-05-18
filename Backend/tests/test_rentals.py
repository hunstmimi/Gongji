from __future__ import annotations

from datetime import datetime

from backend_app.db import connection_scope, transaction
from backend_app.config import TIMEZONE


def patch_now(monkeypatch, *datetimes: datetime) -> None:
    values = list(datetimes)
    last_value = values[-1]

    def fake_now():
        if values:
            return values.pop(0)
        return last_value

    monkeypatch.setattr("backend_app.utils.now_dt", fake_now)


def login_headers(client) -> dict:
    response = client.post(
        "/api/auth/login",
        json={"username": "gpu_user_001", "password": "123456"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_sample_rental(client, headers: dict) -> dict:
    response = client.post(
        "/api/rentals",
        headers=headers,
        json={
            "card_type": "4090",
            "cabinet_type": "单卡机柜",
            "card_count": 2,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    return data


def test_create_rental_requires_login(client, monkeypatch):
    patch_now(monkeypatch, datetime(2026, 4, 30, 20, 0, tzinfo=TIMEZONE))
    response = client.post(
        "/api/rentals",
        json={
            "card_type": "4090",
            "cabinet_type": "单卡机柜",
            "card_count": 1,
        },
    )

    assert response.status_code == 401
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "UNAUTHORIZED"


def test_create_rental_success(client, monkeypatch):
    patch_now(monkeypatch, datetime(2026, 4, 30, 20, 0, tzinfo=TIMEZONE))
    headers = login_headers(client)
    data = create_sample_rental(client, headers)

    assert data["status"] == "active"
    assert data["card_count"] == 2
    assert data["hourly_user_price_total"] == 22.8
    assert data["hourly_power_cost_total"] == 3.7
    assert data["power_cost_mode"] == "estimated"
    assert data["provisioning_status"] == "ready"
    assert len(data["allocations"]) == 2
    assert [item["cabinet_code"] for item in data["allocations"]] == [
        "10.21.53.156-4090",
        "10.21.53.162-4090",
    ]
    assert data["connection"]["ip"] == "10.21.53.156"
    assert data["connection"]["connection_type"] == "rental_environment"
    assert data["connection"]["provisioning_status"] == "ready"
    assert data["connection"]["environment_id"] == f"rental-{data['rental_id']}-1"
    assert data["connection"]["username"].startswith(f"rent_{data['rental_id']}_")
    assert data["connection"]["port"] != 22
    assert f"-p {data['connection']['port']}" in data["connection"]["command"]
    assert len(data["connections"]) == 2
    assert data["connections"][0]["visible_devices"] == "0"
    assert data["connections"][1]["environment_id"] == f"rental-{data['rental_id']}-2"

    with connection_scope() as conn:
        rental = conn.execute("SELECT user_id FROM rentals WHERE id = ?", (data["rental_id"],)).fetchone()
        rented_count = conn.execute(
            "SELECT COUNT(*) AS count FROM cabinets WHERE status = 'rented'"
        ).fetchone()["count"]
    assert rental["user_id"] == 1
    assert rented_count >= 3


def test_get_rental_detail(client, monkeypatch):
    patch_now(monkeypatch, datetime(2026, 4, 30, 20, 0, tzinfo=TIMEZONE))
    headers = login_headers(client)
    created = create_sample_rental(client, headers)
    rental_id = created["rental_id"]

    response = client.get(f"/api/rentals/{rental_id}", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["rental_id"] == rental_id
    assert data["status"] == "active"
    assert len(data["allocations"]) == 2


def test_create_rental_no_available_cabinets_returns_unified_error(client, monkeypatch):
    patch_now(monkeypatch, datetime(2026, 4, 30, 10, 0, tzinfo=TIMEZONE))
    headers = login_headers(client)
    response = client.post(
        "/api/rentals",
        headers=headers,
        json={
            "card_type": "V100X2",
            "cabinet_type": "单卡机柜",
            "card_count": 2,
        },
    )

    assert response.status_code == 409
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "NO_AVAILABLE_CARDS"


def test_get_missing_rental_returns_unified_404(client):
    headers = login_headers(client)
    response = client.get("/api/rentals/99999", headers=headers)

    assert response.status_code == 404
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "RENTAL_NOT_FOUND"


def test_cancel_rental_releases_cabinets_and_computes_totals(client, monkeypatch):
    patch_now(
        monkeypatch,
        datetime(2026, 4, 30, 20, 0, tzinfo=TIMEZONE),
        datetime(2026, 4, 30, 20, 30, tzinfo=TIMEZONE),
    )
    headers = login_headers(client)
    created = create_sample_rental(client, headers)
    rental_id = created["rental_id"]
    codes = [item["cabinet_code"] for item in created["allocations"]]

    response = client.post(f"/api/rentals/{rental_id}/cancel", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "cancelled"
    assert data["duration_seconds"] >= 0
    assert data["hourly_user_price_total"] == 22.8
    assert data["hourly_power_cost_total"] == 3.7

    placeholders = ",".join("?" for _ in codes)
    with connection_scope() as conn:
        rows = conn.execute(
            f"SELECT cabinet_code, status FROM cabinets WHERE cabinet_code IN ({placeholders}) ORDER BY cabinet_code",
            codes,
        ).fetchall()
    assert [row["status"] for row in rows] == ["offline", "offline"]


def test_cancel_rental_is_idempotent(client, monkeypatch):
    patch_now(
        monkeypatch,
        datetime(2026, 4, 30, 20, 0, tzinfo=TIMEZONE),
        datetime(2026, 4, 30, 20, 30, tzinfo=TIMEZONE),
        datetime(2026, 4, 30, 20, 31, tzinfo=TIMEZONE),
    )
    headers = login_headers(client)
    created = create_sample_rental(client, headers)
    rental_id = created["rental_id"]

    first = client.post(f"/api/rentals/{rental_id}/cancel", headers=headers)
    second = client.post(f"/api/rentals/{rental_id}/cancel", headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["status"] == "cancelled"
    assert second.json()["status"] == "cancelled"


def test_create_rental_can_wake_cheaper_offline_cabinet(client, monkeypatch):
    patch_now(monkeypatch, datetime(2026, 4, 30, 20, 0, tzinfo=TIMEZONE))
    headers = login_headers(client)

    with transaction() as conn:
        conn.execute(
            """
            UPDATE cabinets
            SET status = 'available', active_card_count = 0, last_idle_at = NULL, night_hourly_power_cost = ?
            WHERE cabinet_code = ?
            """,
            (2.3, "10.21.53.113-4090"),
        )
        conn.execute(
            """
            UPDATE cabinets
            SET status = 'offline', active_card_count = 0, last_idle_at = NULL, night_hourly_power_cost = ?
            WHERE cabinet_code = ?
            """,
            (1.4, "10.21.53.156-4090"),
        )

    response = client.post(
        "/api/rentals",
        headers=headers,
        json={
            "card_type": "4090",
            "cabinet_type": "单卡机柜",
            "card_count": 1,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert [item["cabinet_code"] for item in data["allocations"]] == ["10.21.53.156-4090"]
    assert data["hourly_power_cost_total"] == 1.4

    with connection_scope() as conn:
        status = conn.execute(
            "SELECT status, active_card_count FROM cabinets WHERE cabinet_code = ?",
            ("10.21.53.156-4090",),
        ).fetchone()
    assert status["status"] == "rented"
    assert status["active_card_count"] == 1


def test_cancel_rental_powers_off_cabinet_when_no_cards_remain(client, monkeypatch):
    patch_now(
        monkeypatch,
        datetime(2026, 4, 30, 20, 0, tzinfo=TIMEZONE),
        datetime(2026, 4, 30, 20, 30, tzinfo=TIMEZONE),
    )
    headers = login_headers(client)
    created = create_sample_rental(client, headers)
    rental_id = created["rental_id"]
    codes = [item["cabinet_code"] for item in created["allocations"]]

    response = client.post(f"/api/rentals/{rental_id}/cancel", headers=headers)

    assert response.status_code == 200
    placeholders = ",".join("?" for _ in codes)
    with connection_scope() as conn:
        rows = conn.execute(
            f"SELECT cabinet_code, status, active_card_count FROM cabinets WHERE cabinet_code IN ({placeholders}) ORDER BY cabinet_code",
            codes,
        ).fetchall()
    assert [row["status"] for row in rows] == ["offline", "offline"]
    assert all(row["active_card_count"] == 0 for row in rows)


def test_validation_error_uses_unified_shape(client):
    headers = login_headers(client)
    response = client.post(
        "/api/rentals",
        headers=headers,
        json={
            "card_type": "4090",
            "cabinet_type": "单卡机柜",
            "card_count": 0,
        },
    )

    assert response.status_code == 422
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "VALIDATION_ERROR"
