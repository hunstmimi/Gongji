from __future__ import annotations


def test_locations_summary_shape(client):
    response = client.get("/api/locations/summary")

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "edges" in data
    assert len(data["items"]) == 4
    assert len(data["edges"]) == 4
    assert "cabinet_breakdown" in data["items"][0]
    assert len(data["items"][0]["cabinet_breakdown"]) >= 1


def test_locations_summary_counts_and_status(client):
    response = client.get("/api/locations/summary")
    items = {item["location"]: item for item in response.json()["items"]}

    assert items["位置1"]["total_cabinets"] > 0
    assert items["位置1"]["available_cards"] > 0
    assert items["位置1"]["node_status"] == "available"

    assert items["位置2"]["total_cabinets"] == 2
    assert items["位置2"]["available_cards"] == 2
    assert items["位置2"]["node_status"] == "available"

    assert items["位置3"]["node_status"] == "available"
    assert items["位置4"]["available_cards"] >= 1


def test_locations_summary_breakdown_rolls_up_to_location_totals(client):
    response = client.get("/api/locations/summary")
    items = response.json()["items"]

    for item in items:
        breakdown = item["cabinet_breakdown"]
        assert sum(entry["total_cabinets"] for entry in breakdown) == item["total_cabinets"]
        assert sum(entry["available_cabinets"] for entry in breakdown) == item["available_cabinets"]
        assert sum(entry["online_available_cabinets"] for entry in breakdown) == item["online_available_cabinets"]
        assert sum(entry["rented_cabinets"] for entry in breakdown) == item["rented_cabinets"]
        assert sum(entry["offline_cabinets"] for entry in breakdown) == item["offline_cabinets"]


def test_locations_summary_breakdown_contains_expected_machine_types(client):
    response = client.get("/api/locations/summary")
    items = {item["location"]: item for item in response.json()["items"]}
    location_one_breakdown = items["位置1"]["cabinet_breakdown"]

    pairs = [(entry["card_type"], entry["cabinet_type"]) for entry in location_one_breakdown]
    assert pairs == [("3090", "单卡机柜")]

    location_two_breakdown = items["位置2"]["cabinet_breakdown"]
    assert [
        (entry["card_type"], entry["cabinet_type"], entry["total_cabinets"])
        for entry in location_two_breakdown
    ] == [("3090", "单卡机柜", 1), ("4090", "单卡机柜", 1)]

    location_four_breakdown = items["位置4"]["cabinet_breakdown"]
    assert ("910B3", "8卡机柜") in [
        (entry["card_type"], entry["cabinet_type"]) for entry in location_four_breakdown
    ]
    assert sum(entry["available_cards"] for entry in location_four_breakdown) == 4
    assert sum(entry["managed_cards"] for entry in location_four_breakdown) == 4
    assert sum(entry["total_cards"] for entry in location_four_breakdown) == 8


def test_locations_summary_auto_adds_new_location_node(client):
    login = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "Admin@2026"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    created = client.post(
        "/api/admin/machines",
        headers=headers,
        json={
            "cabinet_code": "10.20.12.240-4090",
            "location": "位置5",
            "host_ip": "10.20.12.240",
            "ssh_port": 22,
            "card_type": "4090",
            "cabinet_type": "单卡机柜",
            "capacity_cards": 1,
            "day_hourly_power_cost": 2.4,
            "night_hourly_power_cost": 2.0,
        },
    )
    assert created.status_code == 200

    response = client.get("/api/locations/summary")
    data = response.json()
    items = {item["location"]: item for item in data["items"]}

    assert "位置5" in items
    assert items["位置5"]["total_cabinets"] == 1
    assert items["位置5"]["x_ratio"] != 0.5
    assert items["位置5"]["y_ratio"] != 0.5
    assert any(edge["from"] == "位置4" and edge["to"] == "位置5" for edge in data["edges"])
