**Matika** | Version: **v0.0.4** | Copyright (c) 2026 Patrick James Tallman


# Matika Deployment Guide

This guide is for **technical operators** deploying Matika to a server.
If you are an end user installing a Matika-based application on your personal
computer, use the installer provided by your application vendor — you do not
need this guide.

---

## 1. Deployment Model

Matika is a stateless FastAPI application. The `plugins/` directory is
**intentionally empty** in the core repository; plugins are injected at
deployment time. This means a single core codebase can power many distinct
product configurations depending on which plugins are installed.

---

## 2. Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | **Required** | Secures session cookies and CSRF tokens. Generate with `python3 -c "import secrets; print(secrets.token_urlsafe(64))"`. Never use a default. |
| `DATABASE_URL` | Optional | SQLite (default) or `postgresql://user:pass@host/db`. Switching databases requires no code changes. |
| `MATIKA_PLUGINS_DIR` | Optional | Overrides the plugins directory path. In production, point this at a directory outside the core repository containing your licensed AppLugs. If unset, defaults to `plugins/` relative to the application root. |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Optional | Enable Google OAuth |
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | Optional | Enable GitHub OAuth |

Copy `.env.example` to `.env` and populate before starting.

Example — using `MATIKA_PLUGINS_DIR`:
```bash
MATIKA_PLUGINS_DIR=/opt/matika/plugins
```

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

# 4. Plugins — choose one option:

# Option A: Use MATIKA_PLUGINS_DIR (recommended — keeps core repo clean)
mkdir -p /opt/matika/plugins
cd /opt/matika/plugins
git clone https://github.com/pjtallman/eyerate.git eyerate
# Add to .env: MATIKA_PLUGINS_DIR=/opt/matika/plugins

# Option B: Clone directly into plugins/ (simpler single-server setups)
cd plugins/
git clone https://github.com/pjtallman/eyerate.git eyerate

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

**Plugin schemas** (e.g. EyeRate's `securities` table) are not managed by core
Alembic migrations. Plugins apply their own schema changes via `on_load()` →
`create_all()` at startup.

Plugin menu definitions (`*_menu.json`) are loaded by the `MenuLoaderService`
at startup. No database migration is required for menu changes. After adding or
modifying a plugin's menu JSON, restart the server.

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
- [ ] `plugins/` directory in the core repository is empty and not committed to git
- [ ] `MATIKA_PLUGINS_DIR` (if set) points to a directory containing only trusted, reviewed AppLugs
- [ ] Default admin password changed on first login (`force_password_change=True` is the default)

---

## 9. Automated Build System

`scripts/release.py` automates versioning and GitHub release creation for the
core framework. For full deployment, pair the core release with the specific
plugin releases required for the target environment.

---

## 10. Development Setup

This section documents the full developer workflow for contributors and AppLug developers.

### Prerequisites
- Python 3.14+
- Node.js 18+
- `uv` (`pip install uv`)
- Git

### One-time setup
```bash
# Clone and enter the repo
git clone https://github.com/pjtallman/Matika.git && cd Matika

# Python environment
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt

# Frontend
npm install && npm run build

# Secret key
cp .env.example .env
# Edit .env and set SECRET_KEY

# Database
export $(cat .env | xargs)
PYTHONPATH=src alembic upgrade head
```

### Plugin wiring (one-time per machine)
```bash
cp plugins.dev.json.example plugins.dev.json
# Edit plugins.dev.json to point at your local plugin repos
python scripts/dev_setup.py
```

### Run (development)
```bash
SECRET_KEY=<key> PYTHONPATH=src uvicorn matika.main:app \
  --host 127.0.0.1 --port 8000 --reload
```

### Tests
```bash
pytest                          # all tests
pytest tests/test_auth.py       # single module
pytest tests/test_auth.py::test_login_success   # single test
```

See `CLAUDE.md` for the authoritative command reference.
