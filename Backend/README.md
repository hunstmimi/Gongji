# Backend

FastAPI backend for the compute rental system.

It supports two database modes:

- local SQLite for development/tests
- Postgres via `DATABASE_URL` for deployment (for example Neon on Vercel)

## Run

```bash
pip install -r requirements.txt
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Run from the `Backend` directory.

## Environment Variables

Copy `Backend/.env.example` into a local `.env` file if you want a template.

- `DATABASE_URL`: Postgres connection string for Neon/Vercel deployment
- `COMPUTE_RENTAL_DB_PATH`: local SQLite path used when `DATABASE_URL` is empty
- `CORS_ALLOWED_ORIGINS`: comma-separated frontend origins to allow in addition to local Vite URLs
- `COMPUTE_RENTAL_SSH_USERNAME_PREFIX`: prefix for generated rental environment usernames
- `COMPUTE_RENTAL_SSH_PORT_BASE`: base port for generated rental environment SSH endpoints
- `COMPUTE_RENTAL_SSH_PASSWORD_SEED`: local seed used to derive demo rental environment passwords

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

## API

- `GET /api/locations/summary`
- `GET /api/cards`
- `POST /api/rentals`
- `GET /api/rentals/{rental_id}`
- `POST /api/rentals/{rental_id}/cancel`
