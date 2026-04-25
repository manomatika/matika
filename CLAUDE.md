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

### Run the App
```bash
PYTHONPATH=src uvicorn matika.main:app --host 127.0.0.1 --port 8000 --reload
```

### Build TypeScript
```bash
npm run build   # compiles src/frontend/*.ts → src/matika/static/js/
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
| Plugin engine | `src/matika/core/applug_service.py` | Discovers, loads, and registers AppLugs |
| Auth | `src/matika/auth/` | bcrypt password hashing, JWT, OAuth; FastAPI DI via `dependencies.py` |
| Database | `src/matika/database.py`, `models.py` | SQLAlchemy + SQLite/Postgres; core entities: User, Role, Permission, UserSetting, SystemSetting |
| RBAC | `src/matika/security/service.py` | Role → Permission enforcement; PermissionLevel enum (NONE/BROWSE/MAINTAIN/ADMIN) |
| Routers | `src/matika/routers/` | `public.py` (login/register), `settings.py`, `admin.py` |
| Templates | `src/matika/templates/` | Jinja2; `maintenance_activity_base.html` is the standard two-panel admin layout |
| i18n | `src/matika/i18n.py` | Locale merging across core + all plugins |
| Frontend | `src/frontend/` | Vanilla TypeScript compiled to JS; one file per page |

### Plugin System (AppLugs)

Each plugin lives in `plugins/<name>/` and contains an `applug.json` manifest. At startup, `applug_service.py` scans that directory, reads manifests, imports each plugin package, and calls `on_load()` on a class that extends `BaseAppLug`.

Plugins can:
- Register FastAPI routers with their own routes
- Add database tables (via `on_load()`)
- Contribute menu items, permissions/roles, and i18n locale strings
- Extend the Jinja2 context

### Key Runtime Patterns

- **Global auth dependency:** `inject_user_to_state` populates `request.state.user` on every request.
- **Session middleware:** `SessionMiddleware` issues session cookies that expire on browser close.
- **PageType enum** (`src/matika/core/constants.py`): classifies pages as PUBLIC, AUTHENTICATED, or ADMIN to drive access control.
- **Two-panel template:** Plugin maintenance pages should extend `maintenance_activity_base.html`.

### Testing

`tests/conftest.py` wires up a session-scoped test database (`data/test_matika.db`), a mock plugin, and shared fixtures (`db`, `client`, `test_user`, `test_admin`). Tests use `TestClient` — no async test runner needed.
