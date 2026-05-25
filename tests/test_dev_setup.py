"""
Unit tests for scripts/dev_setup.py.

All tests use tmp_path fixtures and never touch the real plugins/ directory
or the real plugins.dev.json file.
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Load the script as a module without running main()
# ---------------------------------------------------------------------------

def _load_dev_setup():
    script_path = Path(__file__).resolve().parent.parent / "scripts" / "dev_setup.py"
    spec = importlib.util.spec_from_file_location("dev_setup", script_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def dev_setup():
    return _load_dev_setup()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_plugin(base: Path, name: str, *, menu: bool = True) -> Path:
    """Create a minimal valid plugin directory.

    Plugins use the consolidated `*_menus.json` (plural) format with optional
    top-level `application` / `roles` sections — see matika CLAUDE.md's
    "AppLug contract". `dev_setup.py` validates presence of a file matching
    `*_menus.json`; it does not parse the contents.
    """
    p = base / name
    p.mkdir(parents=True)
    (p / "applug.json").write_text(json.dumps({"id": name, "version": "1.0"}))
    if menu:
        (p / f"{name}_menus.json").write_text(
            json.dumps({"schema_version": "1.0"})
        )
    return p


def _make_config(path: Path, plugins: list) -> None:
    path.write_text(json.dumps({"plugins": plugins}))


# ---------------------------------------------------------------------------
# process_plugin — unit tests
# ---------------------------------------------------------------------------

class TestProcessPlugin:

    def test_valid_plugin_creates_symlink(self, tmp_path, dev_setup, monkeypatch):
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        plugin_src = _make_plugin(tmp_path / "repos", "myplugin")

        monkeypatch.setattr(dev_setup, "PLUGINS_DIR", plugins_dir)
        monkeypatch.setattr(dev_setup, "REPO_ROOT", tmp_path)

        result = dev_setup.process_plugin(str(plugin_src))

        assert result == "linked"
        link = plugins_dir / "myplugin"
        assert link.is_symlink()
        assert link.resolve() == plugin_src

    def test_idempotent_second_run_returns_already_ok(self, tmp_path, dev_setup, monkeypatch):
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        plugin_src = _make_plugin(tmp_path / "repos", "myplugin")

        monkeypatch.setattr(dev_setup, "PLUGINS_DIR", plugins_dir)
        monkeypatch.setattr(dev_setup, "REPO_ROOT", tmp_path)

        dev_setup.process_plugin(str(plugin_src))           # first run
        result = dev_setup.process_plugin(str(plugin_src))  # second run

        assert result == "already_ok"
        assert (plugins_dir / "myplugin").is_symlink()

    def test_nonexistent_path_returns_skipped(self, tmp_path, dev_setup, monkeypatch):
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        monkeypatch.setattr(dev_setup, "PLUGINS_DIR", plugins_dir)
        monkeypatch.setattr(dev_setup, "REPO_ROOT", tmp_path)

        result = dev_setup.process_plugin("/definitely/does/not/exist")

        assert result == "skipped"
        assert list(plugins_dir.iterdir()) == []

    def test_missing_applug_json_returns_skipped(self, tmp_path, dev_setup, monkeypatch):
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        bad_plugin = tmp_path / "repos" / "badplugin"
        bad_plugin.mkdir(parents=True)
        # No applug.json

        monkeypatch.setattr(dev_setup, "PLUGINS_DIR", plugins_dir)
        monkeypatch.setattr(dev_setup, "REPO_ROOT", tmp_path)

        result = dev_setup.process_plugin(str(bad_plugin))

        assert result == "skipped"
        assert not (plugins_dir / "badplugin").exists()

    def test_missing_menu_json_returns_skipped(self, tmp_path, dev_setup, monkeypatch):
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        # Plugin has applug.json but no *_menu.json
        plugin_src = _make_plugin(tmp_path / "repos", "nomenu", menu=False)

        monkeypatch.setattr(dev_setup, "PLUGINS_DIR", plugins_dir)
        monkeypatch.setattr(dev_setup, "REPO_ROOT", tmp_path)

        result = dev_setup.process_plugin(str(plugin_src))

        assert result == "skipped"
        assert not (plugins_dir / "nomenu").exists()

    def test_broken_symlink_user_declines_returns_skipped(
        self, tmp_path, dev_setup, monkeypatch
    ):
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        plugin_src = _make_plugin(tmp_path / "repos", "myplugin")

        # Create a symlink that points to a different (wrong) location
        wrong_target = tmp_path / "repos" / "wrongplace"
        wrong_target.mkdir()
        link = plugins_dir / "myplugin"
        link.symlink_to(wrong_target)

        monkeypatch.setattr(dev_setup, "PLUGINS_DIR", plugins_dir)
        monkeypatch.setattr(dev_setup, "REPO_ROOT", tmp_path)
        monkeypatch.setattr("builtins.input", lambda _: "n")  # user says no

        result = dev_setup.process_plugin(str(plugin_src))

        assert result == "skipped"
        assert link.resolve() == wrong_target.resolve()  # unchanged

    def test_broken_symlink_user_accepts_returns_fixed(
        self, tmp_path, dev_setup, monkeypatch
    ):
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        plugin_src = _make_plugin(tmp_path / "repos", "myplugin")

        wrong_target = tmp_path / "repos" / "wrongplace"
        wrong_target.mkdir()
        link = plugins_dir / "myplugin"
        link.symlink_to(wrong_target)

        monkeypatch.setattr(dev_setup, "PLUGINS_DIR", plugins_dir)
        monkeypatch.setattr(dev_setup, "REPO_ROOT", tmp_path)
        monkeypatch.setattr("builtins.input", lambda _: "y")  # user accepts

        result = dev_setup.process_plugin(str(plugin_src))

        assert result == "fixed"
        assert link.resolve() == plugin_src.resolve()


# ---------------------------------------------------------------------------
# main() — integration tests
# ---------------------------------------------------------------------------

class TestMain:

    def _run(self, dev_setup, tmp_path, monkeypatch, config_content=None, **kwargs):
        """Run dev_setup.main() with an isolated filesystem."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir(exist_ok=True)   # safe on repeated calls
        config_file = tmp_path / "plugins.dev.json"
        example_file = tmp_path / "plugins.dev.json.example"

        if config_content is not None:
            config_file.write_text(json.dumps(config_content))

        # Write a real example file so the "copy example" path works
        example_file.write_text(json.dumps({"plugins": []}))

        monkeypatch.setattr(dev_setup, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(dev_setup, "PLUGINS_DIR", plugins_dir)
        monkeypatch.setattr(dev_setup, "CONFIG_FILE", config_file)
        monkeypatch.setattr(dev_setup, "EXAMPLE_FILE", example_file)

        return dev_setup.main()

    def test_valid_config_links_plugin(self, tmp_path, dev_setup, monkeypatch):
        plugin_src = _make_plugin(tmp_path / "repos", "alpha")
        rc = self._run(
            dev_setup, tmp_path, monkeypatch,
            config_content={"plugins": [str(plugin_src)]},
        )
        assert rc == 0
        assert (tmp_path / "plugins" / "alpha").is_symlink()

    def test_idempotent_double_run(self, tmp_path, dev_setup, monkeypatch):
        plugin_src = _make_plugin(tmp_path / "repos", "alpha")
        cfg = {"plugins": [str(plugin_src)]}

        rc1 = self._run(dev_setup, tmp_path, monkeypatch, config_content=cfg)
        rc2 = self._run(dev_setup, tmp_path, monkeypatch, config_content=cfg)

        assert rc1 == 0
        assert rc2 == 0
        assert (tmp_path / "plugins" / "alpha").is_symlink()

    def test_missing_config_copies_example_and_returns_1(
        self, tmp_path, dev_setup, monkeypatch
    ):
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        config_file = tmp_path / "plugins.dev.json"
        example_file = tmp_path / "plugins.dev.json.example"
        example_file.write_text(json.dumps({"plugins": []}))

        monkeypatch.setattr(dev_setup, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(dev_setup, "PLUGINS_DIR", plugins_dir)
        monkeypatch.setattr(dev_setup, "CONFIG_FILE", config_file)
        monkeypatch.setattr(dev_setup, "EXAMPLE_FILE", example_file)

        rc = dev_setup.main()

        assert rc == 1
        assert config_file.exists()  # example was copied

    def test_empty_plugins_array_returns_0(self, tmp_path, dev_setup, monkeypatch):
        rc = self._run(dev_setup, tmp_path, monkeypatch, config_content={"plugins": []})
        assert rc == 0

    def test_nonexistent_path_skipped_no_crash(self, tmp_path, dev_setup, monkeypatch):
        rc = self._run(
            dev_setup, tmp_path, monkeypatch,
            config_content={"plugins": ["/this/path/does/not/exist"]},
        )
        # Exits 1 because no plugins were successfully wired
        assert rc == 1

    def test_missing_applug_json_skipped_no_crash(self, tmp_path, dev_setup, monkeypatch):
        bad = tmp_path / "repos" / "badplugin"
        bad.mkdir(parents=True)
        # No applug.json in this directory

        rc = self._run(
            dev_setup, tmp_path, monkeypatch,
            config_content={"plugins": [str(bad)]},
        )
        assert rc == 1

    def test_missing_menu_json_skipped_no_crash(self, tmp_path, dev_setup, monkeypatch):
        plugin_src = _make_plugin(tmp_path / "repos", "nomenu", menu=False)

        rc = self._run(
            dev_setup, tmp_path, monkeypatch,
            config_content={"plugins": [str(plugin_src)]},
        )
        assert rc == 1
        assert not (tmp_path / "plugins" / "nomenu").exists()

    def test_multiple_plugins_all_linked(self, tmp_path, dev_setup, monkeypatch):
        alpha = _make_plugin(tmp_path / "repos", "alpha")
        beta  = _make_plugin(tmp_path / "repos", "beta")

        rc = self._run(
            dev_setup, tmp_path, monkeypatch,
            config_content={"plugins": [str(alpha), str(beta)]},
        )
        assert rc == 0
        assert (tmp_path / "plugins" / "alpha").is_symlink()
        assert (tmp_path / "plugins" / "beta").is_symlink()

    def test_mix_valid_and_invalid_valid_still_linked(
        self, tmp_path, dev_setup, monkeypatch
    ):
        valid = _make_plugin(tmp_path / "repos", "good")

        rc = self._run(
            dev_setup, tmp_path, monkeypatch,
            config_content={"plugins": [
                "/does/not/exist",
                str(valid),
            ]},
        )
        assert rc == 0  # At least one succeeded
        assert (tmp_path / "plugins" / "good").is_symlink()
