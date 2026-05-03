**Matika** | Version: **v0.0.4** | Copyright (c) 2026 Patrick James Tallman

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
`dev_setup.py` is idempotent — safe to run multiple times. It validates each path contains both `applug.json` and at least one `*_menus.json` before creating symlinks. `plugins.dev.json` is in `.gitignore` and is never committed.

### Required Environment Variables
```bash
# Generate a secure key (required — app refuses to start without it)
export SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")

# Or create a persistent .env file (copy .env.example first):
cp .env.example .env   # then edit .env
export $(cat .env | xargs)
```

`MATIKA_ENV=development` — set this in your local `.env` to allow AppLugs that declare
a released `matika_version` (e.g. `X.Y.Z`) to load when Matika is running at a `_dev`
version (e.g. `X.Y.Z_dev`). This relaxes only the version check — no other validation
changes. Never set this in production. Never commit `.env`.

### Run the Development Server
```bash
source .venv/bin/activate && export $(cat .env | grep -v '^#' | xargs) && PYTHONPATH=src uvicorn matika.main:app --host 127.0.0.1 --port 8000 --reload
```

Or as separate steps for clarity:
```bash
source .venv/bin/activate
export $(cat .env | grep -v '^#' | xargs)
PYTHONPATH=src uvicorn matika.main:app --host 127.0.0.1 --port 8000 --reload
```

Why each part is needed:
- `source .venv/bin/activate` — required; puts `venv/bin/` on PATH so `uvicorn` and all dependencies are found
- `export $(cat .env | grep -v '^#' | xargs)` — loads `SECRET_KEY` and `MATIKA_ENV` from `.env` into the shell (`grep -v '^#'` strips comment lines)
- `PYTHONPATH=src` — tells Python where to find the `matika` package
- `--reload` — auto-restarts the server on file changes

### Build TypeScript
```bash
npm run build   # compiles src/frontend/*.ts → src/matika/static/js/
```

### Database Migrations (Alembic)
```bash
PYTHONPATH=src alembic upgrade head                              # apply all pending
PYTHONPATH=src alembic current                                   # check revision
PYTHONPATH=src alembic revision --autogenerate -m "description"  # generate from model changes
PYTHONPATH=src alembic downgrade -1                              # roll back one
```

### Tests
```bash
pytest                                                      # all tests
pytest tests/test_auth.py                                   # one module
pytest tests/test_auth.py::test_login_success               # one test
```

---

## Architecture

Matika is a **plugin-agnostic FastAPI framework** — the core has zero knowledge of any business domain. Domain logic lives entirely in plugins called **AppLugs**.

### Core Layers

| Layer | Path | Role |
|---|---|---|
| Plugin engine | `src/matika/core/applug_service.py` | Discovers, loads, and registers AppLugs; builds role menu cache at startup |
| Menu loader | `src/matika/core/menu_loader.py` | `MenuLoaderService` — discovers and parses all `*_menus.json` files |
| Auth | `src/matika/auth/` | bcrypt, JWT, OAuth; `dependencies.py` provides `login_required`, `validate_csrf` |
| Database | `src/matika/database.py`, `models.py` | SQLAlchemy ORM; SQLite (dev) or PostgreSQL/MySQL (prod) |
| Migrations | `migrations/` | Alembic versioned migrations for core schema only |
| RBAC | `src/matika/security/service.py` | Role → Permission checks on every request; composite indexes on `permissions` |
| Rate limiter | `src/matika/core/rate_limiter.py` | In-process login limiter (10 failures / 5 min → 15-min lockout) |
| Routers | `src/matika/routers/` | `public.py` (login/register/home), `settings.py`, `admin.py` |
| Templates | `src/matika/templates/` | Jinja2; `maintenance_activity_base.html` is the standard two-panel admin layout |
| i18n | `src/matika/i18n.py` | Core locale + per-plugin override merging |
| Frontend | `src/frontend/` | Vanilla TypeScript → JS; `csrf.ts` shared helper |

---

### Plugin Management System

The `plugins/` directory is **intentionally empty in git**. Plugins are injected at setup time, never committed. There are three injection patterns:

#### 1. Development (symlinks via `dev_setup.py`)
```
plugins.dev.json.example   ← template, committed
plugins.dev.json           ← per-developer config, gitignored
scripts/dev_setup.py       ← validates + creates symlinks
plugins/eyerate → /path/to/eyerate   ← result
```
`dev_setup.py` validates each entry has `applug.json` AND at least one `*_menus.json` before symlinking. It is idempotent and handles broken/wrong-target symlinks interactively.

#### 2. Server deployment (git clone or `MATIKA_PLUGINS_DIR`)
```bash
# Option A — clone into plugins/ (simple single-server)
cd plugins && git clone https://github.com/org/eyerate.git eyerate

# Option B — separate directory (recommended for production)
MATIKA_PLUGINS_DIR=/opt/matika/plugins  # set in .env
# clone plugins into /opt/matika/plugins/
```
`MATIKA_PLUGINS_DIR` is read in `AppLugService.__init__()` (`applug_service.py:34`) before falling back to `ROOT_DIR/plugins`. It works at full runtime — not test-only.

#### 3. End-user installer (future)
Standalone `.dmg`/`.exe` built with PyInstaller. Bundles the framework + selected plugins. No Python environment required.

#### AppLug contract
Every plugin directory must contain:
- `applug.json` — manifest: `id`, `version`, `name`, `matika_version` (required — exact Matika version this AppLug was built and tested against), optional `display_name`, `entry_point`, `permissions`
- `<id>_menus.json` — consolidated menu file (schema v1.0) with two optional top-level sections:
  - `application` (optional) — an Application-type menu rendered as a dropdown in the plugin's hub
  - `roles` (optional) — array of role menus; each entry has `role`, `id`, `label_key`, and `items`
    - Admin role items: flat `Link` entries (no `Menu` wrapper)
    - Other role items: `Menu` wrapper containing nested links (dropdown behavior)
- Python class extending `BaseAppLug` with `on_load(db)` and `on_unload(db)`

`matika_version` (required) is checked at startup by `BaseAppLug._validate_compatibility()`. If absent or mismatched the AppLug is refused and skipped — a clear `RuntimeError` is logged. This is the compatibility contract baseline introduced in Matika 0.0.2; no breaking changes to `BaseAppLug` or the plugin discovery contract from this version forward.

`display_name` (optional) is the short UI label shown in the menu selector. Falls back to `name` if absent.

All plugin POST routes must add `check_page_permission` and `validate_csrf` dependencies.

---

### Menu Loading Pipeline

Menu data flows through two distinct phases:

#### Phase 1 — File loading (`MenuLoaderService`)

`MenuLoaderService` (`core/menu_loader.py`) scans two locations:

| Source | Path | Key |
|---|---|---|
| Core menus | `src/matika/menus/` | `"core"` |
| Plugin menus | `plugins/<id>/<id>_menus.json` | `"<plugin_id>"` |

Plugin menus are loaded via `load_applug_menus()`, which reads `*_menus.json` files (consolidated format). Core menus continue to use individual `*_menu.json` files. The service caches results after the first call (`load_all()` is lazy-cached; call `invalidate_cache()` to reset). Schema version `"1.0"` is enforced — files with other versions are skipped with a warning.

#### Phase 2 — Context building (`AppLugService.get_menus_for_context`)

Called per-request. Applies server-side role filtering and pre-translates labels before sending to the template:

1. Filter menus by `roles` field (menus whose entire item set is filtered away are hidden entirely)
2. Translate `label_key` → display label using the `t` dict
3. Build the **selector** structure (discriminated union: `item | separator | header`)
4. Build **hubs** for each selector entry

Selector ordering is fixed: `Default → (sep) → Favorites → (sep) → [Applications header] → plugins → (sep) → [Roles header] → roles`.

Hub ordering within each entry: plugin menus first → core non-System menus → core System (Help) menus last.

**Role hubs** are built from the `roles` sections of `*_menus.json` files plus core Role-type menus (e.g. `admin_menu.json`). `_build_role_menus` is removed — role menus are static file-driven, not generated from the permissions database.

**Admin dropdown** aggregates System menus and AppLug-contributed items. When two or more sources contribute items, `SectionHeader` items are injected to separate them. A single source never shows section headers.

**`fresh_login` session flag** is set on login and cleared after the first page load. While set, the Default hub is always shown regardless of the user's saved preference — ensuring a consistent landing state after login.

#### `*_menus.json` schema v1.0 (plugin consolidated format)

```json
{
  "schema_version": "1.0",
  "application": {
    "id": "unique-id",
    "label_key": "i18n_key",
    "items": [
      { "type": "Link",      "label_key": "k", "href": "/path", "open_new_tab": false },
      { "type": "Menu",      "label_key": "k", "items": [ ... ] },
      { "type": "Separator" }
    ]
  },
  "roles": [
    {
      "role": "Admin",
      "id": "unique-role-id",
      "label_key": "i18n_key",
      "items": [
        { "type": "Link", "label_key": "k", "href": "/path" }
      ]
    },
    {
      "role": "User",
      "id": "unique-role-id",
      "label_key": "i18n_key",
      "items": [
        { "type": "Menu", "label_key": "section", "items": [
          { "type": "Link", "label_key": "k", "href": "/path" }
        ]}
      ]
    }
  ]
}
```

Both `application` and `roles` are optional — a plugin may provide one, both, or neither.

`MenuType.DEFAULT` is a **selector entry type**, not a menu type. Default is an aggregated view assembled at runtime.

Core menus (`src/matika/menus/`) continue to use individual `*_menu.json` files with the `menus` array format. Core menus: `admin_menu.json` (type `Role`) and `help_menu.json` (type `System`). System-type menus always render last in every hub.

#### `menus_data` JSON injected into every page

```html
<script type="application/json" id="matika-menus">
  { "selector": [...], "hubs": { "__default__": [...], "eyerate": [...], ... } }
</script>
<meta name="user-id" content="{{ user.id }}">
<meta name="user-default-menu" content="{{ user_default_menu }}">
```

TypeScript reads these on `DOMContentLoaded`. Hub selection is persisted in `sessionStorage` under a per-user key (`matika_active_hub_<user_id>`) so navigating between pages preserves the selection.

**Default menu preference** is stored in `user_settings` (name=`"default_menu"`, value=hub_id). Priority on page load: `sessionStorage` → user saved preference → system Default.

---

### Deployment Use Cases

| Use Case | Audience | Plugin injection | Auth |
|---|---|---|---|
| Development | Plugin/framework developers | `dev_setup.py` symlinks via `plugins.dev.json` | Local `.env` |
| Server deployment | Technical operators | `MATIKA_PLUGINS_DIR` or `plugins/` clones | Server `.env` / secrets manager |
| End-user installer | Non-technical users | Bundled by vendor at build time | First-login password change |

See `docs/DEPLOYMENT.md` for the full operator guide and `docs/INSTALL.md` for end-user and developer installation steps.

---

### Key Runtime Patterns

- **Global auth dependency:** `inject_user_to_state` populates `request.state.user` on every request. Roles and settings are eager-loaded via `subqueryload`.
- **CSRF:** Session-based token generated in context processor. `validate_csrf` FastAPI dependency on all authenticated POST routes. JavaScript (`csrf.ts`) auto-injects token on form `submit` events; TypeScript files that call `form.submit()` programmatically must call `injectCsrfToken(form)` explicitly.
- **Session middleware:** `SessionMiddleware` issues cookies (cleared on browser close); 30-day absolute cap even for `is_persistent` (remember-me) sessions.
- **Security headers:** `SecurityHeadersMiddleware` adds `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`.
- **SECRET_KEY:** Hard-required — app refuses to start without it. Never has a default fallback.
- **`MATIKA_PLUGINS_DIR`:** Read in `AppLugService.__init__()`. Overrides `ROOT_DIR/plugins` at runtime. Tests set it to a pytest-managed temp dir via `conftest.py`; the project's `plugins/` directory is never touched during test runs.

---

### Persistence Layer

- **ORM:** Pure SQLAlchemy (zero raw SQL). Switching databases = change `DATABASE_URL`. No code changes required.
- **SQLite** (default): zero-config, single-user, ideal for dev and desktop installs.
- **PostgreSQL/MySQL:** set `DATABASE_URL`; connection pool (`pool_size=10`, `max_overflow=20`, `pool_pre_ping=True`) activates automatically for non-SQLite engines.
- **Migrations:** Alembic in `migrations/`. Core schema only — plugin tables are plugin-managed via `on_load()` → `create_all()`. Always run `alembic upgrade head` after pulling changes that touch `models.py`.
- **Performance:** `permissions` table has 5 indexes including composites on `(page_path, role_id)` and `(page_path, user_id)` — critical since this table is queried on every authenticated request.
- **N+1 prevention:** List-view routes use `selectinload()` for relationships. Export routes use `selectinload(Role.permissions)` to avoid per-role lazy queries.

---

### Security Model

- All admin POST routes have `check_page_permission` + `validate_csrf` dependencies.
- `check_page_permission` walks up the URL path hierarchy to find a matching permission (e.g. `/admin/roles/create` → checks `/admin/roles` → `/admin`).
- Server-side role filtering in `get_menus_for_context`: admin URLs are **never sent** to non-admin users in the `menus_data` JSON payload.
- Login rate limiting: 10 failures per IP in a 5-min window → 15-min lockout. Bypassed during `IS_TESTING`.
- File uploads: 5 MB cap on photos (magic-byte verified against JPEG/PNG/GIF/WebP); 10 MB cap on JSON imports.
- `CSRF` validation is bypassed when `IS_TESTING` (PYTEST_VERSION env var set). Tests do not need to include CSRF tokens in POST data.

---

### Testing

`tests/conftest.py` wires up a session-scoped test database (`data/test_matika.db`) using `MATIKA_PLUGINS_DIR` to point at a pytest-managed temp dir. The mock plugin in `tests/plugins/mock_plugin/` is copied there at session start — the real `plugins/` directory is never touched. Tests use `TestClient` (no async runner). `SECRET_KEY` is set in `conftest.py` before any app import.

---

## Release Pipeline

- `VERSION` is the single source of truth for version metadata. Never hand-edit version literals in any other file (`pyproject.toml`, `package.json`, etc.) — the release tooling propagates from `VERSION`.
- During development, `VERSION` carries a `_dev` suffix (e.g. `0.0.4_dev`). Propagated files always carry the stripped version (e.g. `0.0.4`) — `_dev` is a marker on `VERSION` only.
- `scripts/release.py <version>` is the release entry point: verifies `VERSION` currently reads `<target>_dev`, strips `_dev`, runs `sync_version.py`, runs the drift pre-flight check, commits. Does **not** push, tag, or create a GitHub release — those steps are manual, after human review.
- `scripts/sync_version.py` propagates `VERSION` into the allowlist of version-bearing files (currently `pyproject.toml` and `package.json`). When adding a new file with a version literal, add it to the script's allowlist.
- `scripts/sync_version.py --check` runs in read-only drift detection mode. Exits 0 (clean), 1 (drift), 2 (configuration error). `--check --json` produces structured output: `{"version": "...", "drift": [{"path": "...", "expected": "...", "found": "..."}]}`.
- Drift tests live under `tests/` — no `tests/scripts/` split needed because matika's top-level `conftest.py` doesn't have heavyweight autouse fixtures.

---

### Standing Rules
- Always add unit tests for new functionality; update existing tests for changed behaviour.
- All tests must pass with 0 skipped and 0 failed — no exceptions.
- Never hardcode `SECRET_KEY` — read from environment only.
- Never modify the production DB during testing.
- Flag best-practice violations before implementing; never silently comply.
- EyeRate-specific dependencies (`yfinance`, `curl_cffi`) belong in `eyerate/requirements.txt`, not in Matika's `requirements.txt`.
- Never run `git merge` — rebase or cherry-pick only.
- Never run `rm -rf` on any directory.
- Developer handles git staging and commits manually; do not stage or commit unless explicitly granted full git permissions for the session.
- `MATIKA_ENV=development` must never be committed — it belongs only in the local `.env`.
