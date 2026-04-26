**Matika** | Version: **0.0.2_dev** | Copyright (c) 2026 Patrick James Tallman

# Matika Deployment Guide

## 1. Deployment Model

Matika is a stateless FastAPI application. The `plugins/` directory is **intentionally empty** in the core repository; plugins are injected at deployment time. This means a single core codebase can power many distinct product configurations depending on which plugins are installed.

---

## 2. Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | **Required** | Secures session cookies and CSRF tokens. Generate with `python3 -c "import secrets; print(secrets.token_urlsafe(64))"`. Never use a default. |
| `DATABASE_URL` | Optional | SQLite (default) or `postgresql://user:pass@host/db`. Switching databases requires no code changes. |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Optional | Enable Google OAuth |
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | Optional | Enable GitHub OAuth |
| `MATIKA_PLUGINS_DIR` | Optional | Override the plugin directory path (used by the test suite; leave unset in production) |

Copy `.env.example` to `.env` and populate before starting.

---

## 3. Production Setup (Manual)

```bash
# 1. Clone core
git clone https://github.com/pjtallman/Matika.git && cd Matika

# 2. Python environment
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt

# 3. Frontend
npm install && npm run build

# 4. Plugins
cd plugins/
git clone https://github.com/pjtallman/eyerate.git eyerate
cd ..

# 5. Environment
cp .env.example .env
# → Set SECRET_KEY and DATABASE_URL in .env

# 6. Migrations
export $(cat .env | xargs)
PYTHONPATH=src alembic upgrade head

# 7. Start
PYTHONPATH=src uvicorn matika.main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## 4. Docker Deployment

```bash
docker-compose up -d
```

Set `SECRET_KEY` and optionally `DATABASE_URL` in `docker-compose.yml` environment section. The image runs `uvicorn matika.main:app --host 0.0.0.0 --port 8000` internally.

**Important:** Run migrations before starting new containers that contain schema changes:
```bash
docker-compose run --rm app sh -c "PYTHONPATH=src alembic upgrade head"
```

---

## 5. PostgreSQL for Multi-User Deployments

SQLite is appropriate for single-user or desktop installations. For shared servers:

1. Create a PostgreSQL database:
   ```sql
   CREATE DATABASE matika;
   CREATE USER matika_user WITH PASSWORD 'strong_password';
   GRANT ALL PRIVILEGES ON DATABASE matika TO matika_user;
   ```

2. Set `DATABASE_URL=postgresql://matika_user:strong_password@localhost/matika` in `.env`.

3. Run migrations: `PYTHONPATH=src alembic upgrade head`.

Matika automatically enables connection pooling (`pool_size=10`, `max_overflow=20`, `pool_pre_ping=True`) for non-SQLite databases.

---

## 6. Schema Migrations

Matika uses **Alembic** for versioned schema management. This is mandatory in any environment where the database already exists and a code update includes model changes.

```bash
# Apply all pending migrations (run after every pull that touches models.py)
PYTHONPATH=src alembic upgrade head

# Check current revision
PYTHONPATH=src alembic current

# Roll back one revision
PYTHONPATH=src alembic downgrade -1
```

**Plugin schemas** (e.g. EyeRate's `securities` table) are not managed by core Alembic migrations. Plugins apply their own schema changes via `on_load()` → `create_all()` at startup.

---

## 7. Zero-Downtime Deployments

For high-availability setups (multiple uvicorn workers or replicas):

1. Deploy new code to the next instance **without** stopping existing ones.
2. Run `alembic upgrade head` — Alembic migrations are designed to be backward-compatible (additive changes only).
3. Perform a rolling restart of application instances.

The `pool_pre_ping=True` setting ensures stale connections are detected and recycled automatically.

---

## 8. Security Checklist

- [ ] `SECRET_KEY` set to a cryptographically random value (≥ 64 bytes)
- [ ] `DATABASE_URL` points to PostgreSQL for multi-user deployments
- [ ] `alembic upgrade head` run after every deployment
- [ ] HTTPS termination at the load balancer / Nginx
- [ ] `plugins/` directory contains only trusted, reviewed AppLugs
- [ ] Admin password changed on first login (`force_password_change=True` is the default)

---

## 9. Automated Build System

`scripts/release.py` automates versioning and GitHub release creation for the core framework. For full deployment, pair the core release with the specific plugin releases required for the target environment.
