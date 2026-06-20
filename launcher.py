"""
launcher.py — PyInstaller entry point for the Matika frozen desktop app.

Responsibilities
----------------
1. First-run initialisation:
   - Generate a secure SECRET_KEY and write it to ~/matika/.env
   - Create the DB schema from the SQLAlchemy models (create_all) and stamp
     Alembic to head, IN-PROCESS (NOT via subprocess / sys.executable — in a
     frozen bundle sys.executable IS the app binary; shelling out would
     re-enter main() and fork-bomb the process)
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

# Set once _setup_logging() installs the file handler. The emergency paths
# below fall back to writing this same file directly if normal logging never
# got the chance to initialise.
_LOG_PATH: Path | None = None
_LOGGING_CONFIGURED = False


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

    Idempotent: a second call is a no-op so the bootstrap-then-main sequence
    does not double-install handlers.
    """
    global _LOG_PATH, _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return

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

    _LOG_PATH = log_path
    _LOGGING_CONFIGURED = True
    logger.info("Matika starting — log: %s", log_path)


# ---------------------------------------------------------------------------
# Last-resort failure capture
#
# The user MANDATE: no startup failure may ever be silent. A Finder-launched
# crash discards stdout/stderr, so the dated log file is the only durable
# diagnostic surface. These helpers guarantee a traceback reaches that file
# even for import-time / pre-main failures that occur before — or instead of —
# normal logging being configured.
# ---------------------------------------------------------------------------

def _emergency_log_path() -> Path:
    """Best-effort path to today's log file, creating ~/matika/logs/ if needed.

    Used when a failure happens before _setup_logging() ran (so _LOG_PATH is
    still None). Never raises: on any error it falls back to ~/matika so the
    traceback still lands on disk somewhere discoverable.
    """
    if _LOG_PATH is not None:
        return _LOG_PATH
    try:
        log_dir = Path.home() / "matika" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir / f"matika-{date.today().isoformat()}.log"
    except Exception:
        return Path.home() / "matika" / "startup-failure.log"


def _write_fatal(exc: BaseException) -> str:
    """Write the full traceback of *exc* to the dated log file and return it.

    Tries the configured root logger first (so the record is formatted and
    flushed like every other line); ALWAYS also appends the raw traceback to
    the dated log file directly, so the diagnostic survives even if the
    logging subsystem itself is the thing that failed to initialise.
    """
    import traceback as _tb

    tb_text = "".join(_tb.format_exception(type(exc), exc, exc.__traceback__))

    try:
        logging.getLogger().critical("FATAL startup failure:\n%s", tb_text)
    except Exception:
        pass

    try:
        path = _emergency_log_path()
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(
                f"\n{date.today().isoformat()} FATAL startup failure "
                f"(ManoMatika could not start):\n{tb_text}\n"
            )
    except Exception:
        # Truly last resort — stderr (discarded under Finder, but present in
        # the CI smoke launch and `open`-from-terminal paths).
        print(f"FATAL startup failure:\n{tb_text}", file=sys.stderr)

    return tb_text


def _show_fatal_dialog(tb_text: str) -> None:
    """Show the user-facing 'cannot start' dialog with the failure detail."""
    msg = (
        "ManoMatika cannot start — an error occurred during launch.\n\n"
        f"{tb_text.strip().splitlines()[-1] if tb_text.strip() else ''}\n\n"
        "See the log file in ~/matika/logs/ for the full traceback."
    )
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("ManoMatika — Startup Error", msg)
        root.destroy()
    except Exception:
        print(f"ERROR: {msg}", file=sys.stderr)


def _excepthook(exc_type, exc, tb) -> None:
    """Top-level last-resort hook: log any uncaught exception + show dialog."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc, tb)
        return
    tb_text = _write_fatal(exc)
    _show_fatal_dialog(tb_text)


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


def _init_database_schema(data_dir: Path) -> None:
    """Initialise the first-run database schema IN-PROCESS, then stamp Alembic.

    matika's SQLAlchemy models are the source of truth for the schema:
    ``matika.database.init_db()`` runs ``Base.metadata.create_all()``, which
    creates every table AND the indexes the models declare. The Alembic
    migrations carry only INCREMENTAL changes for already-existing installs
    (e.g. adding the permissions indexes to a pre-index DB), so running
    ``alembic upgrade head`` against a FRESH empty database fails with
    "no such table: permissions" — the initial index migration assumes the
    table is already there. (That is exactly the second boot failure the CI
    smoke-launch caught.)

    The correct first-run sequence for this create_all-owns-the-schema model is
    therefore: ``create_all()`` to build the current schema, then
    ``alembic stamp head`` to record the DB as fully migrated — so a future app
    version's NEW migrations apply incrementally on top, and the initial index
    migration is never replayed onto a schema that already has those indexes.

    Everything runs IN-PROCESS via the Alembic Python API rather than a
    subprocess: sys.executable inside a frozen bundle IS the app binary, so
    shelling out with [sys.executable, "-m", "alembic", ...] would re-enter
    launcher.py::main(), trigger another first_run_init(), and fork-bomb the
    process tree until EAGAIN.

    The database lives at ~/matika/data/matika.db. DATABASE_URL is set in the
    process environment because matika.database builds its engine from it at
    import time (and migrations/env.py reads it too); the previous value is
    restored on exit so subsequent code is not affected.
    """
    db_path = data_dir / "data" / "matika.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    database_url = f"sqlite:///{db_path}"

    # matika.database reads DATABASE_URL at import time to build its engine, so
    # it MUST be set before the import below. Restore the prior value after.
    _prev_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    try:
        logger.info("Creating database schema (create_all) — database: %s", db_path)
        from matika.database import init_db

        init_db()  # Base.metadata.create_all — tables + model-declared indexes
        logger.info("Database schema created")

        from alembic import command as alembic_command
        from alembic.config import Config as AlembicConfig

        alembic_ini = _bundle_path("alembic.ini")
        migrations_dir = _bundle_path("migrations")
        cfg = AlembicConfig(alembic_ini)
        cfg.set_main_option("sqlalchemy.url", database_url)
        # Pin script_location to the bundled migrations tree explicitly so the
        # stamp resolves the sys._MEIPASS-relative versions/, not a dev path.
        cfg.set_main_option("script_location", migrations_dir)
        logger.info(
            "Stamping alembic to head (ini=%s, migrations=%s)",
            alembic_ini, migrations_dir,
        )
        alembic_command.stamp(cfg, "head")
        logger.info("alembic stamp head complete")
    finally:
        if _prev_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = _prev_url


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
    2. Create the database schema (create_all) + stamp Alembic to head
       (in-process, not via subprocess)
    3. Extract bundled plugins → ~/matika/plugins/
    4. Write sentinel file ~/matika/.initialized

    Raises ``RuntimeError`` if any step fails; the sentinel is only written
    after all steps succeed so a partial init is retried on next launch.
    """
    logger.info("First-run init starting")
    env_path = data_dir / ".env"
    _generate_secret_key(env_path)
    logger.info("SECRET_KEY generated → %s", env_path)

    _init_database_schema(data_dir)

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
        f"ManoMatika cannot start because port {port} is already in use.\n\n"
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
        messagebox.showerror("ManoMatika — Port Conflict", message)
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
            msg = f"ManoMatika first-run setup failed:\n\n{exc}\n\nManoMatika cannot start."
            try:
                import tkinter as tk
                from tkinter import messagebox

                root = tk.Tk()
                root.withdraw()
                messagebox.showerror("ManoMatika — Setup Error", msg)
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
    # Logging up FIRST — before any risky/heavy import in main() (alembic, the
    # matika app, plugins, uvicorn). A failure anywhere after this point lands
    # in ~/matika/logs/matika-<date>.log, satisfying the mandate that NO
    # startup failure is ever silent.
    try:
        _setup_logging(_data_dir())
    except Exception as _boot_exc:  # logging bootstrap itself failed
        _write_fatal(_boot_exc)

    # Catch even exceptions raised outside the explicit try/except below
    # (e.g. in background threads' default hook) as a final backstop.
    sys.excepthook = _excepthook

    try:
        main()
    except SystemExit:
        raise  # an intentional sys.exit() — already logged at the call site
    except BaseException as _exc:
        tb_text = _write_fatal(_exc)
        _show_fatal_dialog(tb_text)
        sys.exit(1)
