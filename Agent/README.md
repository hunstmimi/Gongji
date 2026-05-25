# GongJi Node Agent

Node Agent runs on the accelerator host and provisions rental instances for the platform backend.

For the current MVP it supports dry-run mode by default. Dry-run returns real-shaped SSH
connection payloads without requiring Docker or a GPU machine.

## Run Locally

```bash
pip install -r requirements.txt
python run.py
```

Or:

```bash
uvicorn app:app --host 0.0.0.0 --port 18080
```

## Environment

Copy `.env.example` to `.env`.

- `AGENT_TOKEN`: shared bearer token used by the backend
- `AGENT_DRY_RUN`: `true` for local/mock mode, `false` for Docker mode
- `AGENT_PUBLIC_HOST`: host/IP returned to users in SSH commands
- `AGENT_NODE_ID`: stable node id reported to the backend heartbeat endpoint
- `AGENT_SSH_PORT_MIN`, `AGENT_SSH_PORT_MAX`: allowed SSH port range
- `AGENT_ACCELERATOR_TYPE`: `ascend`, `nvidia`, or `none`
- `AGENT_DOCKER_COMMAND`: Docker command. Use `docker` when the agent user can access Docker. In production, run the agent with Docker socket permission or under systemd with the required privileges; do not rely on interactive sudo.
- `AGENT_ASCEND_COMMON_DEVICES`: shared Ascend device files mounted into every container
- `AGENT_ASCEND_MOUNTS`: host paths mounted into every Ascend container
- `AGENT_BACKEND_BASE_URL`: backend base URL for periodic node heartbeats, e.g. `http://10.x.x.x:8000`
- `AGENT_BACKEND_TOKEN`: bearer token used when reporting heartbeats to the backend
- `AGENT_HEARTBEAT_INTERVAL_SECONDS`: node status report interval, default `15`

## API

- `GET /api/health`
- `POST /api/instances`
- `GET /api/instances/{instance_id}`
- `POST /api/instances/{instance_id}/stop`
- `GET /api/gpus`

All instance APIs require:

```text
Authorization: Bearer <AGENT_TOKEN>
```

## Docker Mode

When `AGENT_DRY_RUN=false`, the agent calls Docker CLI.

Ascend 910B3 mode mounts only the rented NPU devices into the user's container:

```bash
docker run -d --name rental-123 \
  --device /dev/davinci0:/dev/davinci0 \
  --device /dev/davinci1:/dev/davinci1 \
  --device /dev/davinci_manager \
  --device /dev/hisi_hdc \
  -e ASCEND_VISIBLE_DEVICES=0,1 \
  -p 22123:22 ...
```

NVIDIA mode uses Docker's GPU flag:

```bash
docker run -d --name rental-123 --gpus device=0,1 -p 22123:22 ...
```

The image should already contain the matching Ascend/CANN user-space libraries. Avoid
blindly bind-mounting `/usr/local/Ascend` from the host over a working image unless you
have verified the versions match; doing so can hide libraries already present in the image.

## Ascend SSH Image

Build the default SSH image on the Ascend host:

```bash
cd Agent/images/ascend-ssh
docker build -t gongji/ascend-ssh:latest .
```

The image starts `sshd`, creates/configures `SSH_USERNAME` and `SSH_PASSWORD`, and writes
the runtime Ascend/Python environment into `/etc/profile.d/gongji-runtime-env.sh` so SSH
sessions can load the same accelerator environment.

## Heartbeat

When `AGENT_BACKEND_BASE_URL` is set, the agent periodically posts node state to:

```text
POST <backend>/api/nodes/heartbeat
Authorization: Bearer <AGENT_BACKEND_TOKEN>
```

The heartbeat includes parsed accelerator state from `npu-smi info`/`nvidia-smi` and
GongJi container records discovered from Docker labels. The backend stores the latest
node/device snapshot and marks `occupied_unknown` or `unhealthy` devices as unrentable.
