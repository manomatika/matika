**Matika** | Version: **1.0.7** | Copyright (c) 2026 Patrick James Tallman

# Matika Deployment & Installation Guide

Matika is designed for seamless deployment across various environments. Its plugin-agnostic nature requires a specific workflow for managing extensions (AppLugs).

## 1. Deployment Model
Matika operates as a central framework. In any given installation, the core remains identical, while the functionality is dictated by the contents of the `plugins/` directory.

### Repository Policy:
The `plugins/` directory in the Matika repository is **intentionally kept empty** (tracked via `.gitignore`). Plugins are considered external dependencies and are injected during the deployment/installation phase.

---

## 2. Production Installation (Manual)

### Step 1: Core Setup
1. **Clone Core:** `git clone https://github.com/pjtallman/Matika.git`
2. **Environment:**
   ```bash
   uv venv
   source .venv/bin/activate
   uv pip install -r requirements.txt
   ```
3. **Frontend Build:**
   ```bash
   npm install && npm run build
   ```

### Step 2: Plugin (AppLug) Deployment
Choose the plugins required for this specific deployment.
1. Navigate to the `plugins/` directory.
2. Clone or symlink the desired plugins:
   ```bash
   # Example: Installing EyeRate
   git clone https://github.com/pjtallman/eyerate.git eyerate
   ```
   *Note: On development machines, a symlink `ln -s ../../eyerate eyerate` is often preferred.*

### Step 3: Initialization
Start the server. Matika will:
1. Initialize the database (SQLite by default).
2. Scan the `plugins/` folder.
3. Auto-provision roles and permissions defined in `applug.json` for each plugin.
4. Mount plugin routes and merge localized strings.

---

## 3. Automated Deployment (Build System)

Using the included `scripts/release.py`:
1. The script automates versioning and GitHub release creation.
2. It generates a distribution wheel (`.whl`) for the core framework.
3. For a full deployment, the build pipeline should package the core wheel along with the specific set of plugin wheels or source folders.

---

## 4. Environment Configuration
- **DATABASE_URL:** Set this environment variable to use PostgreSQL or MySQL instead of SQLite.
- **SECRET_KEY:** Required for production session security.
- **GOOGLE_CLIENT_ID / GITHUB_CLIENT_ID:** Required if enabling Social OAuth.

## 5. Security Note (bcrypt)
Matika utilizes direct **bcrypt** hashing to maintain compatibility with Python 3.14+ and ensure maximum security for user credentials. Old installations using `passlib` based hashes may require a password reset or migration if upgrading to 1.0.7+.
