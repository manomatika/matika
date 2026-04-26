**Matika** | Version: **0.0.2_dev** | Copyright (c) 2026 Patrick James Tallman

# Matika Installation Guide

## 1. Standalone Installation (Recommended for End Users)

### macOS (.dmg)
1. Download the latest `matika-macos.dmg` from the Releases page.
2. Drag the Matika icon to `Applications`.
3. On first launch, if macOS shows a security warning go to **System Settings → Privacy & Security → Open Anyway**.

### Windows (.exe)
1. Download the latest `matika-setup.exe`.
2. Run the installer and follow the prompts.
3. Use the Desktop shortcut to start.

---

## 2. Manual Installation (Developers)

### Prerequisites
- Python 3.14+
- Node.js 18+
- `uv` (recommended: `pip install uv`)

### Step-by-Step

```bash
# 1. Clone
git clone https://github.com/pjtallman/Matika.git
cd Matika

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

# 7. Start server
PYTHONPATH=src uvicorn matika.main:app --host 127.0.0.1 --port 8000 --reload
```

Open **http://127.0.0.1:8000** in your browser.

### Initial Admin Credentials
- **Username:** `admin`
- **Password:** `adminpassword`

You will be prompted to change this password on first login.

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

## 4. Plugin (AppLug) Installation

```bash
cd plugins/

# Clone a plugin
git clone https://github.com/pjtallman/eyerate.git eyerate

# Or symlink for development (when repos are siblings)
ln -sf ../../eyerate eyerate
```

Restart the server. Matika auto-discovers plugins, seeds their permissions, and adds their menus.

---

## 5. Database Migrations

Matika uses **Alembic** for versioned schema migrations. Always run this after pulling updates that include model changes:

```bash
PYTHONPATH=src alembic upgrade head
```

To check what revision the database is at:
```bash
PYTHONPATH=src alembic current
```

---

## 6. Troubleshooting

| Symptom | Fix |
|---|---|
| `CRITICAL: SECRET_KEY environment variable is not set` | Copy `.env.example` to `.env` and generate a key |
| `ModuleNotFoundError` | Ensure `PYTHONPATH` includes `src/` |
| Port 8000 already in use | `pkill -f "uvicorn matika"` |
| `bcrypt` errors | Verify Python 3.14+ and latest `bcrypt` package |
| `alembic.util.exc.CommandError: Can't locate revision` | Run `alembic stamp base` then `alembic upgrade head` on a fresh DB |
