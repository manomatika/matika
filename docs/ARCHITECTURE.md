**Matika** | Version: **v0.0.4** | Copyright (c) 2026 Patrick James Tallman


# Matika Technical Architecture & Design

## 1. Executive Summary
Matika is a high-performance, plugin-agnostic framework built with a modern, layered architecture. It provides a core foundation for authentication, Role-Based Access Control (RBAC), dynamic navigation, and security, which can be extended via **AppLugs** (plugins). The framework is designed to have zero hardcoded knowledge of the applications it hosts, enabling a strictly decoupled development model.

## 2. The "No-Knowledge" Principle
The foundational rule of Matika is that the core repository must remain domain-agnostic.
- **Core:** Handles user sessions, permissions, internationalization, security, and plugin discovery.
- **AppLugs:** Handle domain logic (e.g., financial tracking, reporting).
- **Integration:** Matika discovers plugins at runtime via `applug.json` manifests and dynamically integrates their routes, models, and menu metadata.

## 3. Technology Stack
- **Backend:** [FastAPI](https://fastapi.tiangolo.com/) (Python 3.14+)
- **Database:** [SQLite](https://sqlite.org/) (default, zero-config) or **PostgreSQL/MySQL** via [SQLAlchemy](https://www.sqlalchemy.org/) ORM
- **Migrations:** [Alembic](https://alembic.sqlalchemy.org/) for versioned core schema migrations
- **Authentication:** Direct **bcrypt** hashing (optimized for Python 3.14+)
- **Frontend:** [Jinja2](https://palletsprojects.com/p/jinja/) Templates, [TypeScript](https://www.typescriptlang.org/), Vanilla CSS
- **Tooling:** `uv` for Python environment, `npm` for TypeScript compilation, `pytest` for testing

## 4. Folder Structure
```
/
├── .env.example            # Required environment variables (copy → .env)
├── alembic.ini             # Alembic configuration (DATABASE_URL set from env)
├── data/                   # Persistent storage (SQLite .db files)
├── docs/                   # Technical documentation
├── migrations/             # Alembic versioned schema migrations
│   └── versions/           # One file per migration revision
├── plugins/                # AppLug directory (empty in core repo; populated at deploy)
├── scripts/                # Dev/Ops automation (release, milestone, sync)
├── src/                    # Source code root
│   ├── frontend/           # TypeScript source files (compiled to static/js/)
│   │   └── csrf.ts         # Shared CSRF token helper
│   └── matika/             # Main framework package
│       ├── auth/           # Authentication logic, JWT, OAuth, CSRF dependency
│       ├── core/           # AppLug service, menu loader, rate limiter, constants
│       ├── data_mgmt/      # Export/Import logic
│       ├── locales/        # Core translation JSON files (en, es)
│       ├── menus/          # Core menu metadata files (admin_menu.json, help_menu.json)
│       ├── metadata/       # Framework UI metadata
│       ├── static/         # Compiled JS, CSS
│       ├── templates/      # Jinja2 HTML templates
│       ├── main.py         # Application entry point; security headers middleware
│       ├── models.py       # Core ORM models (User, Role, Permission + indexes)
│       └── database.py     # Engine setup; pool config; session factory; init_db
└── tests/                  # Unit and integration tests
```

## 5. Component Architecture

### 5.1. AppLug Service (`core/applug_service.py`)
The framework's discovery and menu engine. It:
- Scans `plugins/` for `applug.json` manifests and dynamically imports entry classes.
- Auto-provisions roles and permissions from manifest declarations.
- Delegates `*_menu.json` loading to `MenuLoaderService`.
- Builds per-role menu caches at startup from the permissions database (`_build_role_menus`).

### 5.2. Menu Hub System
The navigation bar is divided into three zones:

| Zone | Content |
|---|---|
| Left | M logo → navigates to `/` |
| Centre | **Menu Selector** (structured dropdown) + **Hub Items** (active menu bar) |
| Right | User avatar with hover dropdown (Settings, Export, Import, Logout) |

**Menu Selector** ordering: Default → Favorites → Applications (one per AppLug) → Roles (one per role with menus). Hub items are click-to-toggle; the user zone retains CSS hover.

**Menu types** (`MenuType` enum): `Default`, `Application`, `Role`, `System`, `Favorites`.

**Default hub** shows one aggregated submenu per AppLug plus core menus; Help is always last. **Role hubs** are built from the permissions database at startup — every page a role can access appears as a hub item.

### 5.3. Menu Loader Service (`core/menu_loader.py`)
Standalone, cacheable service that discovers and loads `*_menu.json` files:
- **Core menus:** `src/matika/menus/` (admin_menu.json → Role type; help_menu.json → System type)
- **Plugin menus:** `plugins/<id>/<id>_menu.json`

### 5.4. Authentication & Security
- **Session:** Starlette `SessionMiddleware` with `SameSite=Lax` cookies. Idle timeout (configurable) and absolute 30-day cap.
- **CSRF:** Session-based token. `validate_csrf` FastAPI dependency on all authenticated POST routes. JavaScript (`csrf.ts`) auto-injects the token into form submissions.
- **Rate limiting:** In-process limiter on `/login` — 10 failures per 5 minutes triggers a 15-minute lockout per IP.
- **Security headers:** `SecurityHeadersMiddleware` adds `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`.
- **SECRET_KEY:** Required environment variable; app hard-fails on startup if absent.
- **File uploads:** 5 MB cap on photos (magic-byte verified); 10 MB cap on JSON imports.

### 5.5. Internationalization (`i18n.py`)
Merged-dictionary approach. Core strings are loaded first; active plugins contribute overrides. Plugin locale files live at `plugins/<id>/src/<id>/locales/<lang>.json`.

### 5.6. Maintenance Activity Pattern
Admin pages follow a standardized two-panel layout (`maintenance_activity_base.html`): Browse panel (left) + Maintenance panel (right).

## 6. Persistence Layer

### 6.1. ORM & Dialect Abstraction
All database access uses **SQLAlchemy ORM** — zero raw SQL in the codebase. Switching databases is a single environment variable change with no code modifications.

| Setting | Behaviour |
|---|---|
| `DATABASE_URL` starts with `sqlite` | `connect_args={"check_same_thread": False}` |
| Any other driver | Connection pool: `pool_size=10`, `max_overflow=20`, `pool_recycle=1800`, `pool_pre_ping=True` |

### 6.2. Migrations (Alembic)
Core schema is managed by Alembic (`migrations/`). Plugin schemas are managed by each plugin's `on_load()` → `create_all()` call.

```
alembic upgrade head        # apply all pending migrations
alembic current             # show current revision
alembic revision --autogenerate -m "description"  # generate from model changes
alembic downgrade -1        # roll back one revision
```

### 6.3. Performance Indexes
The `permissions` table is queried on **every authenticated request**. Five indexes ensure this is never a full-table scan:

| Index | Columns | Purpose |
|---|---|---|
| `ix_permissions_page_path` | `page_path` | Path lookup |
| `ix_permissions_role_id` | `role_id` | Role filter |
| `ix_permissions_user_id` | `user_id` | User filter |
| `ix_permissions_path_role` | `page_path`, `role_id` | Composite auth query |
| `ix_permissions_path_user` | `page_path`, `user_id` | Composite auth query |

### 6.4. Data Model
```
User ←→ Role (many-to-many via user_roles)
Role → Permission (one-to-many)
User → Permission (one-to-many, for user-specific overrides)
User → UserSetting (one-to-many)
SystemSetting (standalone key-value store)
```

Plugins extend this schema by creating their own tables in `on_load()`. EyeRate adds `securities`.

### 6.5. SQLite vs PostgreSQL

| Scenario | Recommendation |
|---|---|
| Single user / desktop install | SQLite (zero ops, included) |
| Development | SQLite |
| Multi-user / shared server | PostgreSQL |
| Docker / cloud | PostgreSQL |
| CI/CD tests | SQLite (fast, disposable) |

## 7. Scalability

Matika follows cloud-native principles for horizontal scaling when deployed against PostgreSQL:
- **Stateless API:** All session state is in the signed cookie. Multiple instances can run behind a load balancer without sticky sessions.
- **Static assets:** Can be served by Nginx or a CDN, decoupled from the app tier.
- **Connection pooling:** Automatically enabled for non-SQLite databases.
- **Profile photos:** Stored as database BLOBs — no persistent volume mounts required.

## 8. Plugin Development Contract

An AppLug must provide:
1. `applug.json` — manifest with `id`, `version`, `name`, (optional) `display_name`, `entry_point`, `permissions`
2. `<id>_menu.json` — menu metadata (schema v1.0)
3. A Python class extending `BaseAppLug` with `on_load(db)` and `on_unload(db)` methods

All POST routes contributed by a plugin must include `check_page_permission` and `validate_csrf` dependencies to participate in the core security model.
