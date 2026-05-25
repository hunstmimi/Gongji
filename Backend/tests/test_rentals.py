from __future__ import annotations

from datetime import datetime

from backend_app.config import TIMEZONE
from backend_app.db import connection_scope, transaction
from backend_app.errors import AppError
from backend_app.services import provision_service


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
            "card_type": "3090",
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
    assert data["hourly_user_price_total"] == 8.4
    assert data["hourly_power_cost_total"] == 2.7
    assert data["power_cost_mode"] == "estimated"
    assert data["provisioning_status"] == "ready"
    assert len(data["allocations"]) == 2
    assert [item["cabinet_code"] for item in data["allocations"]] == [
        "10.20.12.225-3090",
        "10.20.12.227-3090",
    ]
    assert data["connection"]["ip"] == "10.20.12.225"
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
    assert rented_count >= 2


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
            "card_type": "910B3",
            "cabinet_type": "8卡机柜",
            "card_count": 5,
        },
    )

    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "INVALID_CARD_COUNT"


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
    assert data["hourly_user_price_total"] == 8.4
    assert data["hourly_power_cost_total"] == 2.7

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
            (2.3, "10.20.12.225-3090"),
        )
        conn.execute(
            """
            UPDATE cabinets
            SET status = 'offline', active_card_count = 0, last_idle_at = NULL, night_hourly_power_cost = ?
            WHERE cabinet_code = ?
            """,
            (1.4, "10.20.12.227-3090"),
        )

    response = client.post(
        "/api/rentals",
        headers=headers,
        json={
            "card_type": "3090",
            "cabinet_type": "单卡机柜",
            "card_count": 1,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert [item["cabinet_code"] for item in data["allocations"]] == ["10.20.12.227-3090"]
    assert data["hourly_power_cost_total"] == 1.4

    with connection_scope() as conn:
        status = conn.execute(
            "SELECT status, active_card_count FROM cabinets WHERE cabinet_code = ?",
            ("10.20.12.227-3090",),
        ).fetchone()
    assert status["status"] == "rented"
    assert status["active_card_count"] == 1


def test_create_rental_can_target_preferred_cabinet(client, monkeypatch):
    patch_now(monkeypatch, datetime(2026, 4, 30, 20, 0, tzinfo=TIMEZONE))
    headers = login_headers(client)

    response = client.post(
        "/api/rentals",
        headers=headers,
        json={
            "card_type": "3090",
            "cabinet_type": "单卡机柜",
            "card_count": 1,
            "preferred_cabinet_code": "10.20.12.227-3090",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["allocations"][0]["cabinet_code"] == "10.20.12.227-3090"


def test_create_rental_can_target_preferred_location(client, monkeypatch):
    patch_now(monkeypatch, datetime(2026, 4, 30, 20, 0, tzinfo=TIMEZONE))
    headers = login_headers(client)

    response = client.post(
        "/api/rentals",
        headers=headers,
        json={
            "card_type": "4090",
            "cabinet_type": "单卡机柜",
            "card_count": 1,
            "preferred_location": "位置3",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["allocations"][0]["location"] == "位置3"


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


def test_create_and_cancel_rental_marks_specific_gpu_devices(client, monkeypatch):
    patch_now(
        monkeypatch,
        datetime(2026, 4, 30, 20, 0, tzinfo=TIMEZONE),
        datetime(2026, 4, 30, 20, 30, tzinfo=TIMEZONE),
    )
    headers = login_headers(client)
    created = create_sample_rental(client, headers)
    rental_id = created["rental_id"]

    with connection_scope() as conn:
        rows = conn.execute(
            """
            SELECT c.cabinet_code, g.gpu_index, g.status, g.rental_id
            FROM gpu_devices g
            JOIN cabinets c ON c.id = g.cabinet_id
            WHERE g.rental_id = ?
            ORDER BY c.cabinet_code, g.gpu_index
            """,
            (rental_id,),
        ).fetchall()

    assert [(row["cabinet_code"], row["gpu_index"], row["status"]) for row in rows] == [
        ("10.20.12.225-3090", 0, "rented"),
        ("10.20.12.227-3090", 0, "rented"),
    ]
    assert created["connections"][0]["command"].startswith("ssh rent_")

    response = client.post(f"/api/rentals/{rental_id}/cancel", headers=headers)
    assert response.status_code == 200

    with connection_scope() as conn:
        remaining = conn.execute(
            "SELECT COUNT(*) AS count FROM gpu_devices WHERE rental_id = ?",
            (rental_id,),
        ).fetchone()["count"]
    assert remaining == 0


def test_create_910b3_multi_card_rental_allocates_single_node_indices(client, monkeypatch):
    patch_now(monkeypatch, datetime(2026, 4, 30, 20, 0, tzinfo=TIMEZONE))
    headers = login_headers(client)

    response = client.post(
        "/api/rentals",
        headers=headers,
        json={
            "card_type": "910B3",
            "cabinet_type": "8卡机柜",
            "card_count": 3,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["card_count"] == 3
    assert data["hourly_user_price_total"] == 22.8
    assert len(data["allocations"]) == 1
    allocation = data["allocations"][0]
    assert allocation["cabinet_code"] == "10.26.6.48-910B3"
    assert allocation["device_indices"] == [0, 1, 2]
    assert data["connection"]["command"].startswith("ssh rent_")

    with connection_scope() as conn:
        rows = conn.execute(
            """
            SELECT gpu_index, status, rental_id
            FROM gpu_devices
            WHERE cabinet_id = (
                SELECT id FROM cabinets WHERE cabinet_code = '10.26.6.48-910B3'
            )
            ORDER BY gpu_index
            """,
        ).fetchall()

    assert [(row["gpu_index"], row["status"]) for row in rows] == [
        (0, "rented"),
        (1, "rented"),
        (2, "rented"),
        (3, "available"),
        (4, "disabled"),
        (5, "disabled"),
        (6, "disabled"),
        (7, "disabled"),
    ]


def test_create_910b3_four_card_rental_never_allocates_disabled_devices(client, monkeypatch):
    patch_now(monkeypatch, datetime(2026, 4, 30, 20, 0, tzinfo=TIMEZONE))
    headers = login_headers(client)

    response = client.post(
        "/api/rentals",
        headers=headers,
        json={
            "card_type": "910B3",
            "cabinet_type": "8卡机柜",
            "card_count": 4,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["allocations"][0]["device_indices"] == [0, 1, 2, 3]
    assert data["connection"]["visible_devices"] == "0,1,2,3"


def test_create_910b3_five_card_rental_rejected_by_backend_limit(client, monkeypatch):
    patch_now(monkeypatch, datetime(2026, 4, 30, 20, 0, tzinfo=TIMEZONE))
    headers = login_headers(client)

    response = client.post(
        "/api/rentals",
        headers=headers,
        json={
            "card_type": "910B3",
            "cabinet_type": "8卡机柜",
            "card_count": 5,
        },
    )

    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "INVALID_CARD_COUNT"


def test_node_heartbeat_marks_unknown_occupied_devices_unrentable(client, monkeypatch):
    patch_now(monkeypatch, datetime(2026, 4, 30, 20, 0, tzinfo=TIMEZONE))
    response = client.post(
        "/api/nodes/heartbeat",
        headers={"Authorization": "Bearer local-agent-token"},
        json={
            "node_id": "sribd-910b3-01",
            "host_ip": "10.26.6.48",
            "accelerator_type": "ascend",
            "devices": [
                {"index": 0, "name": "910B3", "health": "OK", "process_count": 1, "hbm_used_mb": 12000, "hbm_total_mb": 65536},
                {"index": 1, "name": "910B3", "health": "OK", "process_count": 0, "hbm_used_mb": 3400, "hbm_total_mb": 65536},
                {"index": 2, "name": "910B3", "health": "OK", "process_count": 0, "hbm_used_mb": 3400, "hbm_total_mb": 65536},
                {"index": 3, "name": "910B3", "health": "OK", "process_count": 0, "hbm_used_mb": 3400, "hbm_total_mb": 65536},
            ],
        },
    )
    assert response.status_code == 200
    assert response.json()["updated_devices"] == 4

    cards = client.get("/api/cards").json()["items"]
    option_910b3 = next(item for item in cards if item["card_type"] == "910B3")["pricing_options"][0]
    assert option_910b3["available_cards"] == 3
    assert option_910b3["max_card_count"] == 3

    headers = login_headers(client)
    rental_response = client.post(
        "/api/rentals",
        headers=headers,
        json={
            "card_type": "910B3",
            "cabinet_type": "8卡机柜",
            "card_count": 2,
        },
    )
    assert rental_response.status_code == 200
    allocation = rental_response.json()["allocations"][0]
    assert allocation["device_indices"] == [1, 2]


def test_provision_payload_scales_cpu_memory_and_shm_by_card_count(monkeypatch):
    monkeypatch.setenv("COMPUTE_RENTAL_AGENT_DRY_RUN", "true")
    monkeypatch.setenv("COMPUTE_RENTAL_CPU_PER_CARD", "6")
    monkeypatch.setenv("COMPUTE_RENTAL_MEMORY_PER_CARD_GB", "48")
    monkeypatch.setenv("COMPUTE_RENTAL_SHM_PER_CARD_GB", "12")

    payload = provision_service.create_instance(
        88,
        {
            "cabinet_code": "10.26.6.48-910B3",
            "host_ip": "10.26.6.48",
            "device_indices": [1, 2],
            "allocated_cards": 2,
        },
        0,
    )

    assert payload["cpu_limit"] == 12
    assert payload["memory_limit_gb"] == 96
    assert payload["shm_size"] == "24g"


def test_provisioning_failure_releases_reserved_devices(client, monkeypatch):
    patch_now(monkeypatch, datetime(2026, 4, 30, 20, 0, tzinfo=TIMEZONE))

    def fail_create_instance(*_args, **_kwargs):
        raise AppError("AGENT_REQUEST_FAILED", "节点 Agent 调用失败", 502)

    monkeypatch.setattr("backend_app.services.rental_service.create_instance", fail_create_instance)
    headers = login_headers(client)
    response = client.post(
        "/api/rentals",
        headers=headers,
        json={
            "card_type": "910B3",
            "cabinet_type": "8卡机柜",
            "card_count": 2,
        },
    )

    assert response.status_code == 502
    with connection_scope() as conn:
        rows = conn.execute(
            """
            SELECT gpu_index, status, rental_id
            FROM gpu_devices
            WHERE cabinet_id = (
                SELECT id FROM cabinets WHERE cabinet_code = '10.26.6.48-910B3'
            )
            ORDER BY gpu_index
            """,
        ).fetchall()
        failed_rental = conn.execute(
            "SELECT status, stop_reason FROM rentals WHERE card_type = '910B3' ORDER BY id DESC LIMIT 1"
        ).fetchone()

    assert [(row["gpu_index"], row["status"], row["rental_id"]) for row in rows] == [
        (0, "available", None),
        (1, "available", None),
        (2, "available", None),
        (3, "available", None),
        (4, "disabled", None),
        (5, "disabled", None),
        (6, "disabled", None),
        (7, "disabled", None),
    ]
    assert failed_rental["status"] == "cancelled"
    assert failed_rental["stop_reason"] == "provisioning_failed"


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



