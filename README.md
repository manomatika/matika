**Matika** | Version: **v0.0.2** | Copyright (c) 2026 Patrick James Tallman


# Matika — Dynamic AppLug Framework

Matika is a high-performance, plugin-agnostic framework built with **FastAPI** and **TypeScript**. The core provides authentication, RBAC, dynamic navigation, and security; all business logic lives in **AppLugs** (plugins) that the framework discovers at runtime without any prior knowledge of them.

## Core Features

- **Dynamic Plugin Discovery** — AppLugs loaded from `plugins/` at startup; routes, menus, permissions, and i18n strings merged automatically.
- **Menu Hub** — Three-zone navigation bar with a structured selector (Default / Favorites / Applications / Roles), click-to-toggle hub dropdowns, and role-based menu caching built from the permissions database.
- **RBAC** — Centralized Role-Based Access Control with per-request permission checks. Permissions table indexed for O(log n) lookups.
- **Security** — CSRF protection on all authenticated POST routes; login rate limiting; security headers; file upload size limits and magic-byte validation; hard-required `SECRET_KEY`.
- **Authentication** — bcrypt password hashing, JWT, OAuth (Google / GitHub). Session cookies with idle timeout and 30-day absolute cap.
- **Database Portability** — Pure SQLAlchemy ORM; zero raw SQL. Switch from SQLite to PostgreSQL with one environment variable. Alembic for versioned migrations.
- **Internationalization** — Core strings + per-plugin locale overrides merged at runtime.
- **Data Management** — User and system data export/import (10 MB file limit).

## Architecture

```
[Plugins: applug.json + *_menu.json + Python code]
         ↕ runtime discovery
[Matika Core: FastAPI + SQLAlchemy + Jinja2 + TypeScript]
         ↕ DATABASE_URL
[SQLite (dev) | PostgreSQL/MySQL (production)]
```

See [Architecture Overview](doc/ARCHITECTURE.md) for the full technical design.

## Quick Start

```bash
# Setup
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt
npm install && npm run build

# Required: generate a secret key
export SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")

# Migrations
PYTHONPATH=src alembic upgrade head

# Run
PYTHONPATH=src uvicorn matika.main:app --host 127.0.0.1 --port 8000 --reload
```

Open **http://127.0.0.1:8000** — log in with `admin` / `adminpassword` (password change required on first login).

## Plugin Development

A minimal AppLug requires:

| File | Purpose |
|---|---|
| `applug.json` | Manifest: id, version, name, display_name, entry_point, permissions |
| `<id>_menu.json` | Menu metadata (schema v1.0; MenuType: Application/Role/System/Favorites) |
| Python class extending `BaseAppLug` | `on_load(db)` + `on_unload(db)` |

See [EyeRate](https://github.com/pjtallman/eyerate) for the reference implementation.

## Documentation

| Document | Description |
|---|---|
| [INSTALL.md](doc/INSTALL.md) | Step-by-step installation for developers and end users |
| [DEPLOYMENT.md](doc/DEPLOYMENT.md) | Production deployment, PostgreSQL setup, migrations, zero-downtime |
| [ARCHITECTURE.md](doc/ARCHITECTURE.md) | Full technical architecture, persistence layer, security model |

## License
Copyright (c) 2026 Patrick James Tallman. All Rights Reserved.
