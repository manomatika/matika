**Matika** | Version: **v0.0.1** | Copyright (c) 2026 Patrick James Tallman


# Matika Technical Architecture & Design

## 1. Executive Summary
Matika is a high-performance yield tracking and security maintenance application built with a modern, layered architecture. It provides real-time security data lookups, bulk operations, and localized administrative controls.

## 2. Technology Stack
- **Backend:** [FastAPI](https://fastapi.tiangolo.com/) (Python 3.14+)
- **Database:** [SQLite](https://sqlite.org/) with [SQLAlchemy](https://www.sqlalchemy.org/) ORM
- **Frontend:** [Jinja2](https://palletsprojects.com/p/jinja/) Templates, [TypeScript](https://www.typescriptlang.org/) (ESNext), Vanilla CSS
- **Tooling:** `uv` for Python management, `npm` for TypeScript compilation, `pytest` for unit testing

## 3. Folder Structure (Best Practices)
The project follows a standard "src layout" to ensure clear separation between source code, tests, and data.

```
/
├── .gitignore              # Git ignore rules
├── README.md               # Basic project info and quick start
├── VERSION                 # Current application version
├── package.json            # Node.js dependencies and build scripts
├── tsconfig.json           # TypeScript configuration
├── pyproject.toml          # Python project configuration
├── pytest.ini              # Test configuration
├── data/                   # Persistent storage (SQLite .db files)
├── doc/                    # Technical documentation
├── plugins/                # Extensible "AppLug" plugins (runtime populated)
├── scripts/                # Dev/Ops automation scripts
├── src/                    # Source code root
│   ├── frontend/           # TypeScript source files
│   └── matika/            # Main Python package
│       ├── main.py         # Application entry point and app factory
│       ├── database.py     # Database engine and initialization
│       ├── models.py       # SQLAlchemy data models
│       ├── i18n.py         # Internationalization service
│       ├── auth/           # Authentication logic and dependencies
│       ├── core/           # Core utilities, paths, and constants
│       ├── data_mgmt/      # Export/Import and data migration
│       ├── locales/        # Translation JSON files
│       ├── routers/        # FastAPI route modules
│       ├── security/       # RBAC and permission services
│       ├── static/         # Compiled JS, CSS, and assets
│       └── templates/      # HTML templates (Jinja2)
└── tests/                  # Unit and integration tests
```

## 4. Component Architecture

### 4.1. AppLug Plugin System
Matika is designed to be extensible through a plugin architecture called "AppLugs".
- **Decoupling:** The core Matika engine has no hardcoded knowledge of specific plugins.
- **Discovery:** On startup, `AppLugService` scans the `plugins/` directory for `applug.json` manifests.
- **Registration:** Plugins can register their own:
    - FastAPI Routers
    - SQLAlchemy Models (auto-migrated)
    - Menu Items (injected into the global navigation)
    - Default Roles and Permissions
    - Localized strings (merged with core translations)

### 4.2. Maintenance Activity Pattern
Administrative pages follow a standardized pattern for consistency and rapid development.
- **`maintenance_activity_base.html`:** Implements a two-vertical-panel layout (Browse vs. Maintenance).
- **`MaintenanceActivityManager` (TS):** Base class for handling CRUD lifecycle events via AJAX.

## 5. Security & Authentication

### 5.1. Session Management
- **Persistence:** Sessions use signed cookies via Starlette's `SessionMiddleware`.
- **Inactivity Timeout:** Managed internally via a `last_activity` timestamp in the session. Configurable via System Settings.
- **Remember Me:** Persistent cookie support for long-lived sessions.

### 5.2. RBAC (Role-Based Access Control)
Matika uses a granular permission system:
- **Page-Level:** Permissions are tied to specific URL paths.
- **Inheritance:** Child paths automatically inherit permissions from their parent (e.g., `/admin/users/create` inherits from `/admin/users`).
- **Levels:** Permissions range from `NONE` to `FULL` (Create, Update, Delete, Read).

## 6. Scalability & Distributed Architecture
(Same as before...)

## 7. Data Model
(Same as before, now referencing models.py...)
