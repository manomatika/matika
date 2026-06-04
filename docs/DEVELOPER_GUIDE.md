# Matika Developer Guide

Authoritative reference for developers working on Matika core or building AppLugs.

---

## Architecture: matika / applug / ahimsa as siblings

The ecosystem is three sibling repositories, **not** a single workspace:

| Repo | Role |
|---|---|
| [`manomatika/matika`](https://github.com/manomatika/matika) | The framework — plugin-agnostic FastAPI host, RBAC, menu hub, security. Source of truth for the AppLug contract. |
| [`manomatika/eyerate`](https://github.com/manomatika/eyerate) (and other applugs) | A plugin (AppLug). Lives in its own repo and runs *inside* matika at startup. Multiple applugs may coexist; eyerate is the reference example. |
| [`manomatika/ahimsa`](https://github.com/manomatika/ahimsa) | Build / validate / release tooling. Consumes tagged matika + applug releases via `recipe.json` and produces installers. Downstream of both. |

In dev, the three repos are cloned as siblings (e.g. `~/dev/projects/matika`, `~/dev/projects/eyerate`, `~/dev/projects/ahimsa`). Matika discovers applugs at startup via a symlink under `plugins/` (created by `scripts/dev_setup.py` from `plugins.dev.json`) or via `MATIKA_PLUGINS_DIR`.

---

## Development Environment Setup

**Prerequisites**
- Python 3.12+
- Node.js 18+ and npm
- `uv` (Python package manager)
- Git

### First-time setup (per machine)

These steps run once. After the first run, `.venv/` exists, dependencies are installed, and the frontend is compiled — you only repeat them when something changes (`requirements.txt`, `package.json`, model migrations).

```bash
# Clone the framework
git clone https://github.com/manomatika/matika.git
cd matika

# Create the venv (one time only)
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt

# Frontend
npm install
npm run build             # compile TypeScript → src/matika/static/js/

# Database
export PYTHONPATH=$(pwd)/src
alembic upgrade head      # apply all migrations
```

**Required `.env` settings for local development**

```bash
cp .env.example .env
# Then edit .env and set:
SECRET_KEY=<generate with: python3 -c "import secrets; print(secrets.token_urlsafe(64))">
MATIKA_ENV=development
```

`.env` is gitignored. Never commit it.

### Set up an AppLug for local development (one-time per machine)

```bash
cp plugins.dev.json.example plugins.dev.json
# Edit plugins.dev.json to point at your local plugin repo paths, then:
python scripts/dev_setup.py
```

`dev_setup.py` is idempotent. It validates each path contains `applug.json` and at least one `*_menus.json` (plural — the consolidated applug menu format, matching what `scripts/dev_setup.py` actually globs for) before creating symlinks into `plugins/`.

---

## Cold-start (per shell session)

Once first-time setup is done, each new terminal session only needs to **activate the venv**, **load env vars**, and **launch the server**. The venv creation, dependency install, frontend build, and migrations from first-time setup do not repeat.

```bash
cd ~/dev/projects/matika              # (or wherever you cloned matika)
source .venv/bin/activate
export $(cat .env | grep -v '^#' | xargs)
PYTHONPATH=src uvicorn matika.main:app --host 127.0.0.1 --port 8000 --reload
```

**Why each line matters:**

| Step | Reason |
|---|---|
| `source .venv/bin/activate` | Puts `.venv/bin/` on PATH. A fresh shell otherwise reports `uvicorn: command not found` — every developer hits this once. |
| `export $(cat .env \| grep -v '^#' \| xargs)` | Loads `SECRET_KEY` (required — app refuses to start without it) and `MATIKA_ENV=development` (see below). `grep -v '^#'` strips comment lines. |
| `PYTHONPATH=src` | Tells Python where to find the `matika` package. |
| `--reload` | Auto-restarts on Python file changes (does not pick up static assets — hard-reload the browser after `npm run build`). |

Open `http://127.0.0.1:8000`.

### What `MATIKA_ENV=development` does

When Matika is at a `_dev` version (e.g. `0.0.4_dev`) the strict version check would normally refuse any AppLug declaring just the released base version (e.g. `0.0.4`). Setting `MATIKA_ENV=development` strips the `_dev` suffix before comparing, so `0.0.4_dev` is treated as `0.0.4` — compatible with applugs that declare the base version.

A warning is logged on every startup when this relaxation is active:
```
WARNING — Running in development mode — matika version check relaxed. Never use in production.
```

This only affects the version check. No other validation is relaxed.

**On first run** Matika creates `data/matika.db` (SQLite), seeds the Admin role and a default admin user, and scans `plugins/` for AppLugs.

---

## Cold-start: browser-testing the EyeRate AppLug under Matika

This is the full sequence for verifying eyerate's `/eyerate/securities` page (or any other applug) end to end. Assumes both repos are cloned as siblings and first-time setup has run for matika.

### Prerequisites (one-time per machine)

1. **Sibling layout:**
   ```
   ~/dev/projects/
     matika/        ← framework
     eyerate/       ← the AppLug under test (or any applug repo)
     ahimsa/        ← release/build tooling (not needed for dev)
   ```
2. **`matika/plugins.dev.json`** lists the applug's path:
   ```bash
   cd ~/dev/projects/matika
   cp plugins.dev.json.example plugins.dev.json
   # Edit to:  { "plugins": ["../eyerate"] }
   ```
3. **`matika/plugins/eyerate` symlink** to the applug repo, created by `dev_setup.py`:
   ```bash
   python scripts/dev_setup.py
   ```
4. **`.env`** has both `SECRET_KEY` and `MATIKA_ENV=development` (see above). The dev-mode flag is essential here: matika's `VERSION` is `0.0.4_dev` while eyerate's `applug.json` declares `matika_version: "0.0.4"`. Without `MATIKA_ENV=development`, matika refuses eyerate at startup.

### Launch sequence (every shell session)

```bash
cd ~/dev/projects/matika
source .venv/bin/activate
export $(cat .env | grep -v '^#' | xargs)
PYTHONPATH=src uvicorn matika.main:app --host 127.0.0.1 --port 8000 --reload
```

### Browser test

Open `http://127.0.0.1:8000/eyerate/securities`. Log in as `admin` / `adminpassword` (first-login forces a password change). The EyeRate Securities maintenance page should render with all five Financial Security Type options populated in its dropdown.

---

## Applug Compatibility

### `matika_version` in `applug.json`

Every AppLug must declare the Matika version it was built and tested against:
```json
{ "matika_version": "X.Y.Z" }
```

### Production (strict matching)

`matika_version` must equal the running Matika version exactly. A mismatch is a hard refusal — the AppLug is skipped at startup with a clear error logged.

### Development (`MATIKA_ENV=development`)

The `_dev` suffix is stripped from the running version before comparing. An AppLug declaring `X.Y.Z` loads under Matika `X.Y.Z_dev` (treated as `X.Y.Z` for compatibility purposes — base version match is sufficient).

Never publish an AppLug with a `_dev` value in `matika_version`. That field must always reference a released version.

---

## Git Conventions

### Branch naming
```
feature/<short-description>
fix/<short-description>
chore/<short-description>
```

### Commit messages
```
type: short imperative summary (≤72 chars)

- bullet details if needed

Closes #N
```
Types: `feat`, `fix`, `chore`, `docs`, `test`, `refactor`.

### Never commit
- `.env` — contains secrets
- `__pycache__/`, `*.pyc` — generated bytecode
- `plugins.dev.json` — per-developer plugin config
- `plugins/` contents — injected at setup time, never committed
- Any file with a hardcoded secret or credential

Developers handle all `git add` and `git commit` manually. Do not automate staging.

---

## Running Tests

```bash
# Full suite
pytest

# Single module
pytest tests/test_applug_system.py

# Single test
pytest tests/test_applug_system.py::test_dev_mode_dev_version_compatible_with_base_released_version
```

All tests must pass before committing. No skipped or `xfail` tests without explicit maintainer approval. The test suite uses an isolated SQLite database (`data/test_matika.db`) and a pytest-managed temp directory for plugins — the real `plugins/` directory is never touched.

---

## Adding a New AppLug

Every AppLug directory must contain:
- `applug.json` — manifest with `id`, `version`, `name`, `matika_version`, `entry_point`, optional `display_name` and `permissions`
- `<id>_menus.json` — consolidated menu file (schema v1.0, see below)
- A Python class extending `BaseAppLug` with `on_load(db)` and `on_unload(db)` methods

### `*_menus.json` schema

The consolidated menu file is the sole source of truth for all menus an AppLug contributes. Menu structure is never stored in the database — it is loaded from this file and cached in memory at startup.

```json
{
  "schema_version": "1.0",
  "menus": {
    "application": {
      "id": "eyerate-main",
      "label_key": "menu_eyerate",
      "items": [
        { "type": "Link", "label_key": "item_securities", "href": "/eyerate/securities" }
      ]
    },
    "roles": [
      {
        "role": "User",
        "id": "eyerate-user",
        "label_key": "menu_eyerate",
        "items": [
          {
            "type": "Menu",
            "label_key": "menu_eyerate",
            "items": [
              { "type": "Link", "label_key": "item_securities", "href": "/eyerate/securities" }
            ]
          }
        ]
      },
      {
        "role": "Admin",
        "id": "eyerate-admin",
        "label_key": "menu_eyerate",
        "items": [
          {
            "type": "Menu",
            "label_key": "menu_eyerate",
            "items": [
              { "type": "Link", "label_key": "item_eyerate_admin", "href": "/eyerate/admin" }
            ]
          }
        ]
      }
    ]
  }
}
```

**Sections (all optional):**

| Key | Shape | Purpose | Selector placement |
|---|---|---|---|
| `application` | single dict | App-wide menu visible to all authenticated users | Applications section |
| `roles` | array of role entries | Per-role menus; each entry targets one role by name | Roles section (only if user holds that role) |
| `system` | single dict | Framework-level menu rendered last in every hub | Always visible (e.g. Help) |

- `application` — omit if the AppLug needs no application menu
- `roles` — omit if the AppLug contributes no role-specific menus; add as many role entries as needed
- `system` — reserved for framework-level menus (Help, About). Core uses this for `help_menus.json`. AppLugs may omit it.

**Full menu matrix (EyeRate as reference):**

| | User role | Admin role |
|---|---|---|
| Application menu (`/eyerate/securities`) | visible | visible |
| Role hub — User | visible | hidden |
| Role hub — Admin | hidden | visible |
| `/eyerate/securities` permission | FULL | FULL |
| `/eyerate/admin` permission | NONE | FULL |

**Startup warning:** If an AppLug directory contains a `*_permission.json` file but no `*_menus.json`, Matika logs a loud warning at startup:
```
WARNING: AppLug '<id>' declares permissions but provides no *_menus.json.
Its pages will be unreachable from any menu. This is likely a development oversight.
```

See `docs/ARCHITECTURE.md` for the full AppLug contract and `docs/INSTALL.md` for installation steps.
