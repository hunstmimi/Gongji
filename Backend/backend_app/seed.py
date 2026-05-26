from __future__ import annotations

from dataclasses import dataclass


LOCATION_LAYOUTS = {
    "位置1": {"x_ratio": 0.18, "y_ratio": 0.22},
    "位置2": {"x_ratio": 0.42, "y_ratio": 0.16},
    "位置3": {"x_ratio": 0.68, "y_ratio": 0.58},
    "位置4": {"x_ratio": 0.84, "y_ratio": 0.34},
}

LOCATION_EDGES = [
    {"from": "位置1", "to": "位置2"},
    {"from": "位置2", "to": "位置3"},
    {"from": "位置1", "to": "位置3"},
    {"from": "位置3", "to": "位置4"},
]

CARD_TYPE_ORDER = {
    "3090": 1,
    "4090": 2,
    "910B3": 3,
    "V100X2": 4,
}

CARD_PRODUCTS = [
    {
        "card_type": "3090",
        "title": "3090",
        "cabinet_desc": "单卡机柜",
        "vram": "24G",
        "cpu": "16核",
        "memory": "64G",
        "display_price": "单卡 4.5元/小时起",
    },
    {
        "card_type": "4090",
        "title": "4090",
        "cabinet_desc": "单卡机柜",
        "vram": "24G",
        "cpu": "16核",
        "memory": "64G",
        "display_price": "单卡 12.0元/小时起",
    },
    {
        "card_type": "910B3",
        "title": "Ascend 910B3",
        "cabinet_desc": "8卡机柜",
        "vram": "64G HBM",
        "cpu": "鲲鹏多核",
        "memory": "按实例分配",
        "display_price": "单卡 8.0元/小时起",
    },
]

USER_PRICE_CONFIGS = [
    {"card_type": "3090", "cabinet_type": "单卡机柜", "hourly_user_price": 4.5, "enabled": 1},
    {"card_type": "4090", "cabinet_type": "单卡机柜", "hourly_user_price": 12.0, "enabled": 1},
    {"card_type": "910B3", "cabinet_type": "8卡机柜", "hourly_user_price": 8.0, "enabled": 1},
]

DEFAULT_USERS = [
    {
        "username": "gpu_user_001",
        "password_hash": "seeded-user-001:b605a16b1b2db6b1d53ddd872561dded825ffde7d5de9532146d5cbf2b638bd8",
        "phone": "15800000746",
        "nickname": "GPU User",
        "avatar_url": None,
        "balance": 286.40,
        "status": "active",
        "role": "user",
    },
    {
        "username": "admin",
        "password_hash": "seeded-admin-001:9abd69b199a66395013704f1243b59611fc93feeb510692a05cdfc20c226e9f3",
        "phone": "18700004352",
        "nickname": "管理员",
        "avatar_url": None,
        "balance": 0,
        "status": "active",
        "role": "admin",
    }
]

DEFAULT_HISTORY_RENTALS = [
    {
        "card_type": "4090",
        "cabinet_type": "单卡机柜",
        "cabinet_count": 1,
        "card_count": 1,
        "started_at": "2026-04-20T10:00:00+08:00",
        "ended_at": "2026-04-20T12:00:00+08:00",
        "duration_seconds": 7200,
        "hourly_user_price_total": 12.0,
        "hourly_power_cost_total": 2.8,
        "user_total_amount": 24.0,
        "power_cost_total": 5.6,
        "status": "cancelled",
        "ip": "10.20.12.247",
        "password": "managed-by-platform",
    },
    {
        "card_type": "3090",
        "cabinet_type": "单卡机柜",
        "cabinet_count": 1,
        "card_count": 1,
        "started_at": "2026-04-18T09:00:00+08:00",
        "ended_at": "2026-04-18T15:00:00+08:00",
        "duration_seconds": 21600,
        "hourly_user_price_total": 4.5,
        "hourly_power_cost_total": 1.2,
        "user_total_amount": 27.0,
        "power_cost_total": 7.2,
        "status": "cancelled",
        "ip": "10.20.12.224",
        "password": "managed-by-platform",
    },
]


@dataclass(frozen=True)
class CabinetSeed:
    cabinet_code: str
    location: str
    card_type: str
    cabinet_type: str
    capacity_cards: int
    day_hourly_power_cost: float
    night_hourly_power_cost: float
    status: str
    host_ip: str
    ssh_port: int = 22
    allowed_device_indices: tuple[int, ...] | None = None


CABINET_SEEDS = [
    CabinetSeed("10.20.12.224-3090", "位置1", "3090", "单卡机柜", 1, 1.8, 1.6, "available", "10.20.12.224"),
    CabinetSeed("10.20.12.225-3090", "位置1", "3090", "单卡机柜", 1, 1.5, 1.3, "available", "10.20.12.225"),
    CabinetSeed("10.20.12.226-3090", "位置2", "3090", "单卡机柜", 1, 1.9, 1.7, "available", "10.20.12.226"),
    CabinetSeed("10.20.12.227-3090", "位置1", "3090", "单卡机柜", 1, 1.6, 1.4, "available", "10.20.12.227"),
    CabinetSeed("10.21.53.82-4090", "位置3", "4090", "单卡机柜", 1, 2.4, 2.0, "available", "10.21.53.82"),
    CabinetSeed("10.21.53.113-4090", "位置2", "4090", "单卡机柜", 1, 2.5, 2.1, "available", "10.21.53.113"),
    CabinetSeed("10.21.53.162-4090", "位置3", "4090", "单卡机柜", 1, 2.2, 1.8, "available", "10.21.53.162"),
    CabinetSeed(
        "10.26.6.48-910B3",
        "位置4",
        "910B3",
        "8卡机柜",
        8,
        16.0,
        12.8,
        "offline",
        "10.26.6.48",
        allowed_device_indices=(0, 1, 2, 3),
    ),
]

PRICE_RULES = {
    ("3090", "单卡机柜"): {
        "single_total": 4.5,
        "bulk_per_card": 4.2,
        "min_card_count": 1,
        "preview_max": 4,
        "allocation_policy": "spread",
    },
    ("4090", "单卡机柜"): {
        "single_total": 12.0,
        "bulk_per_card": 11.4,
        "min_card_count": 1,
        "preview_max": 8,
        "allocation_policy": "spread",
    },
    ("910B3", "8卡机柜"): {
        "single_total": 8.0,
        "bulk_per_card": 7.6,
        "min_card_count": 1,
        "preview_max": 4,
        "allocation_policy": "same_cabinet_required",
    },
}


CABINET_DEVICE_POLICY = {
    item.cabinet_code: item.allowed_device_indices
    for item in CABINET_SEEDS
    if item.allowed_device_indices is not None
}


class PriceRuleNotFoundError(ValueError):
    pass


class CardCountRuleError(ValueError):
    pass


def get_price_rule(card_type: str, cabinet_type: str) -> dict:
    rule = PRICE_RULES.get((card_type, cabinet_type))
    if not rule:
        raise PriceRuleNotFoundError(f"price tier not configured for {card_type} {cabinet_type}")
    return rule


def get_min_card_count(card_type: str, cabinet_type: str) -> int:
    return int(get_price_rule(card_type, cabinet_type).get("min_card_count", 1))


def get_preview_max(card_type: str, cabinet_type: str) -> int:
    return int(get_price_rule(card_type, cabinet_type)["preview_max"])


def get_allocation_policy(card_type: str, cabinet_type: str) -> str:
    return str(get_price_rule(card_type, cabinet_type).get("allocation_policy", "spread"))


def get_allowed_device_indices(cabinet_code: str, capacity_cards: int) -> set[int]:
    configured = CABINET_DEVICE_POLICY.get(cabinet_code)
    if configured is None:
        return set(range(capacity_cards))
    return {index for index in configured if 0 <= index < capacity_cards}


def get_hourly_user_price_total(card_type: str, cabinet_type: str, card_count: int) -> float:
    rule = get_price_rule(card_type, cabinet_type)
    min_card_count = int(rule.get("min_card_count", 1))
    preview_max = int(rule["preview_max"])
    if card_count < min_card_count:
        raise CardCountRuleError(f"{card_type} {cabinet_type} 最少 {min_card_count} 卡起租")
    if card_count > preview_max:
        raise CardCountRuleError(f"{card_type} {cabinet_type} 最多 {preview_max} 卡")
    if card_count == 1:
        return float(rule["single_total"])
    return round(float(rule["bulk_per_card"]) * card_count, 2)


def get_pricing_preview(card_type: str, cabinet_type: str) -> list[dict]:
    preview_min = get_min_card_count(card_type, cabinet_type)
    preview_max = get_preview_max(card_type, cabinet_type)
    return [
        {
            "card_count": count,
            "hourly_user_price_total": get_hourly_user_price_total(card_type, cabinet_type, count),
            "avg_per_card": round(get_hourly_user_price_total(card_type, cabinet_type, count) / count, 2),
        }
        for count in range(preview_min, preview_max + 1)
    ]


def derive_active_card_count(capacity_cards: int, seeded_status: str) -> int:
    if seeded_status == "offline":
        return 0
    if seeded_status == "rented":
        return capacity_cards
    if capacity_cards == 1:
        return 0
    return max(1, capacity_cards // 2)


def derive_cabinet_status(active_card_count: int, capacity_cards: int) -> str:
    if active_card_count <= 0:
        return "offline"
    if active_card_count >= capacity_cards:
        return "rented"
    return "available"


def build_cabinets() -> list[dict]:
    cabinets: list[dict] = []
    for item in CABINET_SEEDS:
        active_card_count = derive_active_card_count(item.capacity_cards, item.status)
        cabinets.append(
            {
                "cabinet_code": item.cabinet_code,
                "location": item.location,
                "card_type": item.card_type,
                "cabinet_type": item.cabinet_type,
                "capacity_cards": item.capacity_cards,
                "day_hourly_power_cost": item.day_hourly_power_cost,
                "night_hourly_power_cost": item.night_hourly_power_cost,
                "active_card_count": active_card_count,
                "status": derive_cabinet_status(active_card_count, item.capacity_cards),
                "host_ip": item.host_ip,
                "ssh_port": item.ssh_port,
            }
        )
    return cabinets
