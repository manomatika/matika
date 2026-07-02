"""Regression suite for the unified logging authority (matika#118).

Covers each Q18 delta at the layer it lives:
  * one shared UUID4 run_id per process, carried across the two-phase flush
  * bounded startup buffer — deque(maxlen=1000)
  * structured record shape + optional forward-compatible `code` seam
  * two deliberate sinks (startup + runtime-aggregate) with a startup→runtime flush
  * dated-file rotation that prunes by retention COUNT, per sink
  * single MATIKA_HOME home authority (fail-loud on an unusable explicit home)

Every test drives the real module so a missing/regressed behavior fails it.
"""

import logging
import re
import uuid

import pytest

from matika.core import logging_setup, paths


@pytest.fixture
def iso_logging():
    """Isolate global logging state: snapshot the root logger, reset the module's
    run_id and startup buffer, and strip any matika-* handlers afterwards so a
    test's real FileHandlers never leak into the rest of the suite."""
    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_level = root.level
    logging_setup._RUN_ID = None
    logging_setup.startup_buffer().clear()
    yield
    for h in list(root.handlers):
        if getattr(h, "name", "") and str(h.name).startswith("matika-"):
            root.removeHandler(h)
            try:
                h.close()
            except Exception:
                pass
    root.handlers = saved_handlers
    root.level = saved_level
    logging_setup._RUN_ID = None
    logging_setup.startup_buffer().clear()


# ---------------------------------------------------------------------------
# run_id
# ---------------------------------------------------------------------------

def test_run_id_is_stable_uuid4(iso_logging):
    rid = logging_setup.get_run_id()
    assert logging_setup.get_run_id() == rid, "run_id must be one-per-process (stable)"
    # UUID4: parses, and version field is 4.
    assert uuid.UUID(rid).version == 4


# ---------------------------------------------------------------------------
# Stamping filter + structured record shape
# ---------------------------------------------------------------------------

def test_filter_stamps_run_id_and_code_seam(iso_logging):
    rec = logging.LogRecord("x", logging.INFO, __file__, 1, "hi", None, None)
    assert logging_setup.StructuredLogFilter().filter(rec) is True
    assert rec.run_id == logging_setup.get_run_id()
    # No code today -> None kept, rendered as '-'. This is the error-code seam.
    assert rec.code is None
    assert rec.code_display == "-"


def test_structured_record_render_shape(iso_logging):
    rid = logging_setup.get_run_id()
    r = logging_setup.StructuredRecord(
        run_id=rid, timestamp="2026-07-02 10:00:00", level="INFO",
        logger="matika.demo", message="hello",
    )
    line = r.render()
    assert f"run={rid}" in line
    assert "code=-" in line
    assert "matika.demo: hello" in line
    assert r.code is None  # forward-compatible optional field, absent today


# ---------------------------------------------------------------------------
# Bounded startup buffer — deque(maxlen=1000)
# ---------------------------------------------------------------------------

def test_startup_buffer_bounded_at_1000(iso_logging, tmp_path):
    assert logging_setup.STARTUP_BUFFER_MAXLEN == 1000
    logging_setup.begin_startup_phase(home=tmp_path)
    log = logging.getLogger("matika.buftest")
    for i in range(1200):
        log.info("m%d", i)
    buf = logging_setup.startup_buffer()
    assert len(buf) == 1000, "startup buffer must be bounded at 1000"
    # Bounded from the LEFT — the newest record survives.
    assert buf[-1].message == "m1199"


# ---------------------------------------------------------------------------
# Two-phase flush — one shared run_id from startup into the aggregate sink
# ---------------------------------------------------------------------------

def test_two_phase_flush_carries_shared_run_id(iso_logging, tmp_path):
    startup_path = logging_setup.begin_startup_phase(home=tmp_path)
    assert startup_path == tmp_path / "logs" / startup_path.name
    assert startup_path.name.startswith("matika-startup-")

    log = logging.getLogger("matika.phasetest")
    log.info("startup-marker")

    rid = logging_setup.get_run_id()
    buffered = [r for r in logging_setup.startup_buffer() if r.message == "startup-marker"]
    assert buffered and buffered[0].run_id == rid

    agg_path = logging_setup.begin_runtime_phase(home=tmp_path)
    assert agg_path.name.startswith("matika-") and "startup" not in agg_path.name

    log.info("runtime-marker")

    agg_text = agg_path.read_text(encoding="utf-8")
    # The buffered startup history was flushed into the aggregate sink...
    assert "startup-marker" in agg_text
    # ...and the ongoing runtime line landed there too...
    assert "runtime-marker" in agg_text
    # ...both under the SAME run_id.
    assert agg_text.count(f"run={rid}") >= 2

    # The startup file + buffer handlers are detached after the handoff.
    root = logging.getLogger()
    names = {getattr(h, "name", None) for h in root.handlers}
    assert "matika-startup" not in names
    assert "matika-startup-buffer" not in names
    assert "matika-aggregate" in names


def test_startup_sink_written_during_boot(iso_logging, tmp_path):
    startup_path = logging_setup.begin_startup_phase(home=tmp_path)
    logging.getLogger("matika.sinktest").info("boot-line-xyz")
    assert "boot-line-xyz" in startup_path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Dated-file rotation — prune by retention COUNT, per sink
# ---------------------------------------------------------------------------

def test_prune_keeps_newest_n_per_sink(tmp_path):
    d = tmp_path / "logs"
    d.mkdir()
    for day in ("2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"):
        (d / f"matika-{day}.log").write_text("a")
        (d / f"matika-startup-{day}.log").write_text("b")

    removed = logging_setup.prune_logs(
        {"aggregate": 2, "startup": 1}, home=tmp_path
    )

    agg = sorted(p.name for p in d.iterdir() if re.match(r"^matika-\d", p.name))
    startup = sorted(p.name for p in d.iterdir() if p.name.startswith("matika-startup-"))
    assert agg == ["matika-2026-01-03.log", "matika-2026-01-04.log"]
    assert startup == ["matika-startup-2026-01-04.log"]
    # Removed lists name the older files.
    assert "matika-2026-01-01.log" in removed["aggregate"]
    assert "matika-startup-2026-01-01.log" in removed["startup"]


def test_prune_unknown_sink_fails_loud(tmp_path):
    (tmp_path / "logs").mkdir()
    with pytest.raises(ValueError) as exc:
        logging_setup.prune_logs({"bogus": 1}, home=tmp_path)
    assert "bogus" in str(exc.value)


def test_prune_is_noop_under_testing(tmp_path):
    d = tmp_path / "logs"
    d.mkdir()
    (d / "matika-2026-01-01.log").write_text("a")
    logging_setup.prune_logs({"aggregate": 0}, home=tmp_path, is_testing=True)
    assert (d / "matika-2026-01-01.log").exists()


# ---------------------------------------------------------------------------
# Phases are no-ops under is_testing (the suite never installs file handlers)
# ---------------------------------------------------------------------------

def test_phases_noop_under_testing(iso_logging, tmp_path):
    assert logging_setup.begin_startup_phase(home=tmp_path, is_testing=True) is None
    assert logging_setup.begin_runtime_phase(home=tmp_path, is_testing=True) is None
    assert not (tmp_path / "logs").exists()
    names = {getattr(h, "name", None) for h in logging.getLogger().handlers}
    assert "matika-startup" not in names


# ---------------------------------------------------------------------------
# Single MATIKA_HOME authority
# ---------------------------------------------------------------------------

def test_matika_home_env_is_the_authority(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("MATIKA_HOME", str(home))
    assert paths.get_matika_home() == str(home.resolve())
    # logging_setup resolves its log dir under the same single authority.
    assert logging_setup.log_dir() == home.resolve() / "logs"
    assert (home / "data").is_dir()


def test_matika_home_unusable_fails_loud(tmp_path, monkeypatch):
    # Point MATIKA_HOME under an existing FILE so mkdir cannot succeed.
    blocker = tmp_path / "afile"
    blocker.write_text("not a dir")
    monkeypatch.setenv("MATIKA_HOME", str(blocker / "sub"))
    with pytest.raises(RuntimeError) as exc:
        paths.get_matika_home()
    assert "MATIKA_HOME" in str(exc.value)
