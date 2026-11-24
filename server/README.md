# Ososbo local server (stage 1)

Python 3.12+, FastAPI, SQLAlchemy, SQLite, Alembic.

## Setup

```bash
cd server
uv sync
cp .env.example .env
```

## Database

```bash
uv run alembic upgrade head
uv run python scripts/seed.py
```

`AUTO_MIGRATE=true` (default) also applies migrations when the app starts.

## Run

```bash
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- OpenAPI: http://127.0.0.1:8000/docs
- Health: `GET /api/v1/health`
- Menu: `GET /api/v1/menu` (requires device Bearer token for roles `kiosk` or `operator`)

## Device registration

```bash
uv run ososbo create-registration-code --role kiosk
# then POST /api/v1/devices/register with { "code", "role", "name?" }
```

## Tests / lint

```bash
uv run pytest
uv run ruff check
```

## Deferred (not in stage 1)

- **TLS** inside the local network (custom CA + pinning) — SPEC §11.1 / §12.4
- **Database backup before migration** (`VACUUM INTO` / `.backup`) — SPEC §5.11
