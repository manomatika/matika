**Matika** | Version: **v0.0.4** | Copyright (c) 2026 Patrick James Tallman


# Matika Installation Guide

---

## 1. End User Installation

Matika-based applications are distributed as standalone installers by the
application vendor. No Python, Node.js, or technical knowledge is required.

### macOS
1. Download the `.dmg` file provided by your application vendor.
2. Open the `.dmg` and drag the application icon to your **Applications** folder.
3. Launch the application from Applications.
4. On first launch, the application initialises automatically. This may take a few seconds.
5. If macOS shows a security warning, go to **System Settings → Privacy & Security → Open Anyway**.

### Windows
1. Download the `.exe` installer provided by your application vendor.
2. Run the installer and follow the prompts.
3. Launch from the **Start Menu** or **Desktop** shortcut.
4. The application initialises automatically on first launch.

> **Note:** Standalone installers are planned for a future release. If you are
> a developer, see Section 2.

---

## 2. Manual Installation (Developers)

> **Note:** This section is for developers of Matika or Matika AppLugs.
> End users should use the installer from their application vendor.

### Prerequisites
- Python 3.14+
- Node.js 18+
- `uv` (recommended: `pip install uv`)

### Step-by-Step

```bash
# 1. Clone
git clone https://github.com/manomatika/matika.git
cd matika

# 2. Virtual environment
uv venv
source .venv/bin/activate        # macOS/Linux
.venv\Scripts\activate           # Windows

# 3. Python dependencies
uv pip install -r requirements.txt

# 4. Frontend build
npm install
npm run build

# 5. Environment — SECRET_KEY is required; the app refuses to start without it
cp .env.example .env
# Edit .env and set SECRET_KEY to the output of:
python3 -c "import secrets; print(secrets.token_urlsafe(64))"

# 6. Apply database migrations
export $(cat .env | xargs)
PYTHONPATH=src alembic upgrade head

# 7. Plugin setup (one-time per machine)
cp plugins.dev.json.example plugins.dev.json
# Edit plugins.dev.json to point at your local plugin repos, then run:
python scripts/dev_setup.py

# 8. Start server
PYTHONPATH=src uvicorn matika.main:app --host 127.0.0.1 --port 8000 --reload
```

Open **http://127.0.0.1:8000** in your browser.

### Initial Admin Credentials
- **Username:** `admin`
- **Password:** `adminpassword`

> ⚠️ **WARNING:** Default credentials are publicly known. Matika enforces a
> password change on first login. Do not expose the server to a network before
> completing first-login setup.

---

## 3. PostgreSQL Setup (Multi-User / Production)

By default Matika uses SQLite. To switch to PostgreSQL:

```bash
# Add to .env:
DATABASE_URL=postgresql://user:password@host:5432/matika_db

# Apply migrations against PostgreSQL:
PYTHONPATH=src alembic upgrade head
```

No code changes are needed — the ORM dialect switches automatically.

---

## 4. Database Migrations

Matika uses **Alembic** for versioned schema migrations. Always run this after pulling updates that include model changes:

```bash
PYTHONPATH=src alembic upgrade head
```

To check what revision the database is at:
```bash
PYTHONPATH=src alembic current
```

---

## 5. Troubleshooting

| Symptom | Fix |
|---|---|
| `CRITICAL: SECRET_KEY environment variable is not set` | Copy `.env.example` to `.env` and generate a key |
| `ModuleNotFoundError` | Ensure `PYTHONPATH` includes `src/` |
| Port 8000 already in use | `pkill -f "uvicorn matika"` |
| `bcrypt` errors | Verify Python 3.14+ and latest `bcrypt` package |
| `alembic.util.exc.CommandError: Can't locate revision` | Run `alembic stamp base` then `alembic upgrade head` on a fresh DB |
| Plugin not loading | Run `python scripts/dev_setup.py` to verify symlinks |
