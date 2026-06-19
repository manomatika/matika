"""
launcher.py — Matika standalone app launcher.

Handles first-run initialization, port conflict detection, server startup,
and browser open. Works in both frozen (PyInstaller) and dev modes.

First-run initialization (frozen mode only, gated by ~/matika/.initialized):
  1. Generate SECRET_KEY → ~/matika/.env (permissions 0600)
  2. Extract bundled plugins from sys._MEIPASS/plugins/ → ~/matika/plugins/
  3. Run alembic upgrade head (via Python API, works in frozen mode)
  4. Write sentinel ~/matika/.initialized only after all steps succeed

Port conflict: shows a native OS dialog and exits 1 if port 8000 is in use.

Browser open: polls until the server accepts connections (3 s, 100 ms intervals)
rather than using a fixed sleep.
"""

import multiprocessing
import os
import secrets
import shutil
import socket
import stat
import sys
import time
import traceback
import webbrowser
from pathlib import Path
from threading import Thread


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
HOME_DIR             = Path.home()
APP_DIR              = HOME_DIR / "matika"
LOG_FILE             = APP_DIR / "launcher.log"
ENV_FILE             = APP_DIR / ".env"
PLUGINS_INSTALL_DIR  = APP_DIR / "plugins"
SENTINEL             = APP_DIR / ".initialized"

HOST = "127.0.0.1"
PORT = 8000


# ---------------------------------------------------------------------------
# Logging — writes to ~/matika/launcher.log; also prints in dev mode
# ---------------------------------------------------------------------------
_log_fh = None


def _open_log() -> None:
    global _log_fh
    APP_DIR.mkdir(parents=True, exist_ok=True)
    _log_fh = open(LOG_FILE, "a", buffering=1)


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    if _log_fh:
        try:
            _log_fh.write(line + "\n")
        except Exception:
            pass
    # Dev mode: also echo to real stderr so the developer sees it
    if not getattr(sys, "frozen", False):
        print(line, file=sys.stderr)


# ---------------------------------------------------------------------------
# Native error dialog
# ---------------------------------------------------------------------------
def show_error(msg: str) -> None:
    """Display a native OS error dialog. Always logs; dialog failure is silent."""
    log(f"CRITICAL: {msg}")
    try:
        if sys.platform == "darwin":
            # osascript is always available on macOS; no extra dependency
            safe = msg.replace("\\", "\\\\").replace('"', '\\"')
            os.system(
                f'osascript -e \'display alert "ManoMatika Error" message "{safe}" buttons {{"OK"}}\''
            )
        elif sys.platform == "win32":
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, msg, "ManoMatika Error", 0x10)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Port check
# ---------------------------------------------------------------------------
def _port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def check_port() -> None:
    """Exit with a user-facing dialog if port 8000 is already in use."""
    if not _port_available(HOST, PORT):
        show_error(
            f"ManoMatika cannot start: port {PORT} is already in use.\n"
            "Please close the conflicting application and try again."
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# Base path resolution
# ---------------------------------------------------------------------------
def get_base_path() -> Path:
    """Return sys._MEIPASS in frozen mode, repo root in dev mode."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    # Dev: this file is at scripts/launcher.py; repo root is one level up
    return Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Environment loading (production only)
# ---------------------------------------------------------------------------
def load_env() -> None:
    """Load ~/matika/.env into os.environ. Only runs in frozen mode.

    In dev mode the developer manages their own .env via the standard
    workflow (cp .env.example .env; export $(cat .env | ...)).
    """
    if not getattr(sys, "frozen", False):
        return
    if not ENV_FILE.exists():
        return
    for raw_line in ENV_FILE.read_text().splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())
    log(f"Loaded environment from {ENV_FILE}")


# ---------------------------------------------------------------------------
# Plugin path wiring (production only)
# ---------------------------------------------------------------------------
def setup_plugin_paths() -> None:
    """Set MATIKA_PLUGINS_DIR and insert plugin src/ dirs into sys.path.

    Only runs in frozen mode. In dev mode, MATIKA_PLUGINS_DIR is set by the
    developer via plugins.dev.json + dev_setup.py (see CLAUDE.md).
    """
    if not getattr(sys, "frozen", False):
        return
    if not PLUGINS_INSTALL_DIR.exists():
        return
    os.environ["MATIKA_PLUGINS_DIR"] = str(PLUGINS_INSTALL_DIR)
    for plugin_dir in sorted(PLUGINS_INSTALL_DIR.iterdir()):
        if not plugin_dir.is_dir():
            continue
        src = plugin_dir / "src"
        if src.is_dir() and str(src) not in sys.path:
            sys.path.insert(0, str(src))
    log(f"MATIKA_PLUGINS_DIR → {PLUGINS_INSTALL_DIR}")


# ---------------------------------------------------------------------------
# First-run initialization steps
# ---------------------------------------------------------------------------
def _generate_secret_key() -> None:
    """Write a fresh SECRET_KEY to ~/matika/.env with 0600 permissions."""
    key = secrets.token_urlsafe(64)
    ENV_FILE.write_text(f"SECRET_KEY={key}\n")
    ENV_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)  # owner read/write only
    log(f"SECRET_KEY generated → {ENV_FILE}")


def _extract_plugins(base_path: Path) -> None:
    """Copy bundled plugins from the app bundle to ~/matika/plugins/.

    Uses shutil.copytree (never symlinks) because the bundle is read-only
    after code signing (M5). Copies are writable and inspectable.
    """
    bundle_plugins = base_path / "plugins"
    if not bundle_plugins.exists():
        log("No plugins in bundle — skipping extraction")
        return

    PLUGINS_INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    for plugin_src in sorted(bundle_plugins.iterdir()):
        if not plugin_src.is_dir():
            continue
        name = plugin_src.name
        dest = PLUGINS_INSTALL_DIR / name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(plugin_src, dest)
        log(f"Extracted plugin: {name} → {dest}")


def _run_migrations(base_path: Path) -> None:
    """Run alembic upgrade head via the Python API.

    Using the Python API (not subprocess) because sys.executable in a frozen
    app is the launcher binary, not a Python interpreter — subprocess with
    '-m alembic' would not work.
    """
    from alembic import command as alembic_command
    from alembic.config import Config as AlembicConfig

    if getattr(sys, "frozen", False):
        alembic_ini = base_path / "alembic.ini"
        migrations_dir = base_path / "migrations"
    else:
        repo_root = Path(__file__).resolve().parent.parent
        alembic_ini = repo_root / "alembic.ini"
        migrations_dir = repo_root / "migrations"

    if not alembic_ini.exists():
        raise FileNotFoundError(f"alembic.ini not found: {alembic_ini}")

    cfg = AlembicConfig(str(alembic_ini))
    cfg.set_main_option("script_location", str(migrations_dir))
    alembic_command.upgrade(cfg, "head")
    log("alembic upgrade head: OK")


def first_run_init(base_path: Path) -> None:
    """Full first-run initialization, gated by the sentinel file.

    Frozen mode only. Dev mode skips entirely — developers manage their
    environment manually per the CLAUDE.md workflow.

    The sentinel ~/matika/.initialized is written ONLY after every step
    succeeds. A half-initialized state (e.g. crash during migration) leaves
    no sentinel, so the next launch retries from the beginning.
    """
    if not getattr(sys, "frozen", False):
        log("Dev mode — skipping first-run init (manage env manually)")
        return

    if SENTINEL.exists():
        log("Sentinel present — skipping first-run init")
        return

    log("First run — beginning initialization sequence")
    _generate_secret_key()
    # Reload env so SECRET_KEY is visible to alembic's env.py
    load_env()
    _extract_plugins(base_path)
    # Wire plugin paths before migrations in case migrations use plugin code
    setup_plugin_paths()
    _run_migrations(base_path)

    SENTINEL.touch()
    log("First-run init complete — sentinel written")


# ---------------------------------------------------------------------------
# Browser open (poll-based)
# ---------------------------------------------------------------------------
def _open_browser_when_ready(
    host: str,
    port: int,
    timeout: float = 3.0,
    interval: float = 0.1,
) -> None:
    """Poll until the server accepts connections, then open the browser."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=interval):
                webbrowser.open(f"http://{host}:{port}")
                log("Browser opened")
                return
        except OSError:
            time.sleep(interval)
    log("WARNING: server did not respond within timeout — browser not opened")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    multiprocessing.freeze_support()

    _open_log()
    log("=== Matika Launcher Starting ===")
    log(f"platform={sys.platform}  frozen={getattr(sys, 'frozen', False)}")

    try:
        base_path = get_base_path()
        log(f"base_path={base_path}")

        # Load env before any matika imports so SECRET_KEY is visible
        load_env()

        # Add matika's src/ to sys.path in dev mode
        if not getattr(sys, "frozen", False):
            _dev_src = base_path / "src"
            if _dev_src.is_dir() and str(_dev_src) not in sys.path:
                sys.path.insert(0, str(_dev_src))

        # Ensure ~/matika/data/ exists (database lives here)
        (APP_DIR / "data").mkdir(parents=True, exist_ok=True)

        # First-run init (frozen only, sentinel-gated)
        first_run_init(base_path)

        # Wire plugin paths for every run in frozen mode
        setup_plugin_paths()

        # Port check before importing matika (fast fail before heavy import)
        check_port()

        # Import application after env and paths are set
        from matika.main import app  # noqa: E402
        import uvicorn               # noqa: E402

        # Open browser in background after server is accepting connections
        is_testing = bool(os.environ.get("PYTEST_CURRENT_TEST"))
        if not is_testing:
            Thread(
                target=_open_browser_when_ready,
                args=(HOST, PORT),
                daemon=True,
            ).start()

        log(f"Starting uvicorn on {HOST}:{PORT}")
        uvicorn.run(app, host=HOST, port=PORT, log_level="info", access_log=True)

    except Exception as exc:
        tb = traceback.format_exc()
        log(f"FATAL: {exc}\n{tb}")
        show_error(f"Failed to start ManoMatika:\n{exc}")
        sys.exit(1)
