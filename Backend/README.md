# Backend

FastAPI backend for the compute rental system.

It supports two database modes:

- local SQLite for development/tests
- PostgreSQL via `DATABASE_URL` for real multi-user deployment

## Run

```bash
pip install -r requirements.txt
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Run from the `Backend` directory.

For a local PostgreSQL instance:

```bash
docker compose -f docker-compose.postgres.yml up -d
cp .env.example .env
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

If Docker Hub cannot pull `postgres:16`, use the local Alpine-based fallback:

```bash
docker compose -f docker-compose.postgres-local.yml up -d --build
```

## Environment Variables

Copy `Backend/.env.example` into a local `.env` file if you want a template.

- `DATABASE_URL`: PostgreSQL connection string. Leave it empty only for local SQLite tests.
- `COMPUTE_RENTAL_DB_PATH`: local SQLite path used when `DATABASE_URL` is empty
- `CORS_ALLOWED_ORIGINS`: comma-separated frontend origins to allow in addition to local Vite URLs
- `COMPUTE_RENTAL_SSH_USERNAME_PREFIX`: prefix for generated rental environment usernames
- `COMPUTE_RENTAL_SSH_PORT_BASE`: base port for generated rental environment SSH endpoints
- `COMPUTE_RENTAL_SSH_PASSWORD_SEED`: local seed used to derive demo rental environment passwords
- `COMPUTE_RENTAL_AGENT_BASE_URL`: optional single Node Agent base URL. Leave it empty for multi-machine routing.
- `COMPUTE_RENTAL_AGENT_PORT`: Node Agent port used when deriving `http://<cabinet.host_ip>:<port>` for each machine, default `18080`.
- `COMPUTE_RENTAL_AGENT_TOKEN`: shared token for backend-to-Agent calls and Agent heartbeat calls
- `COMPUTE_RENTAL_AGENT_DRY_RUN`: `false` for real Docker provisioning
- `COMPUTE_RENTAL_CPU_PER_CARD`: CPU cores assigned per rented card
- `COMPUTE_RENTAL_MEMORY_PER_CARD_GB`: memory assigned per rented card
- `COMPUTE_RENTAL_SHM_PER_CARD_GB`: Docker `--shm-size` assigned per rented card

For concurrent rental traffic, use PostgreSQL. The rental path locks candidate
`gpu_devices` rows with `FOR UPDATE SKIP LOCKED` on PostgreSQL, reserves devices in a
short transaction, then provisions the Docker container outside the lock. If provisioning
fails, the backend marks the rental as stopped and releases the reserved devices.

## Multi-machine Agent Routing

For lab-wide deployment, run one Node Agent on every physical accelerator host. The
backend reads `cabinets.host_ip` from the selected allocation and calls:

```text
http://<cabinet.host_ip>:<COMPUTE_RENTAL_AGENT_PORT>
```

Keep `COMPUTE_RENTAL_AGENT_BASE_URL` empty in this mode. Set it only for a single-node
test where every rental should be forced to one fixed Agent.

## Node Heartbeat

Node Agents report real accelerator/container state to:

```text
POST /api/nodes/heartbeat
Authorization: Bearer <COMPUTE_RENTAL_AGENT_TOKEN>
```

The backend stores latest node and per-device status. Devices reported as
`occupied_unknown` or `unhealthy` are excluded from new allocations even when the
platform database still marks them as available.

## Sync Seed Cabinets

`seed.py` only fills the database when the `cabinets` table is empty. If seed cabinet
data changes after deployment, run the sync script once against the target database.

Preview the changes:

```bash
python scripts/sync_cabinets_from_seed.py
```

Apply the changes:

```bash
python scripts/sync_cabinets_from_seed.py --apply
```

Existing cabinet statuses are preserved by default. Add `--sync-status` only if you
intentionally want existing cabinet statuses to match `seed.py`.

## SQLite to PostgreSQL Migration

If you already have data in the local SQLite file and want to move it into PostgreSQL:

```bash
set DATABASE_URL=postgresql://gongji:gongji-password@127.0.0.1:5432/gongji
python scripts/migrate_sqlite_to_postgres.py
```

Set `SOURCE_SQLITE_PATH` first if the source file is not `Backend/compute_rental.db`.

## API

- `GET /api/locations/summary`
- `GET /api/cards`
- `POST /api/rentals`
- `GET /api/rentals/{rental_id}`
- `POST /api/rentals/{rental_id}/cancel`
- `POST /api/nodes/heartbeat`
