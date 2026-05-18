from __future__ import annotations

import os
from pathlib import Path
from zoneinfo import ZoneInfo


PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parent
DEFAULT_DB_PATH = PROJECT_DIR / "compute_rental.db"
ENV_FILE_PATH = PROJECT_DIR / ".env"

API_PREFIX = "/api"
APP_TITLE = "Compute Rental Backend"
APP_VERSION = "1.0.0"

TIMEZONE = ZoneInfo("Asia/Shanghai")


def _load_env_file() -> None:
    if not ENV_FILE_PATH.exists():
        return
    for raw_line in ENV_FILE_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_env_file()


def resolve_app_env() -> str:
    return (os.getenv("APP_ENV") or "local").strip().lower()


def resolve_database_url() -> str | None:
    return os.getenv("DATABASE_URL") or None


def resolve_db_path() -> Path:
    raw = os.getenv("COMPUTE_RENTAL_DB_PATH")
    return Path(raw) if raw else DEFAULT_DB_PATH


def resolve_cors_origins() -> list[str]:
    raw = os.getenv("CORS_ALLOWED_ORIGINS", "")
    defaults = []
    if resolve_app_env() != "production":
        defaults = [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    extras = [item.strip() for item in raw.split(",") if item.strip()]
    return list(dict.fromkeys(defaults + extras))


def resolve_ssh_username() -> str:
    return (os.getenv("COMPUTE_RENTAL_SSH_USERNAME") or "").strip() or "platform-managed"


def resolve_ssh_password() -> str:
    return os.getenv("COMPUTE_RENTAL_SSH_PASSWORD") or "platform-managed"


def resolve_rental_ssh_username_prefix() -> str:
    return (os.getenv("COMPUTE_RENTAL_SSH_USERNAME_PREFIX") or "").strip() or "rent"


def resolve_rental_ssh_port_base() -> int:
    raw = (os.getenv("COMPUTE_RENTAL_SSH_PORT_BASE") or "").strip()
    if not raw:
        return 22000
    try:
        value = int(raw)
    except ValueError:
        return 22000
    return min(max(value, 1024), 60000)


def resolve_rental_ssh_password_seed() -> str:
    return os.getenv("COMPUTE_RENTAL_SSH_PASSWORD_SEED") or "local-demo-rental-secret"
