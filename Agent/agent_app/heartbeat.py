from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from urllib import request as urllib_request

from .config import (
    resolve_backend_base_url,
    resolve_backend_token,
    resolve_heartbeat_interval_seconds,
    resolve_node_id,
    resolve_public_host,
)


def start_heartbeat_loop(runtime) -> None:
    backend_base_url = resolve_backend_base_url()
    if not backend_base_url:
        return
    thread = threading.Thread(target=_heartbeat_loop, args=(runtime,), daemon=True)
    thread.start()


def _heartbeat_loop(runtime) -> None:
    interval = resolve_heartbeat_interval_seconds()
    while True:
        try:
            send_heartbeat(runtime)
        except Exception:
            pass
        time.sleep(interval)


def send_heartbeat(runtime) -> None:
    backend_base_url = resolve_backend_base_url()
    if not backend_base_url:
        return
    status = runtime.collect_node_status()
    payload = {
        "node_id": resolve_node_id(),
        "host_ip": resolve_public_host(),
        "accelerator_type": status.get("accelerator_type", "unknown"),
        "reported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "devices": status.get("devices", []),
        "containers": status.get("containers", []),
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib_request.Request(
        f"{backend_base_url}/api/nodes/heartbeat",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {resolve_backend_token()}",
            "Content-Type": "application/json",
        },
    )
    with urllib_request.urlopen(req, timeout=10) as response:
        response.read()
