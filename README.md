**Matika** | Version: **v0.0.1** | Copyright (c) 2026 Patrick James Tallman




# Matika

Matika is a high-performance yield tracking and security maintenance application built with FastAPI and TypeScript.

## Quick Start

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/pjtallman/matika.git
    cd matika
    ```

2.  **Automated Installation:**
    Matika provides a unified installer that handles environment setup, frontend building, and validation.
    ```bash
    # Mac/Linux:
    python3 install.py

    # Windows:
    python install.py
    ```

3.  **Access the Application:**
    Once the installer finishes, open your browser and navigate to:
    `http://localhost:8000`

## Documentation

For more detailed information, please refer to the following guides:

- [Technical Architecture & Design](doc/ARCHITECTURE.md) - Deep dive into the stack, folder structure, and data model.
- [Deployment & Installation Guide](doc/DEPLOYMENT.md) - Detailed instructions for automated and manual setups on different OS.
- [Automation Scripts](scripts/README.md) - Documentation for development lifecycle scripts (milestones, releases).

## Features

- **Real-time Security Tracking:** Lookup and maintain security data (ETFs, Stocks, Mutual Funds).
- **Advanced Permissions:** Granular RBAC for pages and subjects (users/roles).
- **Data Mobility:** Export and import system and user data for backup or migration.
- **Internationalization:** Multi-language support (English, Spanish) with dynamic translation.
- **Maintenance Activity Pattern:** Consistent UI for administrative and data-entry tasks.

## Folder Structure

The Matika project follows a modular "src layout" to separate source code, configuration, and data.

```text
/
├── data/                   # Persistent storage (SQLite .db files and backups)
├── doc/                    # Project documentation
│   ├── ARCHITECTURE.md     # Technical design and data model
│   ├── COPYRIGHT.txt       # Legal and licensing information
│   ├── DEPLOYMENT.md       # Production setup and scaling guide
│   ├── INSTALL.md          # Basic installation instructions
│   └── INSTALL_GUIDE.txt   # Detailed step-by-step setup guide
├── logs/                   # Application, startup, and test log files
├── nginx/                  # Nginx configuration for reverse proxy setups
├── scripts/                # Automation and utility scripts
│   ├── build_standalone.py # Script to build standalone executables
│   ├── install.py          # Unified installer and environment setup
│   ├── launcher.py         # Entry point for standalone application
│   ├── matika.spec         # PyInstaller specification for standalone builds
│   ├── milestone_tasks.yaml # Task definitions for development milestones
│   ├── release.py          # Release automation script
│   ├── start_milestone.py  # Script to initialize a new milestone
│   └── sync_version.py     # Utility to synchronize versions across files
├── src/                    # Source code root
│   ├── frontend/           # TypeScript source files (compiled to static/js)
│   └── matika/             # Main Python package
│       ├── auth/           # Authentication services and dependencies
│       ├── core/           # Core utilities: logging, paths, and shared helpers
│       ├── data_mgmt/      # Data export, import, and migration logic
│       ├── deployment/     # Environment and deployment health checkers
│       ├── locales/        # Translation JSON files (en.json, es.json)
│       ├── metadata/       # Activity-specific UI and layout metadata
│       ├── routers/        # FastAPI route definitions (admin, public, settings)
│       ├── security/       # Authorization and RBAC services
│       ├── static/         # Compiled JS, CSS, and user-uploaded assets
│       ├── templates/      # Jinja2 HTML templates
│       ├── database.py     # SQLAlchemy models and session management
│       ├── i18n.py         # Internationalization and translation logic
│       └── main.py         # Application entry point and app initialization
└── tests/                  # Unit and integration test suite (pytest)
```
