"""
launcher.py — PyInstaller entry point for the Matika frozen desktop app.

Responsibilities
----------------
1. First-run initialisation:
   - Generate a secure SECRET_KEY and write it to ~/matika/.env
   - Run alembic migrations IN-PROCESS via alembic.command.upgrade (NOT via
     subprocess / sys.executable — in a frozen bundle sys.executable IS the
     app binary; shelling out would re-enter main() and fork-bomb the process)
   - Extract bundled plugins to ~/matika/plugins/<name>/
   - Set MATIKA_PLUGINS_DIR so the app discovers the extracted plugins
   - Write a sentinel file (~/matika/.initialized) on success so init
     is skipped on every subsequent launch

2. Durable logging:
   - Configure file + stream logging to ~/matika/logs/matika-<date>.log as
     the FIRST action after ~/matika/ is created, so a Finder-launched crash
     always leaves a diagnosable log on disk.

3. Port-conflict detection:
   - Before starting uvicorn, probe port 8000.  If it is already in use,
     show a clear, user-facing error dialog and exit rather than crashing
     silently.

4. App launch:
   - Load environment from ~/matika/.env
   - Start uvicorn with the Matika ASGI app
   - Open the default browser after a short delay

Path helpers
------------
``_bundle_path(*parts)``  → absolute path inside sys._MEIPASS (frozen) or
                            the repo root (development)
``_data_dir()``           → ~/matika  (always writable; created if absent)
"""

from __future__ import annotations

import logging
import os
import secrets
import shutil
import socket
import sys
import threading
import webbrowser
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _bundle_path(*parts: str) -> str:
    """Return the absolute path to a file bundled inside the frozen app.

    In a frozen (PyInstaller) context, ``sys._MEIPASS`` is the unpacked
    bundle root.  In development, fall back to the directory that contains
    this file (the repo root).
    """
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS  # type: ignore[attr-defined]
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, *parts)


def _data_dir() -> Path:
    """Return (and create if necessary) the writable ~/matika directory."""
    d = Path.home() / "matika"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------

def _load_env(env_path: Path) -> None:
    """Load KEY=VALUE pairs from *env_path* into ``os.environ``."""
    if not env_path.exists():
        return
    with env_path.open() as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


# ---------------------------------------------------------------------------
# Logging setup (must run before first_run_init and before uvicorn)
# ---------------------------------------------------------------------------

def _setup_logging(data_dir: Path) -> None:
    """Configure file + stream logging to ~/matika/logs/matika-<date>.log.

    Called as the first action after ~/matika/ exists so that a Finder-
    launched crash always leaves a diagnosable log on disk — Finder discards
    stdout/stderr, making the log file the only durable diagnostic surface.

    Adds handlers directly to the root logger (does NOT use basicConfig) so
    the call is idempotent-safe across repeated calls in tests and always
    installs the file handler regardless of prior logging state.
    """
    log_dir = data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"matika-{date.today().isoformat()}.log"

    fmt = logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s")

    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(fmt)

    sh = logging.StreamHandler()
    sh.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(fh)
    root.addHandler(sh)

    logger.info("Matika starting — log: %s", log_path)


# ---------------------------------------------------------------------------
# First-run initialisation
# ---------------------------------------------------------------------------

def _generate_secret_key(env_path: Path) -> None:
    """Write a fresh SECRET_KEY to *env_path* (creates or appends)."""
    key = secrets.token_urlsafe(64)

    existing_lines: list[str] = []
    if env_path.exists():
        existing_lines = env_path.read_text().splitlines(keepends=True)

    # Replace an existing SECRET_KEY line or append a new one.
    new_lines: list[str] = []
    replaced = False
    for line in existing_lines:
        if line.startswith("SECRET_KEY="):
            new_lines.append(f"SECRET_KEY={key}\n")
            replaced = True
        else:
            new_lines.append(line)
    if not replaced:
        new_lines.append(f"SECRET_KEY={key}\n")

    env_path.write_text("".join(new_lines))
    os.environ["SECRET_KEY"] = key


def _run_alembic_upgrade(data_dir: Path) -> None:
    """Run alembic migrations IN-PROCESS to initialise the database schema.

    Uses alembic.command.upgrade rather than subprocess so that frozen
    PyInstaller bundles are safe: sys.executable inside a bundle IS the app
    binary, and shelling out with [sys.executable, "-m", "alembic", ...] would
    re-enter launcher.py::main(), trigger another first_run_init(), and spawn
    another subprocess — fork-bombing until EAGAIN kills the process tree.

    The database lives at ~/matika/data/matika.db.  DATABASE_URL is set in the
    process environment for the duration of the call because migrations/env.py
    reads it from os.environ (not from the AlembicConfig object); the previous
    value is restored on exit so subsequent code is not affected.
    """
    from alembic import command as alembic_command
    from alembic.config import Config as AlembicConfig

    db_path = data_dir / "data" / "matika.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    database_url = f"sqlite:///{db_path}"

    alembic_ini = _bundle_path("alembic.ini")
    logger.info("Running alembic upgrade head — database: %s", db_path)
    cfg = AlembicConfig(alembic_ini)
    cfg.set_main_option("sqlalchemy.url", database_url)

    # migrations/env.py reads DATABASE_URL from the environment; set it for
    # the duration of the upgrade call and restore the previous value after.
    _prev_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    try:
        alembic_command.upgrade(cfg, "head")
    finally:
        if _prev_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = _prev_url
    logger.info("alembic upgrade head complete")


def _extract_bundled_plugins(data_dir: Path) -> None:
    """Copy plugins bundled inside the frozen app to ~/matika/plugins/.

    Plugins are bundled under ``<bundle>/plugins/`` (see matika.spec).
    Each immediate subdirectory is a plugin; it is copied to
    ``~/matika/plugins/<name>/`` if not already present so that user
    modifications made after first run are preserved.
    """
    bundle_plugins = Path(_bundle_path("plugins"))
    if not bundle_plugins.is_dir():
        # No plugins were bundled — nothing to do.
        return

    plugins_dir = data_dir / "plugins"
    plugins_dir.mkdir(parents=True, exist_ok=True)

    for plugin_src in bundle_plugins.iterdir():
        if not plugin_src.is_dir():
            continue
        plugin_dest = plugins_dir / plugin_src.name
        if not plugin_dest.exists():
            shutil.copytree(str(plugin_src), str(plugin_dest))


def first_run_init(data_dir: Path) -> None:
    """Perform all one-time first-run initialisation steps.

    Steps:
    1. Generate SECRET_KEY → ~/matika/.env
    2. Run alembic upgrade head (in-process, not via subprocess)
    3. Extract bundled plugins → ~/matika/plugins/
    4. Write sentinel file ~/matika/.initialized

    Raises ``RuntimeError`` if any step fails; the sentinel is only written
    after all steps succeed so a partial init is retried on next launch.
    """
    logger.info("First-run init starting")
    env_path = data_dir / ".env"
    _generate_secret_key(env_path)
    logger.info("SECRET_KEY generated → %s", env_path)

    _run_alembic_upgrade(data_dir)

    _extract_bundled_plugins(data_dir)
    logger.info("Plugin extraction complete")

    # Mark initialisation complete.
    (data_dir / ".initialized").touch()
    logger.info("First-run init complete — sentinel written")


# ---------------------------------------------------------------------------
# Port-conflict detection
# ---------------------------------------------------------------------------

def _port_in_use(port: int) -> bool:
    """Return True if *port* is already bound on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        try:
            s.connect(("127.0.0.1", port))
            return True
        except (ConnectionRefusedError, OSError):
            return False


def _show_port_error(port: int) -> None:
    """Display a user-friendly error when the port is already in use."""
    message = (
        f"Matika cannot start because port {port} is already in use.\n\n"
        f"Another application is listening on port {port}.  Please either:\n"
        f"  • Close the application that is using port {port}, or\n"
        f"  • Restart your computer and try again."
    )
    # Try a native dialog; fall back to console if not available.
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Matika — Port Conflict", message)
        root.destroy()
    except Exception:
        print(f"ERROR: {message}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Initialise and launch the Matika app."""
    port = 8000
    data_dir = _data_dir()

    # Logging must be first so every subsequent step — including failures —
    # is captured in ~/matika/logs/matika-<date>.log.  Finder discards stderr,
    # making the log file the only durable diagnostic surface on failed launch.
    _setup_logging(data_dir)

    sentinel = data_dir / ".initialized"
    env_path = data_dir / ".env"

    # --- First-run init -------------------------------------------------------
    if not sentinel.exists():
        try:
            first_run_init(data_dir)
        except Exception as exc:  # pragma: no cover
            logging.exception("first-run setup failed")
            msg = f"Matika first-run setup failed:\n\n{exc}\n\nMatika cannot start."
            try:
                import tkinter as tk
                from tkinter import messagebox

                root = tk.Tk()
                root.withdraw()
                messagebox.showerror("Matika — Setup Error", msg)
                root.destroy()
            except Exception:
                print(f"ERROR: {msg}", file=sys.stderr)
            sys.exit(1)

    # --- Load environment -----------------------------------------------------
    _load_env(env_path)

    # Set MATIKA_PLUGINS_DIR so AppLugService discovers the extracted plugins.
    plugins_dir = data_dir / "plugins"
    if plugins_dir.is_dir():
        os.environ.setdefault("MATIKA_PLUGINS_DIR", str(plugins_dir))

    # Ensure PYTHONPATH includes the bundled src/ directory.
    bundled_src = _bundle_path("src")
    current_pythonpath = os.environ.get("PYTHONPATH", "")
    if bundled_src not in current_pythonpath.split(os.pathsep):
        os.environ["PYTHONPATH"] = (
            bundled_src + os.pathsep + current_pythonpath
            if current_pythonpath
            else bundled_src
        )

    # --- Port conflict check --------------------------------------------------
    if _port_in_use(port):
        _show_port_error(port)
        sys.exit(1)

    # --- Launch ---------------------------------------------------------------
    logger.info("Starting uvicorn on http://127.0.0.1:%s", port)

    def _open_browser() -> None:
        webbrowser.open(f"http://127.0.0.1:{port}")

    threading.Timer(1.5, _open_browser).start()

    import uvicorn

    uvicorn.run(
        "matika.main:app",
        host="127.0.0.1",
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
