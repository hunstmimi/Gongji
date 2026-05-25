from __future__ import annotations

from datetime import datetime

from backend_app.config import TIMEZONE


def login_headers(client, username="admin", password="Admin@2026") -> dict:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_admin_usage_requires_login(client):
    response = client.get("/api/admin/usage")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_admin_usage_rejects_normal_user(client):
    headers = login_headers(client, username="gpu_user_001", password="123456")
    response = client.get("/api/admin/usage", headers=headers)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_admin_usage_reports_current_cards_and_monthly_ranking(client, monkeypatch):
    started = datetime(2026, 5, 10, 10, 0, tzinfo=TIMEZONE)
    current = datetime(2026, 5, 10, 12, 0, tzinfo=TIMEZONE)
    monkeypatch.setattr("backend_app.utils.now_dt", lambda: started)
    user_headers = login_headers(client, username="gpu_user_001", password="123456")
    admin_headers = login_headers(client)

    create = client.post(
        "/api/rentals",
        headers=user_headers,
        json={
            "card_type": "910B3",
            "cabinet_type": "8卡机柜",
            "card_count": 2,
            "preferred_cabinet_code": "10.26.6.48-910B3",
        },
    )
    assert create.status_code == 200

    monkeypatch.setattr("backend_app.services.admin_service.now_dt", lambda: current)
    response = client.get("/api/admin/usage", headers=admin_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["month"] == "2026-05"
    assert data["summary"]["total_current_cards"] == 2
    assert data["summary"]["active_users"] == 1
    assert data["ranking"][0]["username"] == "gpu_user_001"
    assert data["ranking"][0]["month_card_hours"] == 4

    user_row = next(item for item in data["users"] if item["username"] == "gpu_user_001")
    assert user_row["current_card_count"] == 2
    assert user_row["current_rental_count"] == 1
    assert user_row["month_card_hours"] == 4
    assert user_row["active_rentals"][0]["card_type"] == "910B3"
