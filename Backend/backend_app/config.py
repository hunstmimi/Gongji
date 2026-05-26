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


def resolve_agent_base_url() -> str | None:
    value = (os.getenv("COMPUTE_RENTAL_AGENT_BASE_URL") or "").strip().rstrip("/")
    return value or None


def resolve_agent_port() -> int:
    raw = (os.getenv("COMPUTE_RENTAL_AGENT_PORT") or "").strip()
    if not raw:
        return 18080
    try:
        return min(max(int(raw), 1), 65535)
    except ValueError:
        return 18080


def resolve_agent_token() -> str:
    return os.getenv("COMPUTE_RENTAL_AGENT_TOKEN") or "local-agent-token"


def resolve_backend_public_base_url() -> str:
    value = (os.getenv("COMPUTE_RENTAL_BACKEND_PUBLIC_BASE_URL") or "").strip().rstrip("/")
    return value or "http://10.26.6.117:8000"


def resolve_agent_dry_run() -> bool:
    value = (os.getenv("COMPUTE_RENTAL_AGENT_DRY_RUN") or "true").strip().lower()
    return value not in {"0", "false", "no", "off"}


def resolve_agent_default_image() -> str:
    return os.getenv("COMPUTE_RENTAL_AGENT_DEFAULT_IMAGE") or "gongji/ascend-ssh:latest"


def resolve_agent_nvidia_image() -> str:
    return os.getenv("COMPUTE_RENTAL_AGENT_NVIDIA_IMAGE") or "gongji/nvidia-ssh:latest"


def resolve_agent_ascend_image() -> str:
    return os.getenv("COMPUTE_RENTAL_AGENT_ASCEND_IMAGE") or resolve_agent_default_image()


def resolve_cpu_per_card() -> float:
    raw = (os.getenv("COMPUTE_RENTAL_CPU_PER_CARD") or "").strip()
    if not raw:
        return 8.0
    try:
        return max(0.1, float(raw))
    except ValueError:
        return 8.0


def resolve_memory_per_card_gb() -> int:
    raw = (os.getenv("COMPUTE_RENTAL_MEMORY_PER_CARD_GB") or "").strip()
    if not raw:
        return 64
    try:
        return max(1, int(raw))
    except ValueError:
        return 64


def resolve_shm_per_card_gb() -> int:
    raw = (os.getenv("COMPUTE_RENTAL_SHM_PER_CARD_GB") or "").strip()
    if not raw:
        return 16
    try:
        return max(1, int(raw))
    except ValueError:
        return 16
