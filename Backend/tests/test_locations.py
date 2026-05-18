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

    assert items["位置2"]["node_status"] == "available"
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
    assert pairs == [
        ("3090", "单卡机柜"),
        ("4090", "单卡机柜"),
    ]

    location_four_breakdown = items["位置4"]["cabinet_breakdown"]
    assert ("V100X2", "单卡机柜") in [
        (entry["card_type"], entry["cabinet_type"]) for entry in location_four_breakdown
    ]
    assert sum(entry["available_cards"] for entry in location_four_breakdown) >= 1
