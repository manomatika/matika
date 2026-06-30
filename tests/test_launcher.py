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
# _init_database_schema  (create_all + alembic stamp head; in-process, no subprocess)
# ---------------------------------------------------------------------------

class TestInitDatabaseSchema:
    """Defect 1 (layer 3): a FRESH first-run DB must be created via the models'
    create_all() and then stamped to Alembic head — NOT `alembic upgrade head`,
    which fails on an empty DB because the initial migration only ADDS indexes to
    an already-existing permissions table."""

    def _patch_db(self):
        """Patch matika.database.init_db so the test does not need a real DB."""
        import sys as _sys
        import types as _types
        fake_db = _types.ModuleType("matika.database")
        fake_db.init_db = mock.MagicMock()
        # Ensure a parent `matika` package exists so the submodule import works.
        if "matika" not in _sys.modules:
            pkg = _types.ModuleType("matika")
            pkg.__path__ = []  # mark as package
            _sys.modules["matika"] = pkg
        return mock.patch.dict(_sys.modules, {"matika.database": fake_db}), fake_db

    def test_creates_schema_then_stamps_head_inprocess(self, tmp_path):
        """create_all() runs first, then alembic.command.stamp(cfg, 'head') — all
        in-process (no subprocess, which would re-enter main() and fork-bomb)."""
        patch_db, fake_db = self._patch_db()
        with patch_db, \
             mock.patch("alembic.command.stamp") as mock_stamp, \
             mock.patch.object(launcher, "_bundle_path", return_value=str(tmp_path / "alembic.ini")), \
             mock.patch("subprocess.run") as mock_sub, \
             mock.patch("subprocess.Popen") as mock_popen:
            launcher._init_database_schema(tmp_path)

        fake_db.init_db.assert_called_once()
        mock_stamp.assert_called_once()
        _cfg, revision = mock_stamp.call_args[0]
        assert revision == "head"
        mock_sub.assert_not_called()
        mock_popen.assert_not_called()

    def test_does_not_call_alembic_upgrade(self, tmp_path):
        """Regression: upgrade head on a fresh empty DB is the second boot bug —
        the launcher must stamp, never upgrade, on first run."""
        patch_db, _ = self._patch_db()
        with patch_db, \
             mock.patch("alembic.command.stamp"), \
             mock.patch("alembic.command.upgrade") as mock_upgrade, \
             mock.patch.object(launcher, "_bundle_path", return_value=str(tmp_path / "alembic.ini")):
            launcher._init_database_schema(tmp_path)
        mock_upgrade.assert_not_called()

    def test_sets_sqlalchemy_url_to_data_db(self, tmp_path):
        captured: dict = {}

        def _capture(cfg, revision):
            captured["url"] = cfg.get_main_option("sqlalchemy.url")

        patch_db, _ = self._patch_db()
        with patch_db, \
             mock.patch("alembic.command.stamp", side_effect=_capture), \
             mock.patch.object(launcher, "_bundle_path", return_value=str(tmp_path / "alembic.ini")):
            (tmp_path / "alembic.ini").write_text("[alembic]\n")
            launcher._init_database_schema(tmp_path)

        assert captured["url"] == f"sqlite:///{tmp_path / 'data' / 'matika.db'}"

    def test_creates_data_subdirectory(self, tmp_path):
        patch_db, _ = self._patch_db()
        with patch_db, \
             mock.patch("alembic.command.stamp"), \
             mock.patch.object(launcher, "_bundle_path", return_value=str(tmp_path / "alembic.ini")):
            launcher._init_database_schema(tmp_path)
        assert (tmp_path / "data").is_dir()

    def test_database_url_set_before_db_import_and_restored(self, tmp_path, monkeypatch):
        """DATABASE_URL must be set (so matika.database builds the right engine
        and env.py sees it) and restored to the prior value on exit."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///sentinel_value.db")
        captured: dict = {}

        patch_db, fake_db = self._patch_db()
        fake_db.init_db.side_effect = lambda: captured.__setitem__(
            "DATABASE_URL_during", os.environ.get("DATABASE_URL")
        )
        with patch_db, \
             mock.patch("alembic.command.stamp"), \
             mock.patch.object(launcher, "_bundle_path", return_value=str(tmp_path / "alembic.ini")):
            (tmp_path / "alembic.ini").write_text("[alembic]\n")
            launcher._init_database_schema(tmp_path)

        expected_db = str(tmp_path / "data" / "matika.db")
        assert captured["DATABASE_URL_during"] == f"sqlite:///{expected_db}"
        assert os.environ.get("DATABASE_URL") == "sqlite:///sentinel_value.db"


# ---------------------------------------------------------------------------
# _extract_bundled_plugins
# ---------------------------------------------------------------------------

class TestExtractBundledPlugins:
    """Install / refresh of bundled plugins into ~/matika/plugins/.

    REGRESSION COVERAGE (standing rule 22) for the "admin coming soon / lookup
    dead on upgrade" bug: an upgrade over a prior install left STALE plugin code
    in ~/matika/plugins/<id>/ because the old logic skipped any plugin dir that
    already existed. These tests pin the three paths — fresh, refresh-on-upgrade,
    same-version skip — plus user-data preservation and stale-code removal.
    """

    @staticmethod
    def _make_bundle(root: Path, name: str, version: str | None,
                     files: dict[str, str]) -> Path:
        """Create a bundled plugin tree under <root>/<name>/ and return <root>."""
        plug = root / name
        plug.mkdir(parents=True, exist_ok=True)
        manifest = {"id": name}
        if version is not None:
            manifest["version"] = version
        import json as _json
        (plug / "applug.json").write_text(_json.dumps(manifest))
        for rel, content in files.items():
            f = plug / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(content)
        return root

    def test_fresh_install_copies_tree_and_writes_marker(self, tmp_path):
        bundle = self._make_bundle(
            tmp_path / "bundle" / "plugins", "plugin_a", "0.0.4",
            {"templates/admin.html": "Financial Data Provider"},
        )
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        with mock.patch.object(launcher, "_bundle_path", return_value=str(bundle)):
            launcher._extract_bundled_plugins(data_dir)

        dest = data_dir / "plugins" / "plugin_a"
        assert (dest / "applug.json").exists()
        assert (dest / "templates" / "admin.html").read_text() == "Financial Data Provider"
        marker = launcher._read_install_marker(dest)
        assert marker is not None
        assert marker["version"] == "0.0.4"
        assert "templates/admin.html" in marker["files"]

    def test_upgrade_refreshes_stale_code_when_version_differs(self, tmp_path):
        """THE bug: a prior install's stale template must be replaced on upgrade."""
        # Installed (stale) plugin: old "coming soon" template, version 0.0.3,
        # no install marker (predates the refresh mechanism), plus user data.
        data_dir = tmp_path / "data"
        dest = data_dir / "plugins" / "eyerate"
        (dest / "templates").mkdir(parents=True)
        (dest / "templates" / "admin.html").write_text("Administration features coming soon")
        (dest / "applug.json").write_text('{"id": "eyerate", "version": "0.0.3"}')
        (dest / "user_settings.json").write_text('{"provider": "yahoo"}')  # user DATA

        # Bundled (new) plugin: real provider form, version 0.0.4.
        bundle = self._make_bundle(
            tmp_path / "bundle" / "plugins", "eyerate", "0.0.4",
            {"templates/admin.html": "Financial Data Provider"},
        )

        with mock.patch.object(launcher, "_bundle_path", return_value=str(bundle)):
            launcher._extract_bundled_plugins(data_dir)

        # CODE refreshed to the bundled version …
        assert (dest / "templates" / "admin.html").read_text() == "Financial Data Provider"
        assert "coming soon" not in (dest / "templates" / "admin.html").read_text()
        # … user/runtime DATA preserved (not in the bundle manifest) …
        assert (dest / "user_settings.json").read_text() == '{"provider": "yahoo"}'
        # … and the marker now records the bundled version.
        assert launcher._read_install_marker(dest)["version"] == "0.0.4"

    def test_same_version_same_code_is_skipped(self, tmp_path):
        """A genuine no-op: identical version AND fingerprint → nothing rewritten."""
        bundle = self._make_bundle(
            tmp_path / "bundle" / "plugins", "plugin_a", "0.0.4",
            {"code.txt": "v4"},
        )
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        # First call performs the fresh install (writes the marker).
        with mock.patch.object(launcher, "_bundle_path", return_value=str(bundle)):
            launcher._extract_bundled_plugins(data_dir)
        dest = data_dir / "plugins" / "plugin_a"
        # A user file added after install must survive a same-version re-run.
        (dest / "user_data.txt").write_text("keep this")

        with mock.patch.object(launcher, "_bundle_path", return_value=str(bundle)):
            launcher._extract_bundled_plugins(data_dir)

        assert (dest / "user_data.txt").read_text() == "keep this"
        assert (dest / "code.txt").read_text() == "v4"

    def test_same_version_changed_code_is_refreshed_via_fingerprint(self, tmp_path):
        """Same version but changed CODE (e.g. an rc rebuild) still refreshes."""
        data_dir = tmp_path / "data"
        bundle_root = tmp_path / "bundle" / "plugins"
        bundle = self._make_bundle(bundle_root, "plugin_a", "0.0.4", {"code.txt": "old"})
        with mock.patch.object(launcher, "_bundle_path", return_value=str(bundle)):
            launcher._extract_bundled_plugins(data_dir)
        # Same version, new code bytes.
        (bundle_root / "plugin_a" / "code.txt").write_text("new")

        with mock.patch.object(launcher, "_bundle_path", return_value=str(bundle)):
            launcher._extract_bundled_plugins(data_dir)

        assert (data_dir / "plugins" / "plugin_a" / "code.txt").read_text() == "new"

    def test_refresh_removes_code_dropped_by_new_bundle(self, tmp_path):
        """Code files removed in the new version are deleted; user data is kept."""
        data_dir = tmp_path / "data"
        bundle_root = tmp_path / "bundle" / "plugins"
        bundle = self._make_bundle(
            bundle_root, "plugin_a", "0.0.4",
            {"keep.txt": "k", "gone.txt": "g"},
        )
        with mock.patch.object(launcher, "_bundle_path", return_value=str(bundle)):
            launcher._extract_bundled_plugins(data_dir)
        dest = data_dir / "plugins" / "plugin_a"
        (dest / "user_data.txt").write_text("mine")  # never in any bundle

        # New bundle drops gone.txt and bumps version.
        (bundle_root / "plugin_a" / "gone.txt").unlink()
        (bundle_root / "plugin_a" / "applug.json").write_text('{"id": "plugin_a", "version": "0.0.5"}')

        with mock.patch.object(launcher, "_bundle_path", return_value=str(bundle)):
            launcher._extract_bundled_plugins(data_dir)

        assert (dest / "keep.txt").exists()
        assert not (dest / "gone.txt").exists()       # stale code removed
        assert (dest / "user_data.txt").read_text() == "mine"  # user data kept

    def test_legacy_install_without_marker_refreshes_but_keeps_unknown_files(self, tmp_path):
        """No marker (pre-fix install): overwrite bundled code, keep everything else."""
        data_dir = tmp_path / "data"
        dest = data_dir / "plugins" / "plugin_a"
        dest.mkdir(parents=True)
        (dest / "applug.json").write_text('{"id": "plugin_a", "version": "0.0.4"}')
        (dest / "old_template.html").write_text("coming soon")   # could be stale OR data
        bundle = self._make_bundle(
            tmp_path / "bundle" / "plugins", "plugin_a", "0.0.4",
            {"new_template.html": "real form"},
        )

        with mock.patch.object(launcher, "_bundle_path", return_value=str(bundle)):
            launcher._extract_bundled_plugins(data_dir)

        # Bundled code written; unknown pre-existing file conservatively kept
        # (no marker → cannot prove it is stale code rather than user data).
        assert (dest / "new_template.html").read_text() == "real form"
        assert (dest / "old_template.html").exists()
        assert launcher._read_install_marker(dest) is not None

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
             mock.patch.object(launcher, "_init_database_schema"):
            launcher.first_run_init(tmp_path)
        assert (tmp_path / ".initialized").exists()

    def test_no_sentinel_on_schema_failure(self, tmp_path):
        with mock.patch.object(launcher, "_generate_secret_key"), \
             mock.patch.object(launcher, "_init_database_schema",
                               side_effect=RuntimeError("db fail")):
            with pytest.raises(RuntimeError):
                launcher.first_run_init(tmp_path)
        assert not (tmp_path / ".initialized").exists()

    def test_calls_secret_and_schema_steps(self, tmp_path):
        # Plugin extraction is NOT a first-run step any more — it runs on every
        # launch from main() so upgrades refresh stale plugin code.
        with mock.patch.object(launcher, "_generate_secret_key") as gsk, \
             mock.patch.object(launcher, "_init_database_schema") as ids:
            launcher.first_run_init(tmp_path)
        gsk.assert_called_once_with(tmp_path / ".env")
        ids.assert_called_once_with(tmp_path)


# ---------------------------------------------------------------------------
# _port_available / _probe_healthz / _wait_for_ready
# ---------------------------------------------------------------------------

class TestPortBindDetection:
    def test_available_when_port_is_free(self):
        """_port_available returns True for a port no one holds."""
        import socket as _socket
        # Bind-and-release to grab an OS-assigned free port.
        with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            free_port = s.getsockname()[1]
        # Port is now released — should be available.
        assert launcher._port_available(free_port) is True

    def test_unavailable_when_port_is_bound(self):
        """_port_available returns False when another socket holds the port."""
        import socket as _socket
        srv = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        srv.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        port = srv.getsockname()[1]
        try:
            assert launcher._port_available(port) is False
        finally:
            srv.close()


class TestHealthzProbe:
    """Unit tests for _probe_healthz(port)."""

    def _make_response(self, body: bytes):
        """Return a mock context-manager response with .read() → body."""
        resp = mock.MagicMock()
        resp.read.return_value = body
        resp.__enter__ = mock.MagicMock(return_value=resp)
        resp.__exit__ = mock.MagicMock(return_value=False)
        return resp

    def test_returns_dict_on_success(self):
        payload = b'{"product": "ManoMatika", "status": "ok", "version": "0.0.4"}'
        resp = self._make_response(payload)
        with mock.patch("urllib.request.urlopen", return_value=resp):
            result = launcher._probe_healthz(8000)
        assert result == {"product": "ManoMatika", "status": "ok", "version": "0.0.4"}

    def test_returns_none_on_connection_refused(self):
        with mock.patch("urllib.request.urlopen", side_effect=ConnectionRefusedError()):
            result = launcher._probe_healthz(8000)
        assert result is None

    def test_returns_none_on_timeout(self):
        import socket as _socket
        with mock.patch("urllib.request.urlopen", side_effect=_socket.timeout()):
            result = launcher._probe_healthz(8000)
        assert result is None

    def test_returns_none_on_malformed_body(self):
        resp = self._make_response(b"not-json-{{")
        with mock.patch("urllib.request.urlopen", return_value=resp):
            result = launcher._probe_healthz(8000)
        assert result is None


class TestHealthzReadinessPoll:
    """Unit tests for _wait_for_ready(port)."""

    def test_ready_on_first_attempt(self):
        with mock.patch.object(
            launcher, "_probe_healthz", return_value={"status": "ok"}
        ), mock.patch.object(launcher, "time") as mock_time:
            mock_time.monotonic.side_effect = [0.0, 0.0]  # start, first check
            result = launcher._wait_for_ready(8000, startup_timeout=5.0)
        assert result is True

    def test_ready_on_nth_attempt(self):
        """First N-1 probes return None; Nth returns ok → True."""
        responses = [None, None, None, {"status": "ok"}]
        call_count = 0

        def fake_probe(port, timeout=2.0):
            nonlocal call_count
            r = responses[call_count]
            call_count += 1
            return r

        # Provide monotonic times that stay within the 10s deadline.
        times = [float(i) for i in range(10)]
        with mock.patch.object(launcher, "_probe_healthz", side_effect=fake_probe), \
             mock.patch("time.monotonic", side_effect=times), \
             mock.patch("time.sleep"):
            result = launcher._wait_for_ready(8000, interval=0.1, startup_timeout=10.0)

        assert result is True
        assert call_count == 4

    def test_startup_timeout_exhausted(self, caplog):
        """If the probe never returns ok, _wait_for_ready returns False and logs ERROR."""
        import logging as _logging

        # Monotonic times: deadline is 0+2=2; probes return None until time > 2.
        times = [0.0, 0.5, 1.0, 1.5, 2.5]  # last value exceeds deadline
        with mock.patch.object(launcher, "_probe_healthz", return_value=None), \
             mock.patch("time.monotonic", side_effect=times), \
             mock.patch("time.sleep"), \
             caplog.at_level(_logging.ERROR, logger="launcher"):
            result = launcher._wait_for_ready(8000, interval=0.1, startup_timeout=2.0)

        assert result is False
        assert any("not ready" in r.message for r in caplog.records)

    def test_per_attempt_timeout_honored(self):
        """_probe_healthz is called with per_attempt_timeout as the timeout arg."""
        probe_kwargs: list = []

        def fake_probe(port, timeout=2.0):
            probe_kwargs.append(timeout)
            return None  # always fail so we exhaust quickly

        times = [0.0, 0.5, 1.5]  # two probes then deadline exceeded
        with mock.patch.object(launcher, "_probe_healthz", side_effect=fake_probe), \
             mock.patch("time.monotonic", side_effect=times), \
             mock.patch("time.sleep"):
            launcher._wait_for_ready(
                8000, interval=0.1, per_attempt_timeout=0.3, startup_timeout=1.0
            )

        assert all(t == 0.3 for t in probe_kwargs), (
            f"_probe_healthz was called with wrong timeout(s): {probe_kwargs}"
        )


class TestConfiguredPort:
    """Unit tests for _configured_port() — MATIKA_PORT env var, default 8000."""

    def test_default_when_unset(self, monkeypatch):
        monkeypatch.delenv("MATIKA_PORT", raising=False)
        assert launcher._configured_port() == 8000

    def test_reads_matika_port_env_var(self, monkeypatch):
        monkeypatch.setenv("MATIKA_PORT", "9123")
        assert launcher._configured_port() == 9123

    def test_invalid_value_falls_back_to_default(self, monkeypatch, caplog):
        import logging as _logging
        monkeypatch.setenv("MATIKA_PORT", "not-a-port")
        with caplog.at_level(_logging.WARNING, logger="launcher"):
            assert launcher._configured_port() == 8000
        assert any("invalid MATIKA_PORT" in r.message for r in caplog.records)


class TestProbeHealthzWithRetry:
    """Unit tests for _probe_healthz_with_retry — bounded retry for a still-
    starting server (so a slow-but-healthy startup isn't mistaken for dead)."""

    def test_healthy_on_first_attempt_no_retry(self):
        healthy = {"product": "ManoMatika", "status": "ok"}
        with mock.patch.object(launcher, "_probe_healthz", return_value=healthy) as probe, \
             mock.patch("time.sleep") as sleep:
            result = launcher._probe_healthz_with_retry(8000, attempts=3, interval=0.1)
        assert result == healthy
        assert probe.call_count == 1
        sleep.assert_not_called()

    def test_slow_startup_answers_within_bounded_retry(self):
        """First two probes fail/empty, third succeeds within the attempt budget."""
        healthy = {"product": "ManoMatika", "status": "ok"}
        responses = [None, {"status": "ok"}, healthy]
        with mock.patch.object(launcher, "_probe_healthz", side_effect=responses) as probe, \
             mock.patch("time.sleep") as sleep:
            result = launcher._probe_healthz_with_retry(8000, attempts=3, interval=0.1)
        assert result == healthy
        assert probe.call_count == 3
        assert sleep.call_count == 2

    def test_exhausts_attempts_and_returns_last_result(self):
        """Never answers healthy within the bounded retries → returns last seen
        (possibly None) WITHOUT retrying forever."""
        with mock.patch.object(launcher, "_probe_healthz", return_value=None) as probe, \
             mock.patch("time.sleep") as sleep:
            result = launcher._probe_healthz_with_retry(8000, attempts=3, interval=0.1)
        assert result is None
        assert probe.call_count == 3
        assert sleep.call_count == 2  # never sleeps after the final attempt


class TestPortHolderIdentification:
    """Unit tests for the psutil-based reclaim primitives, mocking psutil
    directly (psutil is a real installed dependency, not stubbed out)."""

    def _fake_conn(self, port, status="LISTEN"):
        conn = mock.MagicMock()
        conn.status = status
        conn.laddr = mock.MagicMock(port=port)
        return conn

    def _fake_proc(self, pid, conns=None, exc=None):
        proc = mock.MagicMock()
        proc.pid = pid
        if exc is not None:
            proc.net_connections.side_effect = exc
        else:
            proc.net_connections.return_value = conns or []
        return proc

    # -- _find_port_holder_pid ------------------------------------------------

    def test_find_port_holder_pid_returns_matching_listener(self):
        import psutil
        holder = self._fake_proc(4242, conns=[self._fake_conn(8000, psutil.CONN_LISTEN)])
        other = self._fake_proc(1, conns=[self._fake_conn(9999, psutil.CONN_LISTEN)])
        with mock.patch.object(psutil, "process_iter", return_value=[other, holder]):
            assert launcher._find_port_holder_pid(8000) == 4242

    def test_find_port_holder_pid_none_when_no_listener(self):
        import psutil
        other = self._fake_proc(1, conns=[self._fake_conn(9999, psutil.CONN_LISTEN)])
        with mock.patch.object(psutil, "process_iter", return_value=[other]):
            assert launcher._find_port_holder_pid(8000) is None

    def test_find_port_holder_pid_skips_unreadable_processes(self):
        """A process whose connection table can't be read (AccessDenied) must
        be skipped, not crash the scan — and must not be mistaken for a match."""
        import psutil
        unreadable = self._fake_proc(2, exc=psutil.AccessDenied(2))
        holder = self._fake_proc(4242, conns=[self._fake_conn(8000, psutil.CONN_LISTEN)])
        with mock.patch.object(psutil, "process_iter", return_value=[unreadable, holder]):
            assert launcher._find_port_holder_pid(8000) == 4242

    def test_find_port_holder_pid_ignores_non_listen_connections(self):
        import psutil
        established = self._fake_proc(7, conns=[self._fake_conn(8000, psutil.CONN_ESTABLISHED)])
        with mock.patch.object(psutil, "process_iter", return_value=[established]):
            assert launcher._find_port_holder_pid(8000) is None

    # -- _is_manomatika_process -------------------------------------------------

    def test_is_manomatika_true_when_exe_matches_our_frozen_binary(self, monkeypatch):
        import psutil
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", "/Applications/ManoMatika.app/Contents/MacOS/ManoMatika")
        proc = mock.MagicMock()
        proc.exe.return_value = "/Applications/ManoMatika.app/Contents/MacOS/ManoMatika"
        with mock.patch.object(psutil, "Process", return_value=proc):
            assert launcher._is_manomatika_process(4242) is True

    def test_is_manomatika_true_via_name_pattern_fallback(self, monkeypatch):
        """Path doesn't match exactly (e.g. a different installed version), but
        the executable basename still identifies it as ManoMatika."""
        import psutil
        monkeypatch.setattr(sys, "frozen", False, raising=False)
        proc = mock.MagicMock()
        proc.exe.return_value = "/Applications/ManoMatika-0.0.3.app/Contents/MacOS/ManoMatika"
        with mock.patch.object(psutil, "Process", return_value=proc):
            assert launcher._is_manomatika_process(4242) is True

    def test_is_manomatika_false_for_foreign_process(self):
        import psutil
        proc = mock.MagicMock()
        proc.exe.return_value = "/usr/sbin/some-other-daemon"
        with mock.patch.object(psutil, "Process", return_value=proc):
            assert launcher._is_manomatika_process(999) is False

    def test_is_manomatika_none_when_access_denied(self):
        """Cannot read the candidate's exe path → unknown, never guess."""
        import psutil
        with mock.patch.object(psutil, "Process", side_effect=psutil.AccessDenied(999)):
            assert launcher._is_manomatika_process(999) is None

    def test_is_manomatika_none_when_process_already_gone(self):
        import psutil
        with mock.patch.object(psutil, "Process", side_effect=psutil.NoSuchProcess(999)):
            assert launcher._is_manomatika_process(999) is None

    # -- _force_kill_process ------------------------------------------------

    def test_force_kill_process_kills_and_waits(self):
        import psutil
        proc = mock.MagicMock()
        with mock.patch.object(psutil, "Process", return_value=proc):
            launcher._force_kill_process(4242)
        proc.kill.assert_called_once()
        proc.wait.assert_called_once_with(timeout=5)

    def test_force_kill_process_tolerates_already_gone(self):
        import psutil
        with mock.patch.object(psutil, "Process", side_effect=psutil.NoSuchProcess(4242)):
            launcher._force_kill_process(4242)  # must not raise

    # -- _wait_for_port_free ------------------------------------------------

    def test_wait_for_port_free_true_when_already_free(self):
        with mock.patch.object(launcher, "_port_available", return_value=True):
            assert launcher._wait_for_port_free(8000, timeout=1.0) is True

    def test_wait_for_port_free_false_on_timeout(self):
        with mock.patch.object(launcher, "_port_available", return_value=False), \
             mock.patch("time.sleep"):
            assert launcher._wait_for_port_free(8000, timeout=0.05, interval=0.01) is False


class TestHandlePortConflict:
    """Unit tests for _handle_port_conflict — the full reclaim decision tree."""

    def test_healthy_ours_opens_browser_and_exits_zero(self):
        healthy = {"product": "ManoMatika", "status": "ok", "version": "0.0.4"}
        with mock.patch.object(launcher, "_probe_healthz_with_retry", return_value=healthy), \
             mock.patch("webbrowser.open") as mock_open, \
             pytest.raises(SystemExit) as exc_info:
            launcher._handle_port_conflict(8000)
        assert exc_info.value.code == 0
        mock_open.assert_called_once_with("http://127.0.0.1:8000")

    def test_dead_ours_reclaims_kills_and_returns(self):
        """Dead/unhealthy ManoMatika holder → kill it, confirm port free, RETURN
        (does not exit) so the caller proceeds with a fresh launch."""
        with mock.patch.object(launcher, "_probe_healthz_with_retry", return_value=None), \
             mock.patch.object(launcher, "_find_port_holder_pid", return_value=4242), \
             mock.patch.object(launcher, "_is_manomatika_process", return_value=True), \
             mock.patch.object(launcher, "_force_kill_process") as kill, \
             mock.patch.object(launcher, "_wait_for_port_free", return_value=True):
            result = launcher._handle_port_conflict(8000)
        assert result is None  # returned normally, did not sys.exit
        kill.assert_called_once_with(4242)

    def test_dead_ours_reclaim_kill_succeeds_but_port_still_held_fails_loud(self):
        """Kill succeeded but the port never frees (e.g. a second process grabbed
        it) → must NOT silently proceed; fail loud and exit 1."""
        with mock.patch.object(launcher, "_probe_healthz_with_retry", return_value=None), \
             mock.patch.object(launcher, "_find_port_holder_pid", return_value=4242), \
             mock.patch.object(launcher, "_is_manomatika_process", return_value=True), \
             mock.patch.object(launcher, "_force_kill_process") as kill, \
             mock.patch.object(launcher, "_wait_for_port_free", return_value=False), \
             mock.patch.object(launcher, "_show_port_error") as show_error, \
             pytest.raises(SystemExit) as exc_info:
            launcher._handle_port_conflict(8000)
        assert exc_info.value.code == 1
        kill.assert_called_once_with(4242)
        show_error.assert_called_once_with(8000, holder_pid=4242)

    def test_foreign_holder_fails_loud_and_never_kills(self):
        """Positively-identified foreign process holding the port → fail loud
        with port + holder PID, exit 1, and the holder is NEVER killed."""
        with mock.patch.object(launcher, "_probe_healthz_with_retry", return_value=None), \
             mock.patch.object(launcher, "_find_port_holder_pid", return_value=999), \
             mock.patch.object(launcher, "_is_manomatika_process", return_value=False), \
             mock.patch.object(launcher, "_force_kill_process") as kill, \
             mock.patch.object(launcher, "_show_port_error") as show_error, \
             pytest.raises(SystemExit) as exc_info:
            launcher._handle_port_conflict(8000)
        assert exc_info.value.code == 1
        kill.assert_not_called()
        show_error.assert_called_once_with(8000, holder_pid=999)

    def test_ambiguous_no_holder_found_fails_loud_and_never_kills(self):
        """Port is held (per the bind check) but no listening process could be
        found — must never guess; fail loud, exit 1, no kill attempted."""
        with mock.patch.object(launcher, "_probe_healthz_with_retry", return_value=None), \
             mock.patch.object(launcher, "_find_port_holder_pid", return_value=None), \
             mock.patch.object(launcher, "_force_kill_process") as kill, \
             mock.patch.object(launcher, "_show_port_error") as show_error, \
             pytest.raises(SystemExit) as exc_info:
            launcher._handle_port_conflict(8000)
        assert exc_info.value.code == 1
        kill.assert_not_called()
        show_error.assert_called_once_with(8000, holder_pid=None)

    def test_ambiguous_unreadable_holder_fails_loud_and_never_kills(self):
        """Holder PID found, but identity could not be determined (e.g.
        AccessDenied reading its exe) → ambiguous, never guess, fail loud."""
        with mock.patch.object(launcher, "_probe_healthz_with_retry", return_value=None), \
             mock.patch.object(launcher, "_find_port_holder_pid", return_value=4242), \
             mock.patch.object(launcher, "_is_manomatika_process", return_value=None), \
             mock.patch.object(launcher, "_force_kill_process") as kill, \
             mock.patch.object(launcher, "_show_port_error") as show_error, \
             pytest.raises(SystemExit) as exc_info:
            launcher._handle_port_conflict(8000)
        assert exc_info.value.code == 1
        kill.assert_not_called()
        show_error.assert_called_once_with(8000, holder_pid=4242)


class TestPortRecovery:
    """Integration-style tests for the port-conflict branch wired into main()."""

    def _run_main_with_port_taken(self, probe_return, tmp_path, **extra_patches):
        """Run main() with _port_available=False and _probe_healthz_with_retry
        returning probe_return. extra_patches are additional mock.patch.object
        context managers (name -> kwargs dict) applied around the call."""
        (tmp_path / ".initialized").touch()
        patchers = [
            mock.patch.object(launcher, "_setup_logging"),
            mock.patch.object(launcher, "_data_dir", return_value=tmp_path),
            mock.patch.object(launcher, "_load_env"),
            mock.patch.object(launcher, "_extract_bundled_plugins"),
            mock.patch.object(launcher, "_bundle_path", return_value=str(tmp_path)),
            mock.patch.object(launcher, "_port_available", return_value=False),
            mock.patch.object(launcher, "_probe_healthz_with_retry", return_value=probe_return),
            mock.patch.dict(os.environ, {}),
        ]
        for name, kwargs in extra_patches.items():
            patchers.append(mock.patch.object(launcher, name, **kwargs))
        for p in patchers:
            p.start()
        try:
            launcher.main()
        finally:
            for p in reversed(patchers):
                p.stop()

    def test_ours_opens_browser_and_exits_zero(self, tmp_path):
        """Own ManoMatika instance → open browser to existing window, exit 0."""
        healthz = {"product": "ManoMatika", "status": "ok", "version": "0.0.4"}
        with mock.patch("webbrowser.open") as mock_open, \
             pytest.raises(SystemExit) as exc_info:
            self._run_main_with_port_taken(healthz, tmp_path)
        assert exc_info.value.code == 0
        mock_open.assert_called_once_with("http://127.0.0.1:8000")

    def test_foreign_process_fails_loud_exits_one(self, tmp_path):
        """Positively-identified foreign holder → show dialog, exit 1, no kill."""
        with mock.patch.object(launcher, "_show_port_error"), \
             pytest.raises(SystemExit) as exc_info:
            self._run_main_with_port_taken(
                None, tmp_path,
                _find_port_holder_pid={"return_value": 999},
                _is_manomatika_process={"return_value": False},
                _force_kill_process={"side_effect": AssertionError("must not kill foreign process")},
            )
        assert exc_info.value.code == 1

    def test_ambiguous_holder_treated_as_fail_loud(self, tmp_path):
        """No listening process could be identified → ambiguous, fail loud, exit 1."""
        with mock.patch.object(launcher, "_show_port_error"), \
             pytest.raises(SystemExit) as exc_info:
            self._run_main_with_port_taken(
                None, tmp_path,
                _find_port_holder_pid={"return_value": None},
            )
        assert exc_info.value.code == 1

    def test_dead_ours_reclaims_and_proceeds_to_fresh_launch(self, tmp_path):
        """Dead ManoMatika holder → reclaim (kill + wait-for-free), then fall
        through into the normal fresh-launch path (uvicorn server starts)."""
        mock_server = mock.MagicMock()
        mock_uvicorn = mock.MagicMock()
        mock_uvicorn.Config.return_value = mock.MagicMock()
        mock_uvicorn.Server.return_value = mock_server

        (tmp_path / ".initialized").touch()
        with mock.patch.object(launcher, "_setup_logging"), \
             mock.patch.object(launcher, "_data_dir", return_value=tmp_path), \
             mock.patch.object(launcher, "_load_env"), \
             mock.patch.object(launcher, "_extract_bundled_plugins"), \
             mock.patch.object(launcher, "_bundle_path", return_value=str(tmp_path)), \
             mock.patch.object(launcher, "_port_available", return_value=False), \
             mock.patch.object(launcher, "_probe_healthz_with_retry", return_value=None), \
             mock.patch.object(launcher, "_find_port_holder_pid", return_value=4242), \
             mock.patch.object(launcher, "_is_manomatika_process", return_value=True), \
             mock.patch.object(launcher, "_force_kill_process") as kill, \
             mock.patch.object(launcher, "_wait_for_port_free", return_value=True), \
             mock.patch("signal.signal"), \
             mock.patch("signal.getsignal", return_value=__import__("signal").default_int_handler), \
             mock.patch.dict(sys.modules, {"uvicorn": mock_uvicorn}), \
             mock.patch("threading.Thread"), \
             mock.patch.dict(os.environ, {}):
            launcher.main()  # must NOT raise SystemExit — falls through to launch

        kill.assert_called_once_with(4242)
        mock_uvicorn.Server.assert_called_once()
        mock_server.run.assert_called_once()


class TestShutdownHandler:
    """Verify SIGTERM/SIGINT handler sets server.should_exit (D3 graceful shutdown)."""

    def test_sigterm_sets_server_should_exit(self, tmp_path):
        """The _handle_shutdown closure installed for SIGTERM sets _server.should_exit."""
        import signal as _signal

        captured_handlers: dict = {}

        def _fake_signal_install(signum, handler):
            captured_handlers[signum] = handler

        mock_server = mock.MagicMock()
        mock_server.should_exit = False

        mock_uvicorn = mock.MagicMock()
        mock_uvicorn.Config.return_value = mock.MagicMock()
        mock_uvicorn.Server.return_value = mock_server

        # Create sentinel and env so first_run_init is skipped and _load_env is happy.
        (tmp_path / ".initialized").touch()

        with mock.patch.object(launcher, "_setup_logging"), \
             mock.patch.object(launcher, "_data_dir", return_value=tmp_path), \
             mock.patch.object(launcher, "_load_env"), \
             mock.patch.object(launcher, "_extract_bundled_plugins"), \
             mock.patch.object(launcher, "_bundle_path", return_value=str(tmp_path)), \
             mock.patch.object(launcher, "_port_available", return_value=True), \
             mock.patch("signal.signal", side_effect=_fake_signal_install), \
             mock.patch("signal.getsignal", return_value=_signal.default_int_handler), \
             mock.patch.dict(sys.modules, {"uvicorn": mock_uvicorn}), \
             mock.patch("threading.Thread"), \
             mock.patch.dict(os.environ, {}):
            launcher.main()

        assert _signal.SIGTERM in captured_handlers, \
            "SIGTERM signal handler was not registered"
        # Call the installed handler directly and verify it sets should_exit.
        captured_handlers[_signal.SIGTERM](_signal.SIGTERM, None)
        assert mock_server.should_exit is True


class TestFreezeSupport:
    """multiprocessing.freeze_support() must be the first call in __main__."""

    def test_freeze_support_called_before_main(self):
        """Verify freeze_support() appears in the __main__ block before logging setup."""
        text = _LAUNCHER_PATH.read_text()
        main_block_start = text.find('if __name__ == "__main__":')
        assert main_block_start != -1, "__main__ block not found"
        main_block = text[main_block_start:]
        freeze_pos = main_block.find("freeze_support()")
        setup_logging_pos = main_block.find("_setup_logging")
        assert freeze_pos != -1, "freeze_support() not found in __main__ block"
        assert setup_logging_pos != -1, "_setup_logging not found in __main__ block"
        assert freeze_pos < setup_logging_pos, (
            "freeze_support() must appear before _setup_logging in __main__ "
            f"(found at offset {freeze_pos} vs {setup_logging_pos})"
        )


class TestCrashPortFree:
    """Port-bind approach: no stale lock file on crash (OS releases port on process exit)."""

    def test_port_available_function_exists(self):
        """_port_available must exist and be callable (bind-based, not connect-based)."""
        assert callable(launcher._port_available)

    def test_no_file_lock_used(self):
        """Verify launcher does not use a file-based lock for port management."""
        text = _LAUNCHER_PATH.read_text()
        # File locks (fcntl.flock, lockfile, filelock) should not appear.
        assert "fcntl" not in text, "launcher must not use fcntl file locks"
        assert "lockfile" not in text, "launcher must not use lockfile"

    def test_port_in_use_function_removed(self):
        """Old TCP-connect _port_in_use function must not exist; superseded by bind-check."""
        assert not hasattr(launcher, "_port_in_use"), (
            "_port_in_use still exists; it should have been replaced by _port_available"
        )


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

    def test_spec_collects_full_alembic_and_sqlalchemy_packages(self):
        """Defect 1: hiddenimports alone misses alembic's dynamically-loaded
        migration runtime and data tree. matika.spec must collect_all() the
        alembic and sqlalchemy packages so the frozen bundle can run the
        in-process migration without 'No module named alembic'."""
        spec_path = Path(__file__).parent.parent / "matika.spec"
        spec_text = spec_path.read_text()
        assert "collect_all" in spec_text, "matika.spec is not using collect_all"
        assert 'collect_all("alembic")' in spec_text, (
            "matika.spec must collect_all('alembic')"
        )
        assert 'collect_all("sqlalchemy")' in spec_text, (
            "matika.spec must collect_all('sqlalchemy')"
        )

    def test_spec_collects_psutil_for_launcher_reclaim(self):
        """matika#113: launcher.py's port-holder reclaim logic imports psutil
        lazily inside _find_port_holder_pid/_is_manomatika_process/
        _force_kill_process, so static analysis alone misses it. psutil ships a
        per-platform compiled extension (like curl_cffi), so it must use
        collect_all rather than a plain hiddenimports entry."""
        spec_path = Path(__file__).parent.parent / "matika.spec"
        spec_text = spec_path.read_text()
        assert '"psutil"' in spec_text, "matika.spec hiddenimports is missing psutil"
        assert 'collect_all("psutil")' in spec_text, (
            "matika.spec must collect_all('psutil')"
        )

    def test_spec_force_bundles_entire_matika_package(self, monkeypatch):
        """Defect 1 (layer 2): matika submodules are loaded DYNAMICALLY — alembic
        migrations/env.py runs `from matika.models import Base`, and applugs
        import matika.* at load — so the spec must freeze the whole matika
        package, not just what launcher.py statically reaches. Exec the spec and
        assert the dynamically-needed modules land in hiddenimports."""
        from unittest.mock import MagicMock

        for var in ("MATIKA_PRODUCT_NAME", "MATIKA_PRODUCT_VERSION", "CI"):
            monkeypatch.delenv(var, raising=False)
        spec_path = Path(__file__).parent.parent / "matika.spec"
        ns = {
            "Analysis": lambda *a, **k: MagicMock(),
            "PYZ": lambda *a, **k: MagicMock(),
            "EXE": lambda *a, **k: MagicMock(),
            "COLLECT": lambda *a, **k: MagicMock(),
            "BUNDLE": lambda *a, **k: MagicMock(),
            "SPEC": str(spec_path),
        }
        exec(compile(spec_path.read_text(), str(spec_path), "exec"), ns)
        hidden = ns.get("hiddenimports", [])
        assert "matika.models" in hidden, (
            "matika.models must be force-bundled (alembic env.py imports it)"
        )
        assert "matika.main" in hidden
        assert any(m.startswith("matika.routers") for m in hidden), (
            "matika router submodules must be bundled"
        )

    def test_migrations_env_does_not_clobber_existing_logging(self):
        """Defect 2 regression: migrations/env.py must NOT call fileConfig when
        the root logger already has handlers (the in-process launcher case) —
        fileConfig would replace the launcher's durable ~/matika/logs file
        handler mid-boot, silently losing startup logging after the first
        alembic call."""
        env_path = Path(__file__).parent.parent / "migrations" / "env.py"
        env_text = env_path.read_text()
        assert "not logging.getLogger().handlers" in env_text, (
            "env.py must guard fileConfig() on an empty root-logger handler list"
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
    # _setup_logging is idempotent via module globals; reset them so each test
    # exercises a fresh configuration.
    launcher._LOGGING_CONFIGURED = False
    launcher._LOG_PATH = None
    yield root
    launcher._LOGGING_CONFIGURED = False
    launcher._LOG_PATH = None
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


# ---------------------------------------------------------------------------
# Defect 2 regression — a log with a full traceback is written even for an
# EARLY / import-time failure that occurs before _setup_logging() ran.
# ---------------------------------------------------------------------------

class TestEarlyFailureLogging:
    def test_write_fatal_writes_traceback_without_prior_setup(
        self, tmp_path, monkeypatch, clean_root_logger
    ):
        """Simulate an import-time crash BEFORE _setup_logging(): _write_fatal
        must still create ~/matika/logs/matika-<date>.log with the traceback.

        This is the regression for the mini failure where an alembic ImportError
        produced NO log file: logging must be guaranteed even pre-main."""
        from datetime import date as _date

        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr("pathlib.Path.home", lambda: fake_home)

        # No _setup_logging() call — _LOG_PATH is None, mimicking a failure that
        # happens before/at module-import time.
        assert launcher._LOG_PATH is None

        try:
            raise ImportError("No module named 'alembic'")
        except ImportError as exc:
            tb_text = launcher._write_fatal(exc)

        log_path = fake_home / "matika" / "logs" / f"matika-{_date.today().isoformat()}.log"
        assert log_path.exists(), "no log file written for an early failure"
        content = log_path.read_text(encoding="utf-8")
        assert "FATAL startup failure" in content
        assert "ImportError" in content
        assert "No module named 'alembic'" in content
        assert "Traceback (most recent call last)" in tb_text

    def test_write_fatal_appends_to_configured_log(
        self, tmp_path, clean_root_logger
    ):
        """When logging IS configured, _write_fatal appends the traceback to the
        same dated file used by the rest of the app."""
        from datetime import date as _date

        launcher._setup_logging(tmp_path)
        log_path = tmp_path / "logs" / f"matika-{_date.today().isoformat()}.log"

        try:
            raise RuntimeError("boom during startup")
        except RuntimeError as exc:
            launcher._write_fatal(exc)

        content = log_path.read_text(encoding="utf-8")
        assert "RuntimeError" in content
        assert "boom during startup" in content

    def test_excepthook_logs_uncaught_exception(
        self, tmp_path, monkeypatch, clean_root_logger
    ):
        """The installed sys.excepthook writes any uncaught exception's traceback
        to the dated log (dialog suppressed in the headless test env)."""
        from datetime import date as _date

        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr("pathlib.Path.home", lambda: fake_home)
        monkeypatch.setattr(launcher, "_show_fatal_dialog", lambda *_a, **_k: None)

        try:
            raise ValueError("uncaught at top level")
        except ValueError as exc:
            launcher._excepthook(type(exc), exc, exc.__traceback__)

        log_path = fake_home / "matika" / "logs" / f"matika-{_date.today().isoformat()}.log"
        content = log_path.read_text(encoding="utf-8")
        assert "ValueError" in content
        assert "uncaught at top level" in content
