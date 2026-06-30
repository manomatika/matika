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
   - Write a sentinel file (~/matika/.initialized) on success so init
     is skipped on every subsequent launch

1a. Plugin install / refresh (EVERY launch, NOT gated by the sentinel):
   - Install or refresh bundled plugins into ~/matika/plugins/<name>/ —
     version/fingerprint-gated so an upgrade replaces stale plugin code while
     preserving user/runtime data (see _extract_bundled_plugins)
   - Set MATIKA_PLUGINS_DIR so the app discovers the extracted plugins

2. Durable logging:
   - Configure file + stream logging to ~/matika/logs/matika-<date>.log as
     the FIRST action after ~/matika/ is created, so a Finder-launched crash
     always leaves a diagnosable log on disk.

3. Port-conflict detection and health-gated reclaim:
   - Before starting uvicorn, probe the configured port (MATIKA_PORT env var,
     default 8000 — see ``_configured_port``).  /healthz is the SOLE
     authority for "a healthy server is up"; process-alive / port-bound
     alone are never sufficient.
   - Healthy ManoMatika instance already there → open a browser tab to it,
     exit 0 (second-click path).
   - Port held but /healthz does not answer healthy (dead/wedged/crashed) →
     identify the holder via psutil; if POSITIVELY identified as a
     ManoMatika process, force-kill it and start fresh (reclaim). If the
     holder is foreign or cannot be identified, never guess — fail loud
     with the port + holder PID and exit 1.

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

import hashlib
import json
import logging
import multiprocessing
import os
import secrets
import shutil
import signal
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
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


# Per-plugin install marker written into ~/matika/plugins/<id>/ at every
# extract/refresh. Records WHICH bundled version's CODE is currently installed
# and a content fingerprint of that code, plus the manifest of code-file paths.
# It is the signal that lets an UPGRADE refresh stale plugin code instead of
# skipping it (the root cause of the "admin coming soon / lookup dead" bug:
# a prior install left an old eyerate template in ~/matika/plugins/eyerate/
# and the old `if not exists` logic never re-extracted it). The marker name is
# dotfile-prefixed so AppLugService — which scans for ``applug.json`` — ignores
# it, and so it never collides with plugin code or user data.
_INSTALL_MARKER = ".matika_plugin_install.json"


def _read_plugin_version(plugin_dir: Path) -> str | None:
    """Return the ``version`` declared in a plugin's applug.json, or None.

    ``None`` means the manifest is absent or unreadable — treated as "unknown",
    which forces a refresh so a corrupt/legacy install is healed rather than
    trusted.
    """
    manifest = plugin_dir / "applug.json"
    try:
        with manifest.open(encoding="utf-8") as fh:
            version = json.load(fh).get("version")
    except (OSError, ValueError):
        return None
    return version if isinstance(version, str) else None


def _plugin_code_fingerprint(plugin_dir: Path) -> tuple[str, list[str]]:
    """Return ``(sha256_hex, sorted_relative_code_paths)`` for *plugin_dir*.

    The hash covers every regular file's relative path AND bytes, so any code
    change (even a same-version rebuild) changes the fingerprint. The install
    marker itself is excluded so re-hashing an installed tree is stable. The
    returned path list is the code manifest used to safely remove stale code on
    refresh WITHOUT touching user/runtime data that lives outside the manifest.
    """
    h = hashlib.sha256()
    rel_paths: list[str] = []
    for path in sorted(
        p for p in plugin_dir.rglob("*") if p.is_file()
    ):
        rel = path.relative_to(plugin_dir).as_posix()
        if rel == _INSTALL_MARKER:
            continue
        rel_paths.append(rel)
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(path.read_bytes())
        h.update(b"\0")
    return h.hexdigest(), rel_paths


def _read_install_marker(plugin_dest: Path) -> dict | None:
    """Return the parsed install marker for an installed plugin, or None."""
    marker = plugin_dest / _INSTALL_MARKER
    try:
        with marker.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _write_install_marker(plugin_dest: Path, version: str | None,
                          fingerprint: str, files: list[str]) -> None:
    """Record which bundled version/code is now installed in *plugin_dest*."""
    marker = plugin_dest / _INSTALL_MARKER
    payload = {
        "version": version,
        "code_fingerprint": fingerprint,
        "files": files,
    }
    with marker.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)


def _copy_plugin_code(plugin_src: Path, plugin_dest: Path,
                      bundled_files: list[str]) -> None:
    """Overwrite every bundled CODE file from *plugin_src* into *plugin_dest*.

    Only paths in *bundled_files* (the bundle's code manifest) are written, so
    files that exist in the destination but are NOT part of the bundle (user
    edits, runtime data) are never touched here — data is preserved by omission.
    """
    for rel in bundled_files:
        src = plugin_src / rel
        dest = plugin_dest / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(dest))


def _remove_stale_code(plugin_dest: Path, old_files: list[str],
                       new_files: set[str]) -> list[str]:
    """Delete installed code files that the new bundle no longer ships.

    Only files recorded in the PREVIOUS install marker (*old_files*) are
    candidates, so user/runtime data — which was never in any marker — is never
    deleted. Returns the list of removed relative paths (for logging). When the
    previous install predates this mechanism (no marker → empty *old_files*),
    nothing is removed: we cannot safely distinguish stale code from user data,
    so we only overwrite (which already heals the reported bug).
    """
    removed: list[str] = []
    for rel in old_files:
        if rel in new_files:
            continue
        stale = plugin_dest / rel
        try:
            if stale.is_file():
                stale.unlink()
                removed.append(rel)
        except OSError:
            logger.warning("plugin refresh: could not remove stale file %s", stale)
    return removed


def _extract_bundled_plugins(data_dir: Path) -> None:
    """Install or REFRESH plugins bundled in the frozen app into ~/matika/plugins/.

    Runs on EVERY launch (not just first-run) so an upgrade actually replaces
    stale plugin code. For each bundled plugin under ``<bundle>/plugins/``:

    * **fresh** — destination absent → copy the whole tree, write the marker.
    * **refresh** — destination exists but the bundled version differs from the
      installed version, OR the bundled code fingerprint differs from the one
      recorded in the install marker (catches same-version rebuilds and legacy
      installs with no marker) → overwrite all bundled CODE files, remove code
      the new bundle dropped (manifest-gated, so user/runtime DATA is preserved),
      rewrite the marker.
    * **skip** — installed version AND fingerprint already match → no-op.

    Every decision is logged with the versions involved so a support log shows,
    e.g. ``plugin eyerate: installed 0.0.3, bundled 0.0.4 -> refreshed``.
    """
    bundle_plugins = Path(_bundle_path("plugins"))
    if not bundle_plugins.is_dir():
        # No plugins were bundled — nothing to do.
        logger.info("No bundled plugins directory at %s — skipping extraction",
                    bundle_plugins)
        return

    plugins_dir = data_dir / "plugins"
    plugins_dir.mkdir(parents=True, exist_ok=True)

    for plugin_src in sorted(bundle_plugins.iterdir()):
        if not plugin_src.is_dir():
            continue
        name = plugin_src.name
        plugin_dest = plugins_dir / name

        bundled_version = _read_plugin_version(plugin_src)
        bundled_fp, bundled_files = _plugin_code_fingerprint(plugin_src)

        if not plugin_dest.exists():
            shutil.copytree(str(plugin_src), str(plugin_dest))
            _write_install_marker(plugin_dest, bundled_version, bundled_fp,
                                  bundled_files)
            logger.info(
                "plugin %s: not installed, bundled %s -> extracted (fresh)",
                name, bundled_version,
            )
            continue

        installed_version = _read_plugin_version(plugin_dest)
        marker = _read_install_marker(plugin_dest)
        installed_fp = marker.get("code_fingerprint") if marker else None
        old_files = marker.get("files", []) if marker else []

        version_changed = installed_version != bundled_version
        code_changed = installed_fp != bundled_fp
        if not version_changed and not code_changed:
            logger.info(
                "plugin %s: installed %s, bundled %s -> up to date (skip)",
                name, installed_version, bundled_version,
            )
            continue

        # Refresh CODE in place, preserving any data files not in the bundle.
        _copy_plugin_code(plugin_src, plugin_dest, bundled_files)
        removed = _remove_stale_code(plugin_dest, old_files, set(bundled_files))
        _write_install_marker(plugin_dest, bundled_version, bundled_fp,
                              bundled_files)
        logger.info(
            "plugin %s: installed %s, bundled %s -> refreshed "
            "(version_changed=%s, code_changed=%s, stale_removed=%d, "
            "had_marker=%s)",
            name, installed_version, bundled_version,
            version_changed, code_changed, len(removed), marker is not None,
        )


def first_run_init(data_dir: Path) -> None:
    """Perform all one-time first-run initialisation steps.

    Steps:
    1. Generate SECRET_KEY → ~/matika/.env
    2. Create the database schema (create_all) + stamp Alembic to head
       (in-process, not via subprocess)
    3. Write sentinel file ~/matika/.initialized

    Plugin extraction is NOT a first-run-only step: it runs on every launch
    (see ``main`` → ``_extract_bundled_plugins``) so an upgrade refreshes stale
    bundled plugin code. Gating it behind the ``.initialized`` sentinel was the
    root cause of the "admin coming soon / lookup dead" bug — on an upgrade the
    sentinel already existed, so the new plugin code was never extracted.

    Raises ``RuntimeError`` if any step fails; the sentinel is only written
    after all steps succeed so a partial init is retried on next launch.
    """
    logger.info("First-run init starting")
    env_path = data_dir / ".env"
    _generate_secret_key(env_path)
    logger.info("SECRET_KEY generated → %s", env_path)

    _init_database_schema(data_dir)

    # Mark initialisation complete.
    (data_dir / ".initialized").touch()
    logger.info("First-run init complete — sentinel written")


# ---------------------------------------------------------------------------
# Port-conflict detection
# ---------------------------------------------------------------------------

def _port_available(port: int) -> bool:
    """Return True if port can be bound on localhost (False = port already in use)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _probe_healthz(port: int, timeout: float = 2.0) -> dict | None:
    """Probe /healthz at 127.0.0.1:port. Returns parsed JSON dict or None on failure."""
    import json as _json
    url = f"http://127.0.0.1:{port}/healthz"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return _json.loads(resp.read().decode())
    except Exception as exc:
        logger.warning("healthz probe failed: %s (port %d)", exc, port)
        return None


def _probe_healthz_with_retry(
    port: int, attempts: int = 3, interval: float = 0.3, timeout: float = 1.0
) -> dict | None:
    """Probe /healthz with a small BOUNDED retry.

    A server that is still starting up (e.g. mid-restart after a reclaim) gets
    a beat to answer before being declared dead — without this, a slow but
    healthy startup could be mistaken for a dead-and-reclaimable state. Returns
    the first healthy ManoMatika response seen, or the LAST response observed
    (possibly None) once *attempts* are exhausted; the caller decides what to
    do with a non-healthy result.
    """
    result = None
    for attempt in range(attempts):
        result = _probe_healthz(port, timeout=timeout)
        if result and result.get("status") == "ok" and result.get("product") == "ManoMatika":
            return result
        if attempt < attempts - 1:
            time.sleep(interval)
    return result


def _wait_for_ready(
    port: int,
    interval: float = 0.5,
    per_attempt_timeout: float = 1.0,
    startup_timeout: float = 30.0,
) -> bool:
    """Poll /healthz until ok or startup_timeout exhausted. Returns True on success."""
    deadline = time.monotonic() + startup_timeout
    attempts = 0
    while time.monotonic() < deadline:
        attempts += 1
        data = _probe_healthz(port, timeout=per_attempt_timeout)
        if data and data.get("status") == "ok":
            return True
        time.sleep(interval)
    logger.error(
        "server not ready after %ss (%d attempts); browser not opened",
        startup_timeout, attempts,
    )
    return False


def _show_port_error(port: int, holder_pid: int | None = None) -> None:
    """Display a user-friendly error when the port is already in use.

    *holder_pid*, when known, is included so the message is actionable (rule
    18 — fail loud with the port AND the holder PID, never a bare "in use").
    """
    holder_clause = f" by process {holder_pid}" if holder_pid is not None else ""
    message = (
        f"ManoMatika cannot start because port {port} is already in use{holder_clause}.\n\n"
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
# Configured port
# ---------------------------------------------------------------------------

def _configured_port() -> int:
    """Return the configured server port. MATIKA_PORT env var, default 8000.

    This is the SOLE source of the port everywhere in this module — never
    hardcode it elsewhere. Read after ``_load_env`` has merged ~/matika/.env
    into the process environment, so precedence is: a pre-set shell env var
    (``_load_env`` uses ``os.environ.setdefault``, so it never overrides one)
    > .env file > this default.
    """
    raw = os.environ.get("MATIKA_PORT", "8000")
    try:
        return int(raw)
    except ValueError:
        logger.warning("invalid MATIKA_PORT=%r — falling back to default port 8000", raw)
        return 8000


# ---------------------------------------------------------------------------
# Port-holder identification and reclaim (psutil-based, cross-platform)
#
# OS-independence: this entire feature is identical logic on macOS / Windows /
# Linux. Only _find_port_holder_pid / _force_kill_process touch a
# platform-specific primitive, and both do so exclusively through psutil's
# cross-platform API — no per-OS branching anywhere in this module.
# ---------------------------------------------------------------------------

def _find_port_holder_pid(port: int) -> int | None:
    """Best-effort: return the PID of the process LISTENing on *port*.

    Returns None both when no listener is found AND when a candidate's
    connection table could not be inspected (permission denied, vanished
    mid-scan) — both cases are reported identically as "holder unknown" so the
    caller treats them as ambiguous (fail loud) rather than as "no holder".
    """
    import psutil

    for proc in psutil.process_iter(["pid"]):
        try:
            conns = proc.net_connections(kind="inet")
        except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
            continue
        for conn in conns:
            if conn.status == psutil.CONN_LISTEN and conn.laddr and conn.laddr.port == port:
                return proc.pid
    return None


def _is_manomatika_process(pid: int) -> bool | None:
    """Identify whether *pid* is a ManoMatika process.

    Primary signal: the candidate's own executable path matches the
    currently-running frozen binary's executable path — the strongest
    possible signal, since this launcher process IS the ManoMatika binary.
    Falls back to a name-pattern match on the executable's basename, which
    also covers non-frozen/dev contexts and reinstalls where the exact path
    differs (e.g. an upgraded bundle at a new version-suffixed path).

    Returns None (unknown/ambiguous) — never a guessed True/False — when the
    candidate's executable can't be read (AccessDenied, already gone, or
    empty). Callers MUST treat None as "do not kill".
    """
    import psutil

    try:
        proc = psutil.Process(pid)
        exe = proc.exe()
    except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
        return None

    if not exe:
        return None

    our_exe = sys.executable if getattr(sys, "frozen", False) else None
    if our_exe:
        try:
            if os.path.realpath(exe) == os.path.realpath(our_exe):
                return True
        except OSError:
            pass

    return "manomatika" in os.path.basename(exe).lower()


def _force_kill_process(pid: int) -> None:
    """Force-kill *pid*. A process that is already gone is not an error."""
    import psutil

    try:
        proc = psutil.Process(pid)
        proc.kill()
        proc.wait(timeout=5)
    except psutil.NoSuchProcess:
        pass
    except psutil.TimeoutExpired:
        logger.warning("pid %d did not exit within 5s of force-kill", pid)


def _wait_for_port_free(port: int, timeout: float = 5.0, interval: float = 0.2) -> bool:
    """Poll ``_port_available(port)`` until True or *timeout* elapses."""
    deadline = time.monotonic() + timeout
    while True:
        if _port_available(port):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(interval)


def _handle_port_conflict(port: int) -> None:
    """Resolve a held *port*: defer to a healthy instance, reclaim a dead one,
    or fail loud. Called only when ``_port_available(port)`` is False.

    - /healthz (with a short bounded retry) identifies as a healthy ManoMatika
      instance → a live instance is already serving; open a tab and exit 0
      (the existing second-click path).
    - /healthz does not answer healthy AND the holder is POSITIVELY identified
      as a ManoMatika process → dead/wedged instance; force-kill it, confirm
      the port is free, and return so the caller proceeds with a fresh launch.
    - Anything else (foreign holder, or a holder that cannot be identified) →
      never guess; fail loud with the port and holder PID (when known) and
      exit 1.

    Returns normally ONLY in the reclaim-succeeded case; every other case
    calls ``sys.exit()`` and never returns.
    """
    healthz_data = _probe_healthz_with_retry(port)
    if healthz_data and healthz_data.get("product") == "ManoMatika":
        logger.info(
            "port %d already held by a healthy ManoMatika instance (healthz: %r); "
            "focusing existing window",
            port, healthz_data,
        )
        webbrowser.open(f"http://127.0.0.1:{port}")
        sys.exit(0)

    holder_pid = _find_port_holder_pid(port)
    is_ours = _is_manomatika_process(holder_pid) if holder_pid is not None else None

    if is_ours is True:
        logger.warning(
            "port %d held by a dead/unhealthy ManoMatika process (pid %d; healthz %s) "
            "-> reclaiming: force-killing and restarting fresh",
            port, holder_pid, healthz_data if healthz_data else "unreachable",
        )
        _force_kill_process(holder_pid)
        if not _wait_for_port_free(port):
            logger.error(
                "port %d still held after force-killing pid %d; aborting rather than "
                "guess at a second holder",
                port, holder_pid,
            )
            _show_port_error(port, holder_pid=holder_pid)
            sys.exit(1)
        logger.info("port %d reclaimed from dead pid %d; proceeding with fresh launch",
                    port, holder_pid)
        return  # caller falls through to the normal fresh-launch path

    if holder_pid is None:
        logger.error(
            "port %d held but no listening process could be identified (healthz %s); "
            "refusing to guess — failing loud",
            port, healthz_data if healthz_data else "unreachable",
        )
    else:
        logger.error(
            "port %d held by pid %d, which is NOT identified as a ManoMatika process "
            "(healthz %s); refusing to kill a foreign process — failing loud",
            port, holder_pid, healthz_data if healthz_data else "unreachable",
        )
    _show_port_error(port, holder_pid=holder_pid)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Initialise and launch the Matika app."""
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

    # Configured port — read AFTER _load_env so ~/matika/.env (and any
    # pre-set shell env var) can override the default. See _configured_port.
    port = _configured_port()

    # --- Plugin install / refresh (EVERY launch) -----------------------------
    # Runs unconditionally — NOT gated by the first-run sentinel — so an upgrade
    # over a prior install refreshes stale bundled plugin code while preserving
    # user/runtime data. A failure here must not be silent (stale plugins are
    # exactly the bug we are fixing), but it must also not block boot of the
    # rest of the app, so log loudly and continue.
    try:
        _extract_bundled_plugins(data_dir)
        logger.info("Plugin install/refresh complete")
    except Exception:
        logger.exception("Plugin install/refresh FAILED — continuing boot; "
                         "plugins may be stale or missing")

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

    # --- Port conflict check / health-gated reclaim ----------------------------
    # _handle_port_conflict only returns when it reclaimed a dead ManoMatika
    # process and the port is now free; every other outcome (healthy instance
    # found, foreign holder, ambiguous holder) calls sys.exit() itself.
    if not _port_available(port):
        _handle_port_conflict(port)

    # --- Launch ---------------------------------------------------------------
    logger.info("Starting uvicorn on http://127.0.0.1:%s", port)

    def _browser_open_when_ready() -> None:
        if _wait_for_ready(port):
            logger.info("server ready on port %d; opening browser", port)
            webbrowser.open(f"http://127.0.0.1:{port}")

    threading.Thread(target=_browser_open_when_ready, daemon=True, name="browser-open").start()

    import uvicorn

    _uvicorn_config = uvicorn.Config(
        "matika.main:app",
        host="127.0.0.1",
        port=port,
        log_level="info",
        timeout_graceful_shutdown=5,
    )
    _server = uvicorn.Server(_uvicorn_config)

    def _handle_shutdown(signum: int, frame: object) -> None:
        logger.info("signal %d received → draining (timeout %ss)", signum, 5)
        _server.should_exit = True

    signal.signal(signal.SIGTERM, _handle_shutdown)
    if signal.getsignal(signal.SIGINT) is signal.default_int_handler:
        signal.signal(signal.SIGINT, _handle_shutdown)

    try:
        _server.run()
    finally:
        logger.info("server stopped, port %d released", port)


if __name__ == "__main__":
    multiprocessing.freeze_support()
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
