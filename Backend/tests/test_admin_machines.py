from __future__ import annotations

from backend_app.db import connection_scope, init_db


def admin_headers(client) -> dict:
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "Admin@2026"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def user_headers(client) -> dict:
    response = client.post(
        "/api/auth/login",
        json={"username": "gpu_user_001", "password": "123456"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_admin_machine_list_requires_admin(client):
    assert client.get("/api/admin/machines").status_code == 401
    response = client.get("/api/admin/machines", headers=user_headers(client))
    assert response.status_code == 403


def test_admin_can_create_machine_waiting_for_agent(client):
    headers = admin_headers(client)
    response = client.post(
        "/api/admin/machines",
        headers=headers,
        json={
            "cabinet_code": "10.20.12.230-4090",
            "location": "位置2",
            "host_ip": "10.20.12.230",
            "ssh_port": 22,
            "card_type": "4090",
            "cabinet_type": "单卡机柜",
            "capacity_cards": 1,
            "day_hourly_power_cost": 2.4,
            "night_hourly_power_cost": 2.0,
        },
    )

    assert response.status_code == 200
    machine = response.json()["machine"]
    assert machine["cabinet_code"] == "10.20.12.230-4090"
    assert machine["agent_status"] == "waiting"
    assert machine["available_cards"] == 0
    assert machine["blocked_cards"] == 1

    cards = client.get("/api/cards").json()["items"]
    option_4090 = next(item for item in cards if item["card_type"] == "4090")["pricing_options"][0]
    created = next(item for item in option_4090["machines"] if item["cabinet_code"] == "10.20.12.230-4090")
    assert created["available_cards"] == 0
    assert created["blocked_cards"] == 1


def test_admin_created_machine_becomes_rentable_after_heartbeat(client):
    headers = admin_headers(client)
    client.post(
        "/api/admin/machines",
        headers=headers,
        json={
            "cabinet_code": "10.20.12.231-3090",
            "location": "位置2",
            "host_ip": "10.20.12.231",
            "ssh_port": 22,
            "card_type": "3090",
            "cabinet_type": "单卡机柜",
            "capacity_cards": 1,
            "day_hourly_power_cost": 1.8,
            "night_hourly_power_cost": 1.6,
        },
    )

    heartbeat = client.post(
        "/api/nodes/heartbeat",
        headers={"Authorization": "Bearer local-agent-token"},
        json={
            "node_id": "10.20.12.231",
            "host_ip": "10.20.12.231",
            "accelerator_type": "nvidia",
            "devices": [
                {
                    "index": 0,
                    "name": "RTX 3090",
                    "health": "OK",
                    "usage_percent": 0,
                    "memory_used_mb": 0,
                    "memory_total_mb": 24576,
                    "process_count": 0,
                }
            ],
        },
    )
    assert heartbeat.status_code == 200

    machines = client.get("/api/admin/machines", headers=headers).json()["machines"]
    machine = next(item for item in machines if item["cabinet_code"] == "10.20.12.231-3090")
    assert machine["agent_status"] == "online"
    assert machine["available_cards"] == 1
    assert machine["blocked_cards"] == 0


def test_admin_created_machine_survives_seed_sync(client):
    headers = admin_headers(client)
    client.post(
        "/api/admin/machines",
        headers=headers,
        json={
            "cabinet_code": "10.20.12.232-4090",
            "location": "位置2",
            "host_ip": "10.20.12.232",
            "ssh_port": 22,
            "card_type": "4090",
            "cabinet_type": "单卡机柜",
            "capacity_cards": 1,
            "day_hourly_power_cost": 2.4,
            "night_hourly_power_cost": 2.0,
        },
    )

    init_db()

    with connection_scope() as conn:
        row = conn.execute(
            "SELECT cabinet_code, location FROM cabinets WHERE cabinet_code = ?",
            ("10.20.12.232-4090",),
        ).fetchone()
    assert row["location"] == "位置2"
