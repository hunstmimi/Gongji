from __future__ import annotations

import os
import shlex
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
ENV_FILE_PATH = PROJECT_DIR / ".env"


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


def resolve_host() -> str:
    return os.getenv("AGENT_HOST") or "0.0.0.0"


def resolve_port() -> int:
    return int(os.getenv("AGENT_PORT") or "18080")


def resolve_token() -> str:
    return os.getenv("AGENT_TOKEN") or "local-agent-token"


def resolve_node_id() -> str:
    return os.getenv("AGENT_NODE_ID") or resolve_public_host()


def resolve_backend_base_url() -> str | None:
    value = (os.getenv("AGENT_BACKEND_BASE_URL") or "").strip().rstrip("/")
    return value or None


def resolve_backend_token() -> str:
    return os.getenv("AGENT_BACKEND_TOKEN") or resolve_token()


def resolve_heartbeat_interval_seconds() -> int:
    raw = (os.getenv("AGENT_HEARTBEAT_INTERVAL_SECONDS") or "").strip()
    if not raw:
        return 15
    try:
        return max(5, int(raw))
    except ValueError:
        return 15


def resolve_dry_run() -> bool:
    value = (os.getenv("AGENT_DRY_RUN") or "true").strip().lower()
    return value not in {"0", "false", "no", "off"}


def resolve_public_host() -> str:
    return os.getenv("AGENT_PUBLIC_HOST") or "127.0.0.1"


def resolve_ssh_port_min() -> int:
    return int(os.getenv("AGENT_SSH_PORT_MIN") or "22000")


def resolve_ssh_port_max() -> int:
    return int(os.getenv("AGENT_SSH_PORT_MAX") or "22999")


def resolve_allowed_device_indices() -> set[int] | None:
    raw = (os.getenv("AGENT_ALLOWED_DEVICE_INDICES") or "").strip()
    if not raw:
        return None
    return {int(item.strip()) for item in raw.split(",") if item.strip()}


def resolve_accelerator_type() -> str:
    return (os.getenv("AGENT_ACCELERATOR_TYPE") or "ascend").strip().lower()


def resolve_docker_command() -> list[str]:
    return shlex.split(os.getenv("AGENT_DOCKER_COMMAND") or "docker")


def resolve_ascend_common_devices() -> list[str]:
    raw = os.getenv("AGENT_ASCEND_COMMON_DEVICES") or "/dev/davinci_manager,/dev/hisi_hdc,/dev/devmm_svm"
    return [item.strip() for item in raw.split(",") if item.strip()]


def resolve_ascend_mounts() -> list[tuple[str, str, str]]:
    raw = os.getenv("AGENT_ASCEND_MOUNTS") or ""
    mounts: list[tuple[str, str, str]] = []
    for item in [part.strip() for part in raw.split(",") if part.strip()]:
        pieces = item.split(":")
        if len(pieces) == 2:
            mounts.append((pieces[0], pieces[1], "rw"))
        elif len(pieces) >= 3:
            mounts.append((pieces[0], pieces[1], pieces[2]))
    return mounts
