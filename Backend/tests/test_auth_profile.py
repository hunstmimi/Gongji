from __future__ import annotations


def login_headers(client) -> dict:
    response = client.post(
        "/api/auth/login",
        json={"username": "gpu_user_001", "password": "123456"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_login_returns_masked_phone_and_balance(client):
    response = client.post(
        "/api/auth/login",
        json={"username": "gpu_user_001", "password": "123456"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["user"]["phone_masked"] == "158****0746"
    assert data["user"]["balance"] == 286.4


def test_dashboard_returns_empty_active_and_seeded_history(client):
    headers = login_headers(client)

    response = client.get("/api/me/dashboard", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["active_rentals_count"] == 0
    assert data["active_rentals"] == []
    assert data["history_rentals_count"] >= 2
    assert data["history_rentals"][0]["total_amount"] is not None


def test_recharge_updates_balance(client):
    headers = login_headers(client)

    response = client.post("/api/me/balance/recharge", headers=headers, json={"amount": 50})

    assert response.status_code == 200
    data = response.json()
    assert data["balance"] == 336.4
