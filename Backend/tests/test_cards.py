from __future__ import annotations


def test_cards_returns_expected_items(client):
    response = client.get("/api/cards")

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) == 3

    card_types = [item["card_type"] for item in data["items"]]
    assert card_types == ["3090", "4090", "910B3"]

    first = data["items"][0]
    assert first["title"] == "3090"
    assert "display_price" in first

    by_type = {item["card_type"]: item for item in data["items"]}
    options_4090 = {item["cabinet_type"]: item for item in by_type["4090"]["pricing_options"]}
    assert set(options_4090) == {"单卡机柜"}
    assert options_4090["单卡机柜"]["min_card_count"] == 1
    assert options_4090["单卡机柜"]["capacity_cards"] == 1
    assert options_4090["单卡机柜"]["max_card_count"] >= 1

    option_910b3 = by_type["910B3"]["pricing_options"][0]
    assert option_910b3["cabinet_type"] == "8卡机柜"
    assert option_910b3["min_card_count"] == 1
    assert option_910b3["available_cards"] == 4
    assert option_910b3["managed_cards"] == 4
    assert option_910b3["total_cards"] == 8
    assert option_910b3["available_memory_gb"] == 256
    assert option_910b3["max_card_count"] == 4
    assert option_910b3["capacity_cards"] == 8
    assert option_910b3["machines"][0]["cabinet_code"] == "10.26.6.48-910B3"
    assert option_910b3["machines"][0]["available_cards"] == 4
    assert option_910b3["machines"][0]["managed_cards"] == 4
    assert option_910b3["machines"][0]["disabled_cards"] == 4
