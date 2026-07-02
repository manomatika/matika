"""logging_setup.py — the single logging config / format / path authority for matika.

This module unifies matika's two formerly-accidental logging subsystems — the old
``core/logging_config.py`` (startup/app/test file handlers) and ``launcher.py``'s
standalone dated root-logger handler — into ONE authority with two deliberate sinks:

  * **startup**   — the boot phase.  Every record is stamped with the shared
                    per-process ``run_id`` and buffered in a bounded in-memory
                    ``deque`` while also being written to the dated startup log.
  * **aggregate** — the steady-state runtime log (formerly the "app" log).  At the
                    startup→runtime handoff the buffered startup records are FLUSHED
                    into it (carrying the same ``run_id``), so the runtime log holds
                    the full boot history under one run identity.

Structured records
------------------
Every record carries a shared UUID4 ``run_id`` (one per process run) and an optional
``code`` field.  ``code`` is the forward-compatible seam for the forthcoming
error-code framework (a code→severity/facility/destination stamping filter); it is
always ``None`` here and renders as ``-``.  The stamping filter is attached to each
*handler* (not the root logger) because a logger's filters are applied only to
records logged directly to it — never to records propagated up from child loggers.

Paths
-----
All sinks live under ``<MATIKA_HOME>/logs`` (the single home authority resolved by
``matika.core.paths.get_matika_home``).  Log files are dated; rotation prunes by
retention COUNT per sink.
"""

from __future__ import annotations

import logging
import re
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from .paths import get_matika_home

# ---------------------------------------------------------------------------
# Format / constants
# ---------------------------------------------------------------------------

# The single canonical record format.  ``run=`` and ``code=`` make the shared
# run_id and the (future) error code first-class, greppable fields on every line.
_LOG_FORMAT = (
    "%(asctime)s %(levelname)-8s run=%(run_id)s code=%(code_display)s "
    "%(name)s: %(message)s"
)
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Bounded in-memory buffer for the startup phase (Q18: deque(maxlen=1000)).
STARTUP_BUFFER_MAXLEN = 1000

# Handler names — used both to label handlers and to make phase installation
# idempotent (re-running a phase is a no-op while its handler is still attached).
_STARTUP_HANDLER = "matika-startup"
_STARTUP_BUFFER_HANDLER = "matika-startup-buffer"
_STARTUP_STREAM_HANDLER = "matika-startup-stream"
_AGGREGATE_HANDLER = "matika-aggregate"

# ---------------------------------------------------------------------------
# Run identity — one UUID4 per process run, shared across the two-phase flush
# ---------------------------------------------------------------------------

_RUN_ID: Optional[str] = None


def get_run_id() -> str:
    """Return this process run's UUID4 ``run_id``, creating it on first use.

    Exactly one id per process run: it is stamped on every record and is carried
    unchanged when the startup buffer is flushed into the runtime-aggregate sink,
    so a single boot→runtime session is one grep-able ``run=<uuid>`` identity.
    """
    global _RUN_ID
    if _RUN_ID is None:
        _RUN_ID = str(uuid.uuid4())
    return _RUN_ID


# ---------------------------------------------------------------------------
# Structured record
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StructuredRecord:
    """A structured, self-describing log record.

    ``code`` is the forward-compatible seam for the error-code framework
    (R2/R3): today it is always ``None``.  Keeping it optional-and-absent here
    lets a later code→severity/facility/destination stamping filter populate it
    without any change to this record shape.
    """

    run_id: str
    timestamp: str
    level: str
    logger: str
    message: str
    code: Optional[str] = None

    def render(self) -> str:
        """Render this record as one canonical log line (matches ``_LOG_FORMAT``)."""
        return (
            f"{self.timestamp} {self.level:<8} run={self.run_id} "
            f"code={self.code if self.code else '-'} {self.logger}: {self.message}"
        )


# ---------------------------------------------------------------------------
# Stamping filter + formatter
# ---------------------------------------------------------------------------

class StructuredLogFilter(logging.Filter):
    """Stamp every record with the shared ``run_id`` and an optional error ``code``.

    Attached to each HANDLER (not the root logger) so records propagated up from
    child loggers are stamped too.  ``code`` defaults to ``None`` and is exposed
    to the formatter as ``code_display`` ('-' when absent) — the seam the future
    error-code framework fills in.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "run_id"):
            record.run_id = get_run_id()
        code = getattr(record, "code", None)
        record.code = code
        record.code_display = code if code else "-"
        return True


class StructuredFormatter(logging.Formatter):
    """Canonical formatter.  Defensively fills ``run_id``/``code_display`` so a
    record that reached a handler without the stamping filter (e.g. pytest's
    caplog) still formats instead of raising ``KeyError``."""

    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "run_id"):
            record.run_id = get_run_id()
        if not hasattr(record, "code_display"):
            code = getattr(record, "code", None)
            record.code_display = code if code else "-"
        return super().format(record)


_STRUCT_FILTER = StructuredLogFilter()


def _new_formatter() -> StructuredFormatter:
    return StructuredFormatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)


# ---------------------------------------------------------------------------
# Bounded startup buffer
# ---------------------------------------------------------------------------

_startup_buffer: "deque[StructuredRecord]" = deque(maxlen=STARTUP_BUFFER_MAXLEN)


def startup_buffer() -> "deque[StructuredRecord]":
    """Return the bounded in-memory buffer of structured startup records."""
    return _startup_buffer


class _StartupBufferHandler(logging.Handler):
    """Capture each boot record as a :class:`StructuredRecord` in the bounded deque."""

    def __init__(self, buffer: "deque[StructuredRecord]") -> None:
        super().__init__()
        self._buffer = buffer

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._buffer.append(
                StructuredRecord(
                    run_id=getattr(record, "run_id", get_run_id()),
                    timestamp=datetime.fromtimestamp(record.created).strftime(
                        _DATE_FORMAT
                    ),
                    level=record.levelname,
                    logger=record.name,
                    message=record.getMessage(),
                    code=getattr(record, "code", None),
                )
            )
        except Exception:  # pragma: no cover - logging must never crash the app
            self.handleError(record)


# ---------------------------------------------------------------------------
# Paths / dated filenames
# ---------------------------------------------------------------------------

def log_dir(home: Optional[str | Path] = None) -> Path:
    """Return (creating if absent) ``<MATIKA_HOME>/logs``.

    *home* overrides the resolved MATIKA_HOME — used by the launcher (which passes
    its own data dir) and by tests.
    """
    base = Path(home) if home is not None else Path(get_matika_home())
    d = base / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _dated_filename(sink: str, on: Optional[date] = None) -> str:
    on = on or date.today()
    if sink == "aggregate":
        return f"matika-{on.isoformat()}.log"
    if sink == "startup":
        return f"matika-startup-{on.isoformat()}.log"
    raise ValueError(
        f"unknown log sink {sink!r}; expected 'startup' or 'aggregate'"
    )


# Per-sink matcher for dated files (rotation ignores anything else in logs/).
_DATED_RE = {
    "aggregate": re.compile(r"^matika-\d{4}-\d{2}-\d{2}\.log$"),
    "startup": re.compile(r"^matika-startup-\d{4}-\d{2}-\d{2}\.log$"),
}


def startup_log_path(home: Optional[str | Path] = None) -> Path:
    """Absolute path of today's startup sink file."""
    return log_dir(home) / _dated_filename("startup")


def aggregate_log_path(home: Optional[str | Path] = None) -> Path:
    """Absolute path of today's runtime-aggregate sink file."""
    return log_dir(home) / _dated_filename("aggregate")


# ---------------------------------------------------------------------------
# Two-phase startup → runtime
# ---------------------------------------------------------------------------

def _has_handler(root: logging.Logger, name: str) -> bool:
    return any(getattr(h, "name", None) == name for h in root.handlers)


def _make_file_handler(path: Path, name: str) -> logging.FileHandler:
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.set_name(name)
    handler.setFormatter(_new_formatter())
    handler.addFilter(_STRUCT_FILTER)
    return handler


def begin_startup_phase(
    home: Optional[str | Path] = None,
    *,
    is_testing: bool = False,
    level: int = logging.INFO,
    with_stream: bool = False,
) -> Optional[Path]:
    """Phase 1 — install the startup sink + bounded in-memory buffer.

    Adds a dated startup FileHandler and a :class:`_StartupBufferHandler` (feeding
    ``deque(maxlen=1000)``) to the root logger, each stamping records with the
    shared ``run_id``.  Idempotent: while the startup handler is still attached a
    repeat call only returns the path.  A no-op under *is_testing* so the test
    suite never installs file handlers.
    """
    if is_testing:
        return None
    root = logging.getLogger()
    startup_path = startup_log_path(home)
    if _has_handler(root, _STARTUP_HANDLER):
        return startup_path
    root.setLevel(level)
    root.addHandler(_make_file_handler(startup_path, _STARTUP_HANDLER))
    buffer_handler = _StartupBufferHandler(_startup_buffer)
    buffer_handler.set_name(_STARTUP_BUFFER_HANDLER)
    buffer_handler.addFilter(_STRUCT_FILTER)
    root.addHandler(buffer_handler)
    if with_stream and not _has_handler(root, _STARTUP_STREAM_HANDLER):
        stream = logging.StreamHandler()
        stream.set_name(_STARTUP_STREAM_HANDLER)
        stream.setFormatter(_new_formatter())
        stream.addFilter(_STRUCT_FILTER)
        root.addHandler(stream)
    logging.getLogger(__name__).info(
        "logging startup phase begin — run_id=%s sink=%s", get_run_id(), startup_path
    )
    return startup_path


def begin_runtime_phase(
    home: Optional[str | Path] = None,
    *,
    is_testing: bool = False,
) -> Optional[Path]:
    """Phase 2 — hand off from startup to the runtime-aggregate sink.

    Installs the dated aggregate FileHandler, FLUSHES the buffered startup records
    (carrying the same ``run_id``) into it so the runtime log opens with the full
    boot history, then detaches the startup file + buffer handlers so ongoing
    runtime logging lands only in the aggregate sink.  A no-op under *is_testing*.
    """
    if is_testing:
        return None
    root = logging.getLogger()
    aggregate_path = aggregate_log_path(home)

    # Flush the buffered startup history into the aggregate sink FIRST, in order.
    with open(aggregate_path, "a", encoding="utf-8") as fh:
        for rec in list(_startup_buffer):
            fh.write(rec.render() + "\n")

    if not _has_handler(root, _AGGREGATE_HANDLER):
        root.addHandler(_make_file_handler(aggregate_path, _AGGREGATE_HANDLER))

    # Detach the startup file + buffer handlers — the boot phase is over.
    for handler in list(root.handlers):
        if getattr(handler, "name", None) in (_STARTUP_HANDLER, _STARTUP_BUFFER_HANDLER):
            root.removeHandler(handler)
            handler.close()

    logging.getLogger(__name__).info(
        "logging runtime phase begin — run_id=%s sink=%s (flushed %d startup records)",
        get_run_id(),
        aggregate_path,
        len(_startup_buffer),
    )
    return aggregate_path


# ---------------------------------------------------------------------------
# Dated-file rotation (prune by retention count, per sink)
# ---------------------------------------------------------------------------

def prune_logs(
    retention: Optional[dict[str, int]] = None,
    home: Optional[str | Path] = None,
    *,
    is_testing: bool = False,
) -> dict[str, list[str]]:
    """Prune dated log files, keeping the newest *retention[sink]* files per sink.

    Retention is a COUNT of files (Q18: rotation prunes by retention count), not a
    number of days.  Only files matching a sink's dated pattern are candidates;
    any other filename in ``logs/`` is left untouched.  Returns a per-sink list of
    removed filenames (for diagnostics).  A no-op under *is_testing*.
    """
    removed: dict[str, list[str]] = {}
    if is_testing or not retention:
        return removed
    directory = log_dir(home)
    for sink, keep in retention.items():
        matcher = _DATED_RE.get(sink)
        if matcher is None:
            raise ValueError(
                f"unknown log sink {sink!r} in retention map; "
                f"expected one of {sorted(_DATED_RE)}"
            )
        # ISO dates sort chronologically as strings → newest last.
        dated = sorted(p for p in directory.iterdir() if matcher.match(p.name))
        doomed = dated[:-keep] if keep > 0 else list(dated)
        removed[sink] = []
        for stale in doomed:
            try:
                stale.unlink()
                removed[sink].append(stale.name)
            except OSError as exc:  # pragma: no cover - best-effort prune
                logging.getLogger(__name__).warning(
                    "could not prune stale log %s: %s", stale, exc
                )
    return removed
