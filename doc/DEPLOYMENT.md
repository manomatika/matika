**Matika** | Version: **1.0.7** | Copyright (c) 2026 Patrick James Tallman. All Rights Reserved.

# Matika Deployment & Installation Guide

This document provides detailed instructions for deploying Matika in different environments, ranging from local development setups to professional production distributions.

## 1. Deployment Model Overview
Matika is a monolithic application serving a **FastAPI** backend and a **TypeScript/Vanilla CSS** frontend. It is designed to be extensible via the **AppLug** plugin system.

### Key Components:
- **Backend:** Python 3.14+ utilizing FastAPI and SQLAlchemy.
- **Frontend:** TypeScript assets compiled into static JavaScript.
- **Plugins:** Dynamic "AppLugs" loaded from the `plugins/` directory.
- **Database:** SQLite (default) for single-node simplicity.

---

## 2. Prerequisites
Ensure the following are installed:
- **Python 3.14+**
- **Node.js (v18+) & NPM** (Required for frontend compilation)
- **Git**
- **uv** (Recommended) or **pip**

---

## 3. Installation Methods

### Method A: Local/Development Setup
Ideal for development environments or internal testing.
1.  **Clone:** `git clone https://github.com/pjtallman/Matika.git`
2.  **Install:** Run `python3 install.py`.
3.  **Plugins:** See Section 4 for populating plugins.
4.  **Reference:** See [INSTALL.md](INSTALL.md) for detailed OS-specific instructions.

### Method B: Professional Production Build (Hatchling)
Creates a clean distribution wheel.
1.  **Frontend:** `npm install && npm run build`
2.  **Build:** `uv build` or `python3 -m build`
3.  **Install:** `pip install dist/matika-1.0.7-py3-none-any.whl`

---

## 4. Plugin Management (AppLugs)
Matika does not come with plugins pre-installed. The `plugins/` directory is created automatically on first run.

### To Install a Plugin:
1.  Navigate to your Matika installation directory.
2.  Locate the `plugins/` folder.
3.  Clone or copy the plugin repository into a subdirectory here.
    *   Example: `plugins/eyerate/`
4.  Restart the Matika server.
5.  Matika will automatically detect the plugin manifest (`applug.json`) and register its routes, models, and menu items.

---

## 5. Production Hardening
(Same as before: Nginx, Systemd, HA Scaling...)

---

## 6. Native Standalone Installers
For non-technical users on macOS or Windows.
1.  Download the `.dmg` (macOS) or `.exe` (Windows) from the Releases page.
2.  Follow the instructions in the included [INSTALL.md](INSTALL.md).
3.  Place any desired plugins in the `plugins/` folder created in the application's data directory.
