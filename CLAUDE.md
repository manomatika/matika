# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Development Setup
```bash
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt
npm install
export PYTHONPATH=$PYTHONPATH:$(pwd)/src
```

### Plugin Setup (one-time per machine)
```bash
# Copy the example config and edit it to point at your local plugin repos
cp plugins.dev.json.example plugins.dev.json
# Edit plugins.dev.json, then run:
python scripts/dev_setup.py
```
This replaces the manual `ln -s` approach. `dev_setup.py` is idempotent — run it again any time to add or verify plugins. `plugins.dev.json` is in `.gitignore` and is never committed.

### Required Environment Variables
```bash
# Generate a secure key (required — app refuses to start without it)
export SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")

# Or create a persistent .env file:
echo "SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(64))')" > .env
export $(cat .env | xargs)
```

### Run the App
```bash
SECRET_KEY=<your-key> PYTHONPATH=src uvicorn matika.main:app --host 127.0.0.1 --port 8000 --reload
```

### Build TypeScript
```bash
npm run build   # compiles src/frontend/*.ts → src/matika/static/js/
```

### Database Migrations (Alembic)
```bash
# Apply all pending migrations to the live database
PYTHONPATH=src alembic upgrade head

# Check current migration revision
PYTHONPATH=src alembic current

# Generate a new migration after changing models.py
PYTHONPATH=src alembic revision --autogenerate -m "describe_change"

# Roll back one migration
PYTHONPATH=src alembic downgrade -1
```

### Tests
```bash
pytest                                                      # all tests
pytest tests/test_auth.py                                   # one module
pytest tests/test_auth.py::test_login_success               # one test
```

## Architecture

Matika is a **plugin-agnostic FastAPI framework** — the core has zero knowledge of any business domain. Domain logic lives entirely in plugins called **AppLugs**.

### Core Layers

| Layer | Path | Role |
|---|---|---|
| Plugin engine | `src/matika/core/applug_service.py` | Discovers, loads, and registers AppLugs; builds role menu cache at startup |
| Menu Hub | `src/matika/core/menu_loader.py` | Loads `*_menu.json` files; `MenuLoaderService` provides menus to the selector |
| Auth | `src/matika/auth/` | bcrypt password hashing, JWT, OAuth; FastAPI DI via `dependencies.py`; `validate_csrf` for CSRF protection |
| Database | `src/matika/database.py`, `models.py` | SQLAlchemy ORM + SQLite (dev) or PostgreSQL/MySQL (prod); connection pool configured automatically per engine |
| Migrations | `migrations/` | Alembic versioned migrations for the core schema; plugin tables use `create_all()` in `on_load()` |
| RBAC | `src/matika/security/service.py` | Role → Permission enforcement; PermissionLevel enum; `permissions` table has composite indexes on `(page_path, role_id)` and `(page_path, user_id)` |
| Rate limiter | `src/matika/core/rate_limiter.py` | In-process login rate limiter (10 failures / 5 min → 15-min lockout) |
| Routers | `src/matika/routers/` | `public.py` (login/register), `settings.py`, `admin.py` |
| Templates | `src/matika/templates/` | Jinja2; `maintenance_activity_base.html` is the standard two-panel admin layout |
| i18n | `src/matika/i18n.py` | Locale merging across core + all plugins |
| Frontend | `src/frontend/` | Vanilla TypeScript compiled to JS; `csrf.ts` shared CSRF helper |

### Plugin System (AppLugs)

Each plugin lives in `plugins/<name>/` and must contain:
- `applug.json` — manifest (id, version, `name`, optional `display_name`, entry_point, permissions)
- `<id>_menu.json` — menu metadata (schema v1.0; MenuType: Application/Role/System/Favorites)

At startup, `applug_service.py` scans the plugins directory, loads manifests, imports the entry class, and calls `on_load()`. Menu metadata is loaded separately by `MenuLoaderService`.

### Menu Hub System

Three-zone menu bar: **[M logo]** | **[Selector + Hub items]** | **[User avatar]**

- **Selector** — structured dropdown: Default → Favorites → Applications (per plugin) → Roles (per role with menus)
- **Default hub** — one submenu per AppLug + core menus (Help always last)
- **Application hub** — that plugin's menus + Help
- **Role hub** — built at startup from permissions DB; shows all pages the role can access
- **Hub items** — click-to-toggle dropdowns; user zone retains CSS hover

`menus_data` is server-side rendered as JSON in `<meta name="csrf-token">` and a `<script type="application/json" id="matika-menus">` tag. TypeScript reads it at boot.

### Key Runtime Patterns

- **Global auth dependency:** `inject_user_to_state` populates `request.state.user` on every request.
- **CSRF:** Session-based token; `validate_csrf` dependency on all authenticated POST routes; JavaScript injects token into form submissions.
- **Session middleware:** `SessionMiddleware` issues cookies (cleared on browser close); 30-day absolute cap even for persistent sessions.
- **Security headers:** `SecurityHeadersMiddleware` adds X-Frame-Options, X-Content-Type-Options, Referrer-Policy.
- **SECRET_KEY:** Hard required — app refuses to start without it. Never falls back to a default.
- **MATIKA_PLUGINS_DIR env var:** Tests use a pytest-managed temp directory; the project's `plugins/` symlinks are never touched by test runs.

### Persistence Layer

- **ORM:** Pure SQLAlchemy (no raw SQL anywhere). Switching databases = change `DATABASE_URL`.
- **SQLite** (default): zero-config, single-user, ideal for desktop/dev deployment.
- **PostgreSQL/MySQL**: set `DATABASE_URL`; connection pool (pool_size=10, max_overflow=20, pool_pre_ping=True) activates automatically.
- **Migrations:** Alembic in `migrations/`. Core schema only; plugin tables are plugin-managed via `create_all()`. Always run `alembic upgrade head` after pulling schema changes.
- **Indexes:** `permissions` table has 5 indexes including composites on `(page_path, role_id)` and `(page_path, user_id)` — critical for per-request auth performance.

### Testing

`tests/conftest.py` wires up a session-scoped test database (`data/test_matika.db`) using `MATIKA_PLUGINS_DIR` env var to point to a pytest-managed temp dir (never touches `plugins/`). Tests use `TestClient` — no async runner needed. `SECRET_KEY` is set in conftest before any app import.

### Standing Rules
- Always add unit tests for new functionality; update existing tests for changed functionality.
- All tests must be green before moving to the next phase or declaring work done.
- Never hardcode `SECRET_KEY` — read from environment only.
- Never modify the production DB during testing (use the test DB fixtures).
- Flag best-practice violations before implementing; do not silently comply.
