from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field

from .config import (
    resolve_accelerator_type,
    resolve_allowed_device_indices,
    resolve_ascend_common_devices,
    resolve_ascend_mounts,
    resolve_docker_command,
    resolve_dry_run,
    resolve_public_host,
    resolve_ssh_port_max,
    resolve_ssh_port_min,
)
from .schemas import CreateInstanceRequest, InstanceRecord


class RuntimeErrorResponse(RuntimeError):
    pass


@dataclass
class DryRunRuntime:
    instances: dict[str, InstanceRecord] = field(default_factory=dict)

    def create_instance(self, payload: CreateInstanceRequest) -> InstanceRecord:
        record = build_record(payload, status="running", provisioning_status="ready")
        self.instances[record.instance_id] = record
        return record

    def get_instance(self, instance_id: str) -> InstanceRecord | None:
        return self.instances.get(instance_id)

    def stop_instance(self, instance_id: str) -> InstanceRecord:
        record = self.instances.get(instance_id)
        if not record:
            record = build_record_from_id(instance_id, status="stopped", provisioning_status="missing")
        else:
            record = record.model_copy(update={"status": "stopped", "provisioning_status": "stopped"})
            self.instances[instance_id] = record
        return record

    def list_devices(self) -> dict:
        return {"accelerator_type": resolve_accelerator_type(), "raw": "dry-run"}

    def collect_node_status(self) -> dict:
        return {"accelerator_type": resolve_accelerator_type(), "devices": [], "containers": []}


@dataclass
class DockerRuntime:
    def create_instance(self, payload: CreateInstanceRequest) -> InstanceRecord:
        record = build_record(payload, status="creating", provisioning_status="creating")
        command = [
            *resolve_docker_command(),
            "run",
            "-d",
            "--name",
            record.container_name,
            "--label",
            f"gongji.rental_id={payload.rental_id}",
            "--label",
            f"gongji.instance_id={payload.instance_id}",
            "--label",
            f"gongji.devices={','.join(str(item) for item in payload.gpu_indices)}",
            "-p",
            f"{payload.ssh_port}:22",
            "--shm-size",
            payload.shm_size,
        ]
        command.extend(_accelerator_args(payload))
        if payload.cpu_limit:
            command.extend(["--cpus", str(payload.cpu_limit)])
        if payload.memory_limit_gb:
            command.extend(["--memory", f"{payload.memory_limit_gb}g"])
        command.extend(
            [
                "-e",
                f"SSH_USERNAME={payload.username}",
                "-e",
                f"SSH_PASSWORD={payload.password}",
                payload.image,
            ]
        )
        _run(command)
        return record.model_copy(update={"status": "running", "provisioning_status": "ready"})

    def get_instance(self, instance_id: str) -> InstanceRecord | None:
        result = _run([*resolve_docker_command(), "inspect", instance_id, "--format", "{{.State.Status}}"], check=False)
        if result.returncode != 0:
            return None
        return build_record_from_id(instance_id, status=result.stdout.strip() or "unknown", provisioning_status="ready")

    def stop_instance(self, instance_id: str) -> InstanceRecord:
        _run([*resolve_docker_command(), "rm", "-f", instance_id], check=False)
        return build_record_from_id(instance_id, status="stopped", provisioning_status="stopped")

    def list_devices(self) -> dict:
        accelerator_type = resolve_accelerator_type()
        if accelerator_type == "ascend":
            result = _run(["npu-smi", "info"], check=False)
        elif accelerator_type == "nvidia":
            result = _run(["nvidia-smi"], check=False)
        else:
            result = subprocess.CompletedProcess([], 0, "", "")
        return {
            "accelerator_type": accelerator_type,
            "available": result.returncode == 0,
            "raw": result.stdout,
            "error": result.stderr,
        }

    def collect_node_status(self) -> dict:
        return {
            "accelerator_type": resolve_accelerator_type(),
            "devices": _collect_accelerator_devices(),
            "containers": _collect_gongji_containers(),
        }


def build_record(payload: CreateInstanceRequest, status: str, provisioning_status: str) -> InstanceRecord:
    container_name = payload.container_name or payload.instance_id
    host = resolve_public_host()
    command = f"ssh {payload.username}@{host} -p {payload.ssh_port}"
    return InstanceRecord(
        instance_id=payload.instance_id,
        container_name=container_name,
        host=host,
        ssh_port=payload.ssh_port,
        username=payload.username,
        password=payload.password,
        command=command,
        gpu_indices=payload.gpu_indices,
        image=payload.image,
        status=status,
        provisioning_status=provisioning_status,
    )


def build_record_from_id(instance_id: str, status: str, provisioning_status: str) -> InstanceRecord:
    return InstanceRecord(
        instance_id=instance_id,
        container_name=instance_id,
        host=resolve_public_host(),
        ssh_port=0,
        username="",
        password="",
        command="",
        gpu_indices=[],
        image="",
        status=status,
        provisioning_status=provisioning_status,
    )


def validate_payload(payload: CreateInstanceRequest) -> None:
    if payload.ssh_port < resolve_ssh_port_min() or payload.ssh_port > resolve_ssh_port_max():
        raise RuntimeErrorResponse("ssh_port outside allowed range")
    if any(index < 0 for index in payload.gpu_indices):
        raise RuntimeErrorResponse("gpu index must be non-negative")
    allowed_indices = resolve_allowed_device_indices()
    if allowed_indices is not None:
        requested = set(payload.gpu_indices)
        disallowed = sorted(requested - allowed_indices)
        if disallowed:
            raise RuntimeErrorResponse(f"device indices not allowed: {','.join(str(item) for item in disallowed)}")


def get_runtime():
    return DryRunRuntime() if resolve_dry_run() else DockerRuntime()


def _run(command: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    except FileNotFoundError as exc:
        result = subprocess.CompletedProcess(command, 127, "", str(exc))
    if check and result.returncode != 0:
        raise RuntimeErrorResponse(result.stderr.strip() or "command failed")
    return result


def _accelerator_args(payload: CreateInstanceRequest) -> list[str]:
    accelerator_type = resolve_accelerator_type()
    if accelerator_type == "nvidia":
        return ["--gpus", f"device={','.join(str(item) for item in payload.gpu_indices)}"]
    if accelerator_type == "ascend":
        return _ascend_args(payload)
    if accelerator_type in {"none", "cpu"}:
        return []
    raise RuntimeErrorResponse(f"unsupported accelerator type: {accelerator_type}")


def _ascend_args(payload: CreateInstanceRequest) -> list[str]:
    args: list[str] = []
    for index in payload.gpu_indices:
        args.extend(["--device", f"/dev/davinci{index}:/dev/davinci{index}"])
    for device in resolve_ascend_common_devices():
        args.extend(["--device", device])
    for source, target, mode in resolve_ascend_mounts():
        args.extend(["-v", f"{source}:{target}:{mode}"])
    visible_devices = ",".join(str(item) for item in payload.gpu_indices)
    args.extend(["-e", f"ASCEND_VISIBLE_DEVICES={visible_devices}"])
    args.extend(["-e", f"ASCEND_RT_VISIBLE_DEVICES={visible_devices}"])
    args.extend(["-e", f"NPU_VISIBLE_DEVICES={visible_devices}"])
    return args


def _collect_accelerator_devices() -> list[dict]:
    accelerator_type = resolve_accelerator_type()
    if accelerator_type == "ascend":
        result = _run(["npu-smi", "info"], check=False)
        return _parse_ascend_npu_smi(result.stdout)
    if accelerator_type == "nvidia":
        result = _run(
            [
                "nvidia-smi",
                "--query-gpu=index,name,utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            check=False,
        )
        devices = []
        for line in result.stdout.splitlines():
            pieces = [item.strip() for item in line.split(",")]
            if len(pieces) < 5:
                continue
            devices.append(
                {
                    "index": int(pieces[0]),
                    "name": pieces[1],
                    "health": "OK",
                    "usage_percent": _to_float(pieces[2]),
                    "memory_used_mb": _to_int(pieces[3]),
                    "memory_total_mb": _to_int(pieces[4]),
                    "process_count": 0,
                    "raw": line,
                }
            )
        return devices
    return []


def _parse_ascend_npu_smi(output: str) -> list[dict]:
    devices: dict[int, dict] = {}
    lines = output.splitlines()
    for index, line in enumerate(lines):
        match = re.match(r"^\|\s*(\d+)\s+(\S+)\s+\|\s+(\S+)", line)
        if not match:
            continue
        device_index = int(match.group(1))
        if device_index in devices:
            continue
        chip_line = lines[index + 1] if index + 1 < len(lines) else ""
        pairs = re.findall(r"(\d+)\s*/\s*(\d+)", chip_line)
        hbm_used = hbm_total = None
        if pairs:
            hbm_used, hbm_total = (int(item) for item in pairs[-1])
        aicore_match = re.search(r"\|\s*\S+\s+\|\s+\S+\s+\|\s*(\d+)", chip_line)
        devices[device_index] = {
            "index": device_index,
            "name": match.group(2),
            "health": match.group(3),
            "usage_percent": _to_float(aicore_match.group(1)) if aicore_match else None,
            "hbm_used_mb": hbm_used,
            "hbm_total_mb": hbm_total,
            "process_count": 0,
            "raw": line + "\n" + chip_line,
        }

    in_process_section = False
    for line in lines:
        if "Process id" in line and "Process name" in line:
            in_process_section = True
            continue
        if not in_process_section:
            continue
        process_match = re.match(r"^\|\s*(\d+)\s+\d+\s+\|", line)
        if process_match:
            device_index = int(process_match.group(1))
            if device_index in devices:
                devices[device_index]["process_count"] += 1

    allowed_indices = resolve_allowed_device_indices()
    result = list(devices.values())
    if allowed_indices is not None:
        result = [item for item in result if int(item["index"]) in allowed_indices]
    return sorted(result, key=lambda item: int(item["index"]))


def _collect_gongji_containers() -> list[dict]:
    result = _run(
        [
            *resolve_docker_command(),
            "ps",
            "-a",
            "--filter",
            "label=gongji.instance_id",
            "--format",
            "{{.Names}}\t{{.Status}}\t{{.Ports}}\t{{.Label \"gongji.instance_id\"}}\t{{.Label \"gongji.devices\"}}",
        ],
        check=False,
    )
    containers = []
    for line in result.stdout.splitlines():
        pieces = line.split("\t")
        if len(pieces) < 5:
            continue
        ssh_port = _parse_ssh_port(pieces[2])
        containers.append(
            {
                "container_name": pieces[0],
                "status": pieces[1],
                "ssh_port": ssh_port,
                "instance_id": pieces[3],
                "device_indices": [int(item) for item in pieces[4].split(",") if item],
            }
        )
    return containers


def _parse_ssh_port(ports: str) -> int | None:
    match = re.search(r"0\.0\.0\.0:(\d+)->22/tcp", ports)
    return int(match.group(1)) if match else None


def _to_int(value: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
