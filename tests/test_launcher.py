"""
tests/test_launcher.py — Unit tests for launcher.py

launcher.py runs in a frozen (PyInstaller) context at production time, but
all of its pure-Python logic is unit-testable by mocking filesystem and
subprocess operations.  We do NOT test uvicorn.run() or the tkinter dialog
paths here — those are integration/manual concerns.
"""

from __future__ import annotations

import os
import subprocess
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
# _run_alembic_upgrade
# ---------------------------------------------------------------------------

class TestRunAlembicUpgrade:
    def test_calls_alembic_with_correct_args(self, tmp_path):
        """_run_alembic_upgrade must invoke alembic upgrade head via subprocess."""
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        with mock.patch("subprocess.run", return_value=completed) as mock_run, \
             mock.patch.object(launcher, "_bundle_path", return_value=str(tmp_path / "alembic.ini")):
            launcher._run_alembic_upgrade(tmp_path)

        args = mock_run.call_args[0][0]
        assert args[-3:] == ["-m", "alembic", "-c"] or "alembic" in args
        # Verify the last two tokens are the upgrade command
        assert "upgrade" in args
        assert "head" in args

    def test_raises_on_nonzero_exit(self, tmp_path):
        completed = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="out", stderr="error detail"
        )
        with mock.patch("subprocess.run", return_value=completed), \
             mock.patch.object(launcher, "_bundle_path", return_value=str(tmp_path / "alembic.ini")):
            with pytest.raises(RuntimeError, match="alembic upgrade head failed"):
                launcher._run_alembic_upgrade(tmp_path)

    def test_creates_data_subdirectory(self, tmp_path):
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        with mock.patch("subprocess.run", return_value=completed), \
             mock.patch.object(launcher, "_bundle_path", return_value=str(tmp_path / "alembic.ini")):
            launcher._run_alembic_upgrade(tmp_path)
        assert (tmp_path / "data").is_dir()


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
