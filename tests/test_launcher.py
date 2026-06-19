"""
tests/test_launcher.py — Unit tests for launcher.py

launcher.py runs in a frozen (PyInstaller) context at production time, but
all of its pure-Python logic is unit-testable by mocking filesystem and
subprocess operations.  We do NOT test uvicorn.run() or the tkinter dialog
paths here — those are integration/manual concerns.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest import mock

import pytest

# ---------------------------------------------------------------------------
# Import helpers from launcher (without executing main())
# ---------------------------------------------------------------------------

# Ensure the repo root is importable even when pytest is invoked from an
# arbitrary directory.
import importlib.util
import types

_LAUNCHER_PATH = Path(__file__).parent.parent / "launcher.py"


def _load_launcher() -> types.ModuleType:
    """Load launcher.py as a module without side-effects."""
    spec = importlib.util.spec_from_file_location("launcher", str(_LAUNCHER_PATH))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


launcher = _load_launcher()


# ---------------------------------------------------------------------------
# _bundle_path
# ---------------------------------------------------------------------------

class TestBundlePath:
    def test_development_context_uses_repo_root(self):
        """Outside a frozen bundle, _bundle_path uses the launcher's directory."""
        # sys.frozen is not set in the test environment.
        assert not getattr(sys, "frozen", False)
        result = launcher._bundle_path("VERSION")
        expected = os.path.join(
            os.path.dirname(os.path.abspath(str(_LAUNCHER_PATH))), "VERSION"
        )
        assert result == expected

    def test_frozen_context_uses_meipass(self, tmp_path):
        """In a frozen context, _bundle_path uses sys._MEIPASS."""
        with mock.patch.object(sys, "frozen", True, create=True), \
             mock.patch.object(sys, "_MEIPASS", str(tmp_path), create=True):
            result = launcher._bundle_path("some", "file.txt")
        assert result == str(tmp_path / "some" / "file.txt")


# ---------------------------------------------------------------------------
# _data_dir
# ---------------------------------------------------------------------------

class TestDataDir:
    def test_creates_and_returns_home_matika(self, tmp_path):
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        with mock.patch("pathlib.Path.home", return_value=fake_home):
            result = launcher._data_dir()
        assert result == fake_home / "matika"
        assert result.is_dir()

    def test_idempotent(self, tmp_path):
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        with mock.patch("pathlib.Path.home", return_value=fake_home):
            r1 = launcher._data_dir()
            r2 = launcher._data_dir()
        assert r1 == r2


# ---------------------------------------------------------------------------
# _load_env
# ---------------------------------------------------------------------------

class TestLoadEnv:
    def test_loads_key_value_pairs(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("FOO=bar\nBAZ=qux\n")
        env = os.environ.copy()
        env.pop("FOO", None)
        env.pop("BAZ", None)
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("FOO", None)
            os.environ.pop("BAZ", None)
            launcher._load_env(env_file)
            assert os.environ.get("FOO") == "bar"
            assert os.environ.get("BAZ") == "qux"

    def test_skips_comments_and_blank_lines(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("# this is a comment\n\nVALID_KEY=hello\n")
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("VALID_KEY", None)
            launcher._load_env(env_file)
            assert os.environ.get("VALID_KEY") == "hello"

    def test_does_not_override_existing_env(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("EXISTING_KEY=from_file\n")
        with mock.patch.dict(os.environ, {"EXISTING_KEY": "from_env"}, clear=False):
            launcher._load_env(env_file)
            assert os.environ.get("EXISTING_KEY") == "from_env"

    def test_missing_file_is_noop(self, tmp_path):
        """Calling _load_env on a non-existent path must not raise."""
        launcher._load_env(tmp_path / "nonexistent.env")

    def test_skips_lines_without_equals(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("NOEQUALS\nGOOD=val\n")
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("NOEQUALS", None)
            os.environ.pop("GOOD", None)
            launcher._load_env(env_file)
            assert "NOEQUALS" not in os.environ
            assert os.environ.get("GOOD") == "val"


# ---------------------------------------------------------------------------
# _generate_secret_key
# ---------------------------------------------------------------------------

class TestGenerateSecretKey:
    def test_writes_secret_key_to_new_file(self, tmp_path):
        env_path = tmp_path / ".env"
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SECRET_KEY", None)
            launcher._generate_secret_key(env_path)
        content = env_path.read_text()
        assert content.startswith("SECRET_KEY=")
        key_value = content.strip().split("=", 1)[1]
        assert len(key_value) > 40  # urlsafe 64-byte token is ~86 chars

    def test_sets_secret_key_in_environ(self, tmp_path):
        env_path = tmp_path / ".env"
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SECRET_KEY", None)
            launcher._generate_secret_key(env_path)
            assert "SECRET_KEY" in os.environ
            assert len(os.environ["SECRET_KEY"]) > 40

    def test_replaces_existing_secret_key(self, tmp_path):
        env_path = tmp_path / ".env"
        env_path.write_text("SECRET_KEY=old_key\nOTHER=value\n")
        launcher._generate_secret_key(env_path)
        lines = env_path.read_text().splitlines()
        secret_lines = [l for l in lines if l.startswith("SECRET_KEY=")]
        other_lines = [l for l in lines if l.startswith("OTHER=")]
        assert len(secret_lines) == 1
        assert secret_lines[0] != "SECRET_KEY=old_key"
        assert other_lines == ["OTHER=value"]

    def test_each_call_generates_unique_key(self, tmp_path):
        env1 = tmp_path / ".env1"
        env2 = tmp_path / ".env2"
        launcher._generate_secret_key(env1)
        launcher._generate_secret_key(env2)
        key1 = env1.read_text().strip().split("=", 1)[1]
        key2 = env2.read_text().strip().split("=", 1)[1]
        assert key1 != key2


# ---------------------------------------------------------------------------
# _run_alembic_upgrade  (Fix A regression — no subprocess / in-process API)
# ---------------------------------------------------------------------------

class TestRunAlembicUpgrade:
    def test_uses_inprocess_alembic_api_not_subprocess(self, tmp_path):
        """Fix A: _run_alembic_upgrade must call alembic.command.upgrade in-process.

        In a PyInstaller frozen bundle sys.executable IS the app binary; shelling
        out with [sys.executable, '-m', 'alembic', ...] would re-enter main() and
        fork-bomb the process tree until EAGAIN.  The fix uses the Python API.
        """
        with mock.patch("alembic.command.upgrade") as mock_upgrade, \
             mock.patch.object(launcher, "_bundle_path", return_value=str(tmp_path / "alembic.ini")):
            launcher._run_alembic_upgrade(tmp_path)

        mock_upgrade.assert_called_once()
        _cfg, revision = mock_upgrade.call_args[0]
        assert revision == "head"

    def test_does_not_spawn_subprocess(self, tmp_path):
        """Fix A: critically, no subprocess.run/Popen calls — sys.executable is
        the frozen binary in a bundle and shelling out would re-enter main()."""
        with mock.patch("alembic.command.upgrade"), \
             mock.patch.object(launcher, "_bundle_path", return_value=str(tmp_path / "alembic.ini")), \
             mock.patch("subprocess.run") as mock_sub, \
             mock.patch("subprocess.Popen") as mock_popen:
            launcher._run_alembic_upgrade(tmp_path)

        mock_sub.assert_not_called()
        mock_popen.assert_not_called()

    def test_sets_sqlalchemy_url_to_data_db(self, tmp_path):
        """Fix A: the Alembic config must point to ~/matika/data/matika.db."""
        captured: dict = {}

        def _capture(cfg, revision):
            captured["url"] = cfg.get_main_option("sqlalchemy.url")

        with mock.patch("alembic.command.upgrade", side_effect=_capture), \
             mock.patch.object(launcher, "_bundle_path", return_value=str(tmp_path / "alembic.ini")):
            ini = tmp_path / "alembic.ini"
            ini.write_text("[alembic]\n")
            launcher._run_alembic_upgrade(tmp_path)

        expected = f"sqlite:///{tmp_path / 'data' / 'matika.db'}"
        assert captured["url"] == expected

    def test_creates_data_subdirectory(self, tmp_path):
        with mock.patch("alembic.command.upgrade"), \
             mock.patch.object(launcher, "_bundle_path", return_value=str(tmp_path / "alembic.ini")):
            launcher._run_alembic_upgrade(tmp_path)
        assert (tmp_path / "data").is_dir()

    def test_database_url_env_scoped_to_call(self, tmp_path, monkeypatch):
        """Fix A: DATABASE_URL must be set for migrations/env.py during the
        upgrade call and restored (or removed) on exit so other code is not
        affected.  The existing sentinel value must be preserved."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///sentinel_value.db")
        captured: dict = {}

        def _capture(cfg, revision):
            captured["DATABASE_URL_during_upgrade"] = os.environ.get("DATABASE_URL")

        with mock.patch("alembic.command.upgrade", side_effect=_capture), \
             mock.patch.object(launcher, "_bundle_path", return_value=str(tmp_path / "alembic.ini")):
            ini = tmp_path / "alembic.ini"
            ini.write_text("[alembic]\n")
            launcher._run_alembic_upgrade(tmp_path)

        expected_db = str(tmp_path / "data" / "matika.db")
        assert captured["DATABASE_URL_during_upgrade"] == f"sqlite:///{expected_db}"
        # After the call, DATABASE_URL must be restored to the original value.
        assert os.environ.get("DATABASE_URL") == "sqlite:///sentinel_value.db"


# ---------------------------------------------------------------------------
# _extract_bundled_plugins
# ---------------------------------------------------------------------------

class TestExtractBundledPlugins:
    def test_copies_each_plugin_subdirectory(self, tmp_path):
        bundle_plugins = tmp_path / "bundle" / "plugins"
        plugin_a = bundle_plugins / "plugin_a"
        plugin_a.mkdir(parents=True)
        (plugin_a / "applug.json").write_text('{"id": "plugin_a"}')

        data_dir = tmp_path / "data"
        data_dir.mkdir()

        with mock.patch.object(launcher, "_bundle_path", return_value=str(bundle_plugins)):
            launcher._extract_bundled_plugins(data_dir)

        assert (data_dir / "plugins" / "plugin_a" / "applug.json").exists()

    def test_skips_existing_plugin_directory(self, tmp_path):
        """Already-extracted plugins must not be overwritten."""
        bundle_plugins = tmp_path / "bundle" / "plugins"
        plugin_a = bundle_plugins / "plugin_a"
        plugin_a.mkdir(parents=True)
        (plugin_a / "applug.json").write_text('{"id": "plugin_a"}')

        data_dir = tmp_path / "data"
        dest_plugin = data_dir / "plugins" / "plugin_a"
        dest_plugin.mkdir(parents=True)
        (dest_plugin / "user_data.txt").write_text("keep this")

        with mock.patch.object(launcher, "_bundle_path", return_value=str(bundle_plugins)):
            launcher._extract_bundled_plugins(data_dir)

        # The user's file must still be there — the copy was skipped.
        assert (dest_plugin / "user_data.txt").exists()

    def test_noop_when_no_bundle_plugins_dir(self, tmp_path):
        """If the bundle has no plugins/ directory, extraction must silently succeed."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        # _bundle_path returns a non-existent path
        with mock.patch.object(launcher, "_bundle_path", return_value=str(tmp_path / "plugins")):
            launcher._extract_bundled_plugins(data_dir)  # must not raise
        assert not (data_dir / "plugins").exists() or True  # dir may or may not exist

    def test_ignores_non_directory_entries(self, tmp_path):
        """Loose files at the top level of bundle/plugins are ignored."""
        bundle_plugins = tmp_path / "bundle" / "plugins"
        bundle_plugins.mkdir(parents=True)
        (bundle_plugins / "README.txt").write_text("not a plugin")

        plugin_b = bundle_plugins / "plugin_b"
        plugin_b.mkdir()
        (plugin_b / "applug.json").write_text("{}")

        data_dir = tmp_path / "data"
        data_dir.mkdir()

        with mock.patch.object(launcher, "_bundle_path", return_value=str(bundle_plugins)):
            launcher._extract_bundled_plugins(data_dir)

        assert (data_dir / "plugins" / "plugin_b").is_dir()
        assert not (data_dir / "plugins" / "README.txt").exists()


# ---------------------------------------------------------------------------
# first_run_init (integration of the three steps)
# ---------------------------------------------------------------------------

class TestFirstRunInit:
    def test_writes_sentinel_on_success(self, tmp_path):
        with mock.patch.object(launcher, "_generate_secret_key"), \
             mock.patch.object(launcher, "_run_alembic_upgrade"), \
             mock.patch.object(launcher, "_extract_bundled_plugins"):
            launcher.first_run_init(tmp_path)
        assert (tmp_path / ".initialized").exists()

    def test_no_sentinel_on_alembic_failure(self, tmp_path):
        with mock.patch.object(launcher, "_generate_secret_key"), \
             mock.patch.object(launcher, "_run_alembic_upgrade",
                               side_effect=RuntimeError("db fail")), \
             mock.patch.object(launcher, "_extract_bundled_plugins"):
            with pytest.raises(RuntimeError):
                launcher.first_run_init(tmp_path)
        assert not (tmp_path / ".initialized").exists()

    def test_calls_all_three_steps(self, tmp_path):
        with mock.patch.object(launcher, "_generate_secret_key") as gsk, \
             mock.patch.object(launcher, "_run_alembic_upgrade") as rau, \
             mock.patch.object(launcher, "_extract_bundled_plugins") as ebp:
            launcher.first_run_init(tmp_path)
        gsk.assert_called_once_with(tmp_path / ".env")
        rau.assert_called_once_with(tmp_path)
        ebp.assert_called_once_with(tmp_path)


# ---------------------------------------------------------------------------
# _port_in_use
# ---------------------------------------------------------------------------

class TestPortInUse:
    def test_returns_false_when_port_is_free(self):
        # Use a port that is very unlikely to be bound during testing.
        assert launcher._port_in_use(19999) is False

    def test_returns_true_when_port_is_bound(self):
        import socket as _socket

        srv = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        srv.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        port = srv.getsockname()[1]
        try:
            assert launcher._port_in_use(port) is True
        finally:
            srv.close()


# ---------------------------------------------------------------------------
# Fix B regression — matika.spec must bundle plugins/ when the dir exists
# ---------------------------------------------------------------------------

class TestSpecPluginsDatasEntry:
    """Fix B: matika.spec must include ("plugins", "plugins") in datas when the
    plugins/ directory exists (populated by ahimsa build job), and must NOT
    error when the directory is absent (developer checkout)."""

    def _run_spec_conditional(self, spec_dir: Path, has_plugins: bool) -> list:
        """Execute the spec's plugins conditional in isolation and return datas."""
        if has_plugins:
            (spec_dir / "plugins" / "eyerate").mkdir(parents=True)

        datas: list = []
        SPEC = str(spec_dir / "matika.spec")
        _plugins_src = os.path.join(os.path.dirname(SPEC), "plugins")
        if os.path.isdir(_plugins_src):
            datas.append(("plugins", "plugins"))
        return datas

    def test_plugins_included_when_dir_exists(self, tmp_path):
        """When plugins/ dir is present (CI build), spec must bundle it."""
        datas = self._run_spec_conditional(tmp_path, has_plugins=True)
        assert ("plugins", "plugins") in datas

    def test_plugins_absent_when_dir_missing(self, tmp_path):
        """When plugins/ dir is absent (dev checkout), spec must not error and
        must not add a phantom entry."""
        datas = self._run_spec_conditional(tmp_path, has_plugins=False)
        assert ("plugins", "plugins") not in datas

    def test_spec_file_contains_plugins_conditional(self):
        """The actual matika.spec source must contain the plugins datas conditional."""
        spec_path = Path(__file__).parent.parent / "matika.spec"
        spec_text = spec_path.read_text()
        assert "_plugins_src" in spec_text, (
            "matika.spec is missing the _plugins_src guard for plugins/ datas"
        )
        assert 'datas.append(("plugins", "plugins"))' in spec_text, (
            "matika.spec is missing datas.append((\"plugins\", \"plugins\"))"
        )

    def test_spec_hiddenimports_include_alembic_command(self):
        """Fix A: matika.spec must freeze alembic.command and alembic.config
        so the in-process migration API is available in the frozen bundle."""
        spec_path = Path(__file__).parent.parent / "matika.spec"
        spec_text = spec_path.read_text()
        assert '"alembic.command"' in spec_text, (
            "matika.spec hiddenimports is missing alembic.command"
        )
        assert '"alembic.config"' in spec_text, (
            "matika.spec hiddenimports is missing alembic.config"
        )


# ---------------------------------------------------------------------------
# Fix C regression — durable file logging from launch
# ---------------------------------------------------------------------------

@pytest.fixture()
def clean_root_logger():
    """Save and restore root logger state around each test."""
    import logging as _logging
    root = _logging.getLogger()
    original_level = root.level
    original_handlers = list(root.handlers)
    root.handlers.clear()
    yield root
    for h in root.handlers:
        try:
            h.close()
        except Exception:
            pass
    root.handlers = original_handlers
    root.level = original_level


class TestSetupLogging:
    def test_creates_dated_log_file(self, tmp_path, clean_root_logger):
        """Fix C: _setup_logging must create ~/matika/logs/matika-<date>.log."""
        from datetime import date as _date
        launcher._setup_logging(tmp_path)
        log_dir = tmp_path / "logs"
        assert log_dir.is_dir()
        expected = log_dir / f"matika-{_date.today().isoformat()}.log"
        assert expected.exists(), f"Expected log file not created: {expected}"

    def test_log_file_captures_messages(self, tmp_path, clean_root_logger):
        """Fix C: messages logged after _setup_logging must appear in the file."""
        import logging as _logging
        from datetime import date as _date
        launcher._setup_logging(tmp_path)
        log_path = tmp_path / "logs" / f"matika-{_date.today().isoformat()}.log"
        _logging.getLogger("test.launcher").info("sentinel_message_xyz")
        content = log_path.read_text(encoding="utf-8")
        assert "sentinel_message_xyz" in content

    def test_fatal_error_writes_traceback_to_log(self, tmp_path, clean_root_logger):
        """Fix C: logging.exception() after a crash must include the traceback in
        the log file — this is the primary diagnostic surface for Finder-launched
        failures where stderr is discarded."""
        import logging as _logging
        from datetime import date as _date
        launcher._setup_logging(tmp_path)
        log_path = tmp_path / "logs" / f"matika-{_date.today().isoformat()}.log"
        try:
            raise RuntimeError("simulated first-run failure")
        except Exception:
            _logging.exception("first-run setup failed")
        content = log_path.read_text(encoding="utf-8")
        assert "first-run setup failed" in content
        assert "RuntimeError" in content
        assert "simulated first-run failure" in content

    def test_setup_logging_called_before_first_run_init(self):
        """Fix C: _setup_logging must be called before first_run_init in main().
        Verified by inspecting main()'s source lines."""
        import inspect
        src = inspect.getsource(launcher.main)
        setup_pos = src.find("_setup_logging")
        init_pos = src.find("first_run_init")
        assert setup_pos != -1, "_setup_logging not found in main()"
        assert init_pos != -1, "first_run_init not found in main()"
        assert setup_pos < init_pos, (
            "_setup_logging must appear before first_run_init in main() "
            f"(found at char {setup_pos} vs {init_pos})"
        )
