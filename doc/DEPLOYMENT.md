**Matika** | Version: **0.0.1** | Copyright (c) 2026 Patrick James Tallman



# Matika Deployment & Installation Guide

This document provides detailed instructions for deploying Matika in different environments, ranging from local development setups to professional production distributions.

## 1. Deployment Model Overview
Matika is a monolithic application serving a **FastAPI** backend and a **TypeScript/Vanilla CSS** frontend.

### Key Components:
- **Backend:** Python 3.14+ utilizing FastAPI and SQLAlchemy.
- **Frontend:** TypeScript assets compiled into static JavaScript.
- **Database:** SQLite (default) for single-node simplicity.
- **Build System:** `Hatchling` for production-ready packaging and environment management.

---

## 2. Prerequisites
Regardless of the deployment method, ensure the following are installed:
- **Python 3.14+**
- **Node.js (v18+) & NPM** (Required for frontend compilation)
- **Git**
- **uv** (Recommended) or **pip** & **build** module

---

## 3. Method A: Local & Internal Server Deployment (`install.py`)

This method is ideal for development environments, internal testing servers, or simple local hosting. It automates the entire setup from a git clone.

### Detailed Steps:
1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/pjtallman/Matika.git
    cd Matika
    ```

2.  **Execute the Installer:**
    The unified `install.py` script detects your OS and performs all necessary configuration.
    ```bash
    # Mac/Linux:
    python3 install.py

    # Windows:
    python install.py
    ```

3.  **Process Automation Details:**
    The script performs the following sequential actions:
    - **Validation:** Checks for Git, Node, and NPM.
    - **Environment:** Creates a `.venv` folder and installs dependencies from `requirements.txt`.
    - **Frontend:** Executes `npm install` and `npm run build`. TypeScript is compiled to `src/matika/static/js/`.
    - **Testing:** Runs `pytest` with `PYTHONPATH` correctly set to the `src` directory.
    - **Database:** Initializes `matika.db` with default settings and roles.
    - **Launch:** Starts the server on `0.0.0.0:8000` to allow access from outside the server.

4.  **Verification:**
    Navigate to `http://<server-ip>:8000`. Detailed installation logs are available at `logs/install.log`.

---

## 4. Method B: Professional Production Build (`Hatchling`)

This is the standard for production deployment. It creates a clean **Source Distribution (sdist)** or **Wheel** that contains only the necessary code, explicitly excluding development artifacts like `scripts/`, `tests/`, and `milestone_tasks.yaml`.

### Step 1: Prepare the Frontend
Production builds should contain pre-compiled assets.
```bash
npm install
npm run build
```

### Step 2: Build the Package
Use `uv` (recommended) or the standard Python `build` tool to generate the distribution files.
```bash
# Using uv (fastest):
uv build

# OR using standard python build:
python3 -m pip install build
python3 -m build
```

### Step 3: Distribution Analysis
The build process generates a `dist/` folder containing:
- `matika-1.0.7.tar.gz` (Source Distribution)
- `matika-1.0.7-py3-none-any.whl` (Binary Wheel)

**Exclusion Verification:** Because we use `Hatchling` with the configurations in `pyproject.toml`, the following items are **excluded** from these files:
- `scripts/` folder (Release and Milestone scripts)
- `tests/` folder
- `milestone_tasks.yaml`
- `.pytest_cache/` and `__pycache__`

### Step 4: Install on Production Server
Copy the `.whl` or `.tar.gz` file to your production server and install it into a clean environment.
```bash
# Create and activate environment
python3 -m venv .venv
source .venv/bin/activate

# Install the built wheel
pip install matika-1.0.7-py3-none-any.whl
```

### Step 5: Run in Production
In a production environment, use `uvicorn` directly or a process manager like `systemd`.
```bash
# Set production variables
export SECRET_KEY="your-secure-random-key"
export DATABASE_URL="sqlite:///./data/production.db"

# Start the server
uvicorn matika.main:app --host 0.0.0.0 --port 8000
```

---

## 5. Production Hardening

### 1. Reverse Proxy (Nginx)
Never expose Uvicorn directly to the internet. Use Nginx as a reverse proxy to handle SSL (HTTPS) and static file caching.

### 2. Service Management (Systemd)
Create a service file at `/etc/systemd/system/matika.service`:
```ini
[Unit]
Description=Matika Yield Tracker
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/matika
Environment="PATH=/opt/matika/.venv/bin"
Environment="DATABASE_URL=sqlite:///./data/matika.db"
ExecStart=/opt/matika/.venv/bin/uvicorn matika.main:app --host 0.0.0.0 --port 8000

[Install]
WantedBy=multi-user.target
```

---

---

## 7. Method C: Distributed & High Availability Deployment

For large-scale or production-critical environments, Matika can be deployed in a distributed manner. This allows you to host the database on a separate server and run multiple instances of the Matika application behind a load balancer.

### 1. Separate Database Server
Instead of the default SQLite file, connect to a robust database like PostgreSQL:
1.  **Set Up PostgreSQL:** Install and configure PostgreSQL on a dedicated server. Create a database named `matika`.
2.  **Configure `DATABASE_URL`:** On each Matika app server, set the environment variable:
    ```bash
    export DATABASE_URL="postgresql://username:password@db-server-ip:5432/matika"
    ```
3.  **Drivers:** Ensure you install the appropriate database driver (e.g., `pip install psycopg2-binary`).

### 2. High Availability (Horizontal Scaling)
Deploy multiple application nodes to handle high traffic and provide redundancy:
- **Shared Session Key:** All nodes **must** share the same `SECRET_KEY` so that session cookies can be validated by any node.
- **Portability (BLOB Storage):** Matika stores profile photos as BLOBs in the database. This eliminates the need for shared network volumes (NFS/EFS) for user media, simplifying horizontal scaling.
- **Load Balancing:** Use Nginx or an AWS Application Load Balancer (ALB) to distribute traffic across your nodes.

---

## 7. Method D: Containerized Deployment (Docker Compose & Nginx)

For a professional-grade, easy-to-manage production environment, we use **Docker Compose** to orchestrate the FastAPI application and an **Nginx** reverse proxy.

### Why use Nginx?
- **SSL/TLS Termination:** Easily add HTTPS (e.g., via Let's Encrypt).
- **Security:** Adds essential security headers (HSTS, CSP, etc.).
- **Performance:** Serves static JS and CSS files much faster than Python.
- **Buffering:** Protects the FastAPI application from slow or malicious clients.

### Step 1: Prepare the environment
Ensure your local `src/matika/static/js` is built if you're not using the Docker multi-stage build directly.
```bash
npm run build
```

### Step 2: Configure Docker Compose
Review the `docker-compose.yml` file. It sets up two services:
1.  **`app`:** The FastAPI application running Uvicorn.
2.  **`nginx`:** The reverse proxy listening on port 80.

### Step 3: Run the stack
```bash
docker-compose up -d --build
```
The application will now be accessible at `http://localhost`.

---

## 9. Method E: Native Standalone Installers (User-Friendly)

This is the recommended way for non-technical users to install Matika on macOS or Windows.

For detailed, step-by-step instructions, please refer to the **`INSTALL_GUIDE.txt`** file included in the root of the project and inside every distribution package.

### Summary of steps:
1.  **Download** the installer for your OS from the Releases page:
    -   macOS (Intel or ARM64): `.dmg` file.
    -   Windows: `.exe` Setup file.
2.  **Run the Installer**:
    -   **macOS**: Open the DMG and drag Matika to your Applications folder.
    -   **Windows**: Run the setup wizard and follow the prompts to choose your installation directory.
3.  **Run Matika** (handling OS security prompts as described in `INSTALL_GUIDE.txt`).
4.  **Access** via `http://localhost:8000`.

---

## 10. Nginx Configuration Best Practices


Our `nginx/nginx.conf` is optimized for:
- **Gzip Compression:** Reduces the size of transmitted files (JSON, JS, CSS).
- **Cache Control:** Sets long-lived cache headers for static assets.
- **Security Headers:**
    - `X-Frame-Options: SAMEORIGIN`: Prevents clickjacking.
    - `X-Content-Type-Options: nosniff`: Prevents MIME-sniffing.
    - `Content-Security-Policy`: Restricts where assets can be loaded from.

---

## 9. Troubleshooting
- **Build Failures:** Ensure `npm run build` is successful before running `uv build`. Hatchling will package whatever is in the `static/js` folder.
- **Missing Dependencies:** If running via `uvicorn` directly, ensure all dependencies listed in `pyproject.toml` were installed during the `pip install <wheel>` step.
- **Permission Errors:** Ensure the user running the application has write access to the `data/` and `logs/` directories.
- **Nginx Gateway Timeout:** If the `app` container is still starting, Nginx might return a 502 or 504. Wait a few seconds and refresh.
