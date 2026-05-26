from __future__ import annotations

import io
import posixpath
import shlex
import tarfile
import uuid
from dataclasses import dataclass
from pathlib import Path

import paramiko

from ..config import resolve_agent_token, resolve_backend_public_base_url
from ..errors import AppError
from ..schemas import AdminCreateMachineRequest, AdminMachineAccessRequest
from .admin_machine_service import create_machine, list_machines


AGENT_PORT = 18080
AGENT_INSTALL_DIR = "/opt/gongji-agent"


@dataclass
class CommandResult:
    ok: bool
    stdout: str
    stderr: str
    code: int


class RemoteSession:
    def __init__(self, payload: AdminMachineAccessRequest) -> None:
        self.payload = payload
        self.sudo_password = payload.sudo_password or payload.ssh_password
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    def __enter__(self) -> "RemoteSession":
        self.client.connect(
            hostname=self.payload.host_ip.strip(),
            port=int(self.payload.ssh_port),
            username=self.payload.ssh_username.strip(),
            password=self.payload.ssh_password,
            timeout=12,
            banner_timeout=12,
            auth_timeout=12,
        )
        return self

    def __exit__(self, *_args) -> None:
        self.client.close()

    def run(self, command: str, *, sudo: bool = False, timeout: int = 40) -> CommandResult:
        actual = command
        if sudo:
            actual = (
                f"printf '%s\\n' {shlex.quote(self.sudo_password)} "
                f"| sudo -S -p '' bash -lc {shlex.quote(command)}"
            )
        stdin, stdout, stderr = self.client.exec_command(actual, timeout=timeout)
        out = stdout.read().decode("utf-8", "replace").strip()
        err = stderr.read().decode("utf-8", "replace").strip()
        code = stdout.channel.recv_exit_status()
        return CommandResult(ok=code == 0, stdout=out, stderr=err, code=code)

    def put_bytes(self, remote_path: str, content: bytes) -> None:
        with self.client.open_sftp() as sftp:
            with sftp.file(remote_path, "wb") as handle:
                handle.write(content)


def _accelerator_type(card_type: str) -> str:
    normalized = card_type.lower()
    if "910" in normalized or "ascend" in normalized:
        return "ascend"
    if normalized in {"3090", "4090"} or "nvidia" in normalized:
        return "nvidia"
    return "unknown"


def _check(key: str, label: str, result: CommandResult, remediation: str, *, required: bool = True) -> dict:
    return {
        "key": key,
        "label": label,
        "status": "pass" if result.ok else ("fail" if required else "warn"),
        "required": required,
        "details": result.stdout or result.stderr,
        "remediation": "" if result.ok else remediation,
    }


def _manual_check(key: str, label: str, ok: bool, details: str, remediation: str, *, required: bool = True) -> dict:
    return {
        "key": key,
        "label": label,
        "status": "pass" if ok else ("fail" if required else "warn"),
        "required": required,
        "details": details,
        "remediation": "" if ok else remediation,
    }


def _probe_with_session(session: RemoteSession, payload: AdminMachineAccessRequest) -> list[dict]:
    accelerator = _accelerator_type(payload.card_type)
    checks = [
        _manual_check("ssh", "SSH 登录", True, f"{payload.ssh_username}@{payload.host_ip}:{payload.ssh_port}", ""),
        _check("sudo", "sudo 权限", session.run("true", sudo=True), "给该账号配置 sudo 权限，或填写正确 sudo 密码。"),
        _check("python3", "Python 3", session.run("command -v python3 && python3 --version"), "安装 python3。Ubuntu 可执行：sudo apt install -y python3"),
        _check("python_venv", "Python venv", session.run("python3 -m venv --help >/dev/null 2>&1"), "安装 venv。Ubuntu 可执行：sudo apt install -y python3-venv python3-pip"),
        _check("systemd", "systemd 服务管理", session.run("command -v systemctl"), "当前机器缺少 systemctl，需改用手动守护进程部署。"),
        _check("docker", "Docker 可用", session.run("docker info >/dev/null 2>&1", sudo=True), "安装 Docker，并确认 sudo docker info 可以正常执行。"),
    ]

    if accelerator == "nvidia":
        checks.append(
            _check("nvidia_smi", "NVIDIA 驱动", session.run("command -v nvidia-smi && nvidia-smi -L"), "安装 NVIDIA 驱动，并确认 nvidia-smi 可用。")
        )
        checks.append(
            _check(
                "nvidia_container_toolkit",
                "NVIDIA 容器运行时",
                session.run("command -v nvidia-container-cli || command -v nvidia-container-runtime || docker info 2>/dev/null | grep -i nvidia", sudo=True),
                "安装 NVIDIA Container Toolkit，并重启 Docker。",
            )
        )
    elif accelerator == "ascend":
        checks.append(
            _check("npu_smi", "昇腾 npu-smi", session.run("command -v npu-smi && npu-smi info | head -n 25"), "安装或修复昇腾驱动/CANN，使 npu-smi info 可用。")
        )
        checks.append(
            _check(
                "ascend_devices",
                "昇腾设备节点",
                session.run("test -e /dev/davinci_manager && test -e /dev/hisi_hdc && ls /dev/davinci0 >/dev/null 2>&1"),
                "确认 /dev/davinci*、/dev/davinci_manager、/dev/hisi_hdc 存在。",
            )
        )
    else:
        checks.append(
            _manual_check("accelerator_type", "加速卡类型", False, payload.card_type, "当前只支持 3090、4090、910B3。")
        )

    health = session.run(f"curl -fsS http://127.0.0.1:{AGENT_PORT}/api/health", timeout=8)
    if health.ok:
        checks.append(_manual_check("agent_port", "Agent 端口", True, "已检测到现有 Agent", ""))
    else:
        port = session.run(f"ss -ltn 2>/dev/null | grep ':{AGENT_PORT} '", timeout=8)
        checks.append(
            _manual_check(
                "agent_port",
                "Agent 端口",
                not port.ok,
                "端口空闲" if not port.ok else port.stdout,
                f"释放 {AGENT_PORT} 端口，或调整平台 Agent 端口配置。",
            )
        )
    return checks


def _can_deploy(checks: list[dict]) -> bool:
    return all(item["status"] == "pass" for item in checks if item.get("required", True))


def probe_machine(payload: AdminMachineAccessRequest) -> dict:
    try:
        with RemoteSession(payload) as session:
            checks = _probe_with_session(session, payload)
    except Exception as exc:
        checks = [
            _manual_check(
                "ssh",
                "SSH 登录",
                False,
                str(exc),
                "确认 IP、端口、用户名、密码和内网连通性。",
            )
        ]
    return {
        "success": True,
        "can_deploy": _can_deploy(checks),
        "checks": checks,
    }


def _agent_archive() -> bytes:
    repo_root = Path(__file__).resolve().parents[3]
    agent_dir = repo_root / "Agent"
    if not agent_dir.exists():
        raise AppError("AGENT_PACKAGE_MISSING", "后端服务器上没有找到 Agent 目录", 500)
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        tar.add(agent_dir, arcname="agent")
    return buffer.getvalue()


def _env_content(payload: AdminMachineAccessRequest) -> str:
    allowed = ",".join(str(index) for index in range(int(payload.capacity_cards)))
    return "\n".join(
        [
            f"AGENT_TOKEN={resolve_agent_token()}",
            "AGENT_DRY_RUN=false",
            f"AGENT_PUBLIC_HOST={payload.host_ip.strip()}",
            f"AGENT_NODE_ID={payload.cabinet_code.strip()}",
            f"AGENT_ACCELERATOR_TYPE={_accelerator_type(payload.card_type)}",
            f"AGENT_ALLOWED_DEVICE_INDICES={allowed}",
            f"AGENT_BACKEND_BASE_URL={resolve_backend_public_base_url()}",
            f"AGENT_BACKEND_TOKEN={resolve_agent_token()}",
            "AGENT_HEARTBEAT_INTERVAL_SECONDS=15",
            "AGENT_DOCKER_COMMAND=docker",
            "",
        ]
    )


def _service_content() -> str:
    return f"""[Unit]
Description=GongJi Node Agent
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory={AGENT_INSTALL_DIR}
EnvironmentFile={AGENT_INSTALL_DIR}/.env
ExecStart={AGENT_INSTALL_DIR}/.venv/bin/python run.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
"""


def _write_remote_file_command(path: str, content: str) -> str:
    quoted_path = shlex.quote(path)
    quoted_content = shlex.quote(content)
    return f"cat > {quoted_path} <<'EOF'\n{content}\nEOF\nchmod 600 {quoted_path}"


def _install_agent(session: RemoteSession, payload: AdminMachineAccessRequest) -> list[dict]:
    archive_path = f"/tmp/gongji-agent-{uuid.uuid4().hex}.tar.gz"
    session.put_bytes(archive_path, _agent_archive())
    commands = [
        ("prepare_dir", "准备安装目录", f"rm -rf {AGENT_INSTALL_DIR} && mkdir -p {AGENT_INSTALL_DIR}"),
        ("extract_agent", "解压 Agent", f"tar -xzf {shlex.quote(archive_path)} -C {AGENT_INSTALL_DIR} --strip-components=1 && rm -f {shlex.quote(archive_path)}"),
        ("create_venv", "创建 Python 虚拟环境", f"python3 -m venv {AGENT_INSTALL_DIR}/.venv"),
        ("install_deps", "安装 Agent 依赖", f"{AGENT_INSTALL_DIR}/.venv/bin/pip install -r {AGENT_INSTALL_DIR}/requirements.txt"),
        ("write_env", "写入 Agent 环境", _write_remote_file_command(f"{AGENT_INSTALL_DIR}/.env", _env_content(payload))),
        ("write_service", "写入 systemd 服务", _write_remote_file_command("/etc/systemd/system/gongji-agent.service", _service_content())),
        ("start_service", "启动 Agent 服务", "systemctl daemon-reload && systemctl enable gongji-agent && systemctl restart gongji-agent"),
        ("health", "检查 Agent 健康", f"sleep 3 && curl -fsS http://127.0.0.1:{AGENT_PORT}/api/health"),
    ]
    steps = []
    for key, label, command in commands:
        result = session.run(command, sudo=True, timeout=180)
        steps.append(
            {
                "key": key,
                "label": label,
                "status": "pass" if result.ok else "fail",
                "details": result.stdout or result.stderr,
            }
        )
        if not result.ok:
            break
    return steps


def _ensure_machine(payload: AdminMachineAccessRequest) -> dict:
    existing = next(
        (item for item in list_machines()["machines"] if item["cabinet_code"] == payload.cabinet_code.strip()),
        None,
    )
    if existing:
        return existing
    created = create_machine(
        AdminCreateMachineRequest(
            cabinet_code=payload.cabinet_code,
            location=payload.location,
            host_ip=payload.host_ip,
            ssh_port=payload.ssh_port,
            card_type=payload.card_type,
            cabinet_type=payload.cabinet_type,
            capacity_cards=payload.capacity_cards,
            day_hourly_power_cost=payload.day_hourly_power_cost,
            night_hourly_power_cost=payload.night_hourly_power_cost,
        )
    )
    return created["machine"]


def deploy_agent(payload: AdminMachineAccessRequest) -> dict:
    try:
        with RemoteSession(payload) as session:
            checks = _probe_with_session(session, payload)
            if not _can_deploy(checks):
                return {
                    "success": True,
                    "deployed": False,
                    "can_deploy": False,
                    "message": "检测未通过，未执行部署",
                    "checks": checks,
                    "steps": [],
                }
            machine = _ensure_machine(payload)
            steps = _install_agent(session, payload)
    except Exception as exc:
        raise AppError("AGENT_DEPLOY_FAILED", f"Agent 部署失败：{exc}", 500) from exc

    deployed = all(item["status"] == "pass" for item in steps)
    return {
        "success": True,
        "deployed": deployed,
        "can_deploy": True,
        "message": "Agent 部署完成，等待心跳刷新可租状态" if deployed else "Agent 部署过程中断",
        "machine": machine,
        "checks": checks,
        "steps": steps,
    }
