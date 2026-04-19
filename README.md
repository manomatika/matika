**Matika** | Version: **1.0.7** | Copyright (c) 2026 Patrick James Tallman

# Matika - Dynamic AppLug Framework

Matika is a high-performance, plugin-agnostic framework built with **FastAPI** and **TypeScript**. It is designed to be a core foundation that can be extended dynamically via "AppLugs" (plugins) without the core framework having any prior knowledge of the extensions.

## Core Features

- **Dynamic Plugin Discovery:** Automatically discovers and loads plugins (AppLugs) from the `plugins/` directory at runtime.
- **Unified Security Model:** Centralized Role-Based Access Control (RBAC) that plugins can hook into for permissions.
- **Aggregated UI:** Automatically merges plugin menu items and templates into a seamless dashboard experience.
- **Robust Authentication:** Secure user management with direct **bcrypt** hashing (optimized for Python 3.14+).
- **Internationalization:** Built-in i18n support that allows plugins to contribute their own localized strings.
- **Data Management:** Integrated system and user data export/import capabilities.

## Architecture

Matika follows a "no-knowledge" architectural principle. The core repository is kept clean of specific domain logic, which is instead encapsulated within plugins.

- **Backend:** FastAPI (Python)
- **Database:** SQLAlchemy with SQLite (default) or PostgreSQL/MySQL support.
- **Frontend:** TypeScript with Vanilla CSS (compiled to static JS).
- **Extensibility:** `AppLugService` handles manifest (`applug.json`) parsing, route registration, and entity provisioning.

## Getting Started

### Prerequisites
- Python 3.14+
- Node.js & NPM
- `uv` (recommended)

### Installation
1. **Setup Environment:**
   ```bash
   uv venv
   source .venv/bin/activate
   uv pip install -r requirements.txt
   ```
2. **Compile Frontend:**
   ```bash
   npm install
   npm run build
   ```
3. **Run Application:**
   ```bash
   export PYTHONPATH=$PYTHONPATH:$(pwd)/src
   python src/matika/main.py
   ```

## Plugin Development

Matika looks for plugins in the `plugins/` folder. A standard plugin consists of:
- `applug.json`: Manifest defining ID, version, and entry point.
- `src/`: Plugin source code.
- `eyerate_menu.json` (example): Menu contribution definitions.

See the [EyeRate](https://github.com/pjtallman/eyerate) repository for a reference implementation.

## Documentation
- [Installation Guide](doc/INSTALL.md)
- [Deployment Guide](doc/DEPLOYMENT.md)
- [Architecture Overview](doc/ARCHITECTURE.md)

## License
Copyright (c) 2026 Patrick James Tallman. All Rights Reserved.
