from __future__ import annotations


def test_cards_returns_expected_items(client):
    response = client.get("/api/cards")

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) == 3

    card_types = [item["card_type"] for item in data["items"]]
    assert card_types == ["3090", "4090", "V100X2"]

    first = data["items"][0]
    assert first["title"] == "3090"
    assert "display_price" in first

    by_type = {item["card_type"]: item for item in data["items"]}
    options_4090 = {item["cabinet_type"]: item for item in by_type["4090"]["pricing_options"]}
    assert set(options_4090) == {"单卡机柜"}
    assert options_4090["单卡机柜"]["min_card_count"] == 1
    assert options_4090["单卡机柜"]["capacity_cards"] == 1
    assert options_4090["单卡机柜"]["max_card_count"] >= 1

    option_v100 = by_type["V100X2"]["pricing_options"][0]
    assert option_v100["cabinet_type"] == "单卡机柜"
    assert option_v100["min_card_count"] == 1
    assert option_v100["max_card_count"] == 1
    assert option_v100["capacity_cards"] == 1
