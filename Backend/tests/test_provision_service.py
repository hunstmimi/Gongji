from __future__ import annotations

from backend_app.services import provision_service


def test_create_instance_routes_to_agent_derived_from_host_ip(monkeypatch):
    calls = []

    def fake_request_agent(base_url: str, method: str, path: str, payload: dict) -> dict:
        calls.append((base_url, method, path, payload))
        return {
            "success": True,
            "instance_id": payload["instance_id"],
            "container_name": payload["container_name"],
            "host": "10.26.6.48",
            "ssh_port": payload["ssh_port"],
            "username": payload["username"],
            "password": payload["password"],
            "command": f"ssh {payload['username']}@10.26.6.48 -p {payload['ssh_port']}",
            "gpu_indices": payload["gpu_indices"],
            "status": "running",
            "provisioning_status": "ready",
        }

    monkeypatch.delenv("COMPUTE_RENTAL_AGENT_BASE_URL", raising=False)
    monkeypatch.setenv("COMPUTE_RENTAL_AGENT_PORT", "18080")
    monkeypatch.setenv("COMPUTE_RENTAL_AGENT_DRY_RUN", "false")
    monkeypatch.setattr(provision_service, "_request_agent", fake_request_agent)

    result = provision_service.create_instance(
        12,
        {
            "cabinet_code": "10.26.6.48-910B3",
            "host_ip": "10.26.6.48",
            "device_indices": [0, 1],
            "allocated_cards": 2,
        },
    )

    assert calls[0][0] == "http://10.26.6.48:18080"
    assert calls[0][1:3] == ("POST", "/api/instances")
    assert calls[0][3]["gpu_indices"] == [0, 1]
    assert result["agent_base_url"] == "http://10.26.6.48:18080"


def test_stop_instance_routes_to_agent_derived_from_host_ip(monkeypatch):
    calls = []

    def fake_request_agent(base_url: str, method: str, path: str, payload: dict) -> dict:
        calls.append((base_url, method, path, payload))
        return {"success": True}

    monkeypatch.delenv("COMPUTE_RENTAL_AGENT_BASE_URL", raising=False)
    monkeypatch.setenv("COMPUTE_RENTAL_AGENT_PORT", "18081")
    monkeypatch.setenv("COMPUTE_RENTAL_AGENT_DRY_RUN", "false")
    monkeypatch.setattr(provision_service, "_request_agent", fake_request_agent)

    provision_service.stop_instance("rental-12-1", host_ip="10.21.53.62")

    assert calls == [
        ("http://10.21.53.62:18081", "POST", "/api/instances/rental-12-1/stop", {})
    ]
