import pytest
import json
import os
from matika.core.screen_loader import (
    ScreenLoaderService,
    SUPPORTED_SCHEMA,
    ALLOWED_VERBS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def write_screens_file(path, screens, schema_version=SUPPORTED_SCHEMA):
    """Write a minimal valid *_screens.json to path."""
    data = {"schema_version": schema_version, "screens": screens}
    path.write_text(json.dumps(data))


def make_screen(screen_id, route="/path", markers=None, steps=None):
    """Build a minimal valid 'screen' entry."""
    return {
        "screen_id": screen_id,
        "type": "screen",
        "route": route,
        "markers": markers if markers is not None else [".main"],
        "steps": steps if steps is not None else [
            {"verb": "navigate", "target": route},
        ],
    }


def make_not_a_screen(screen_id, reason="Internal admin-only page"):
    """Build a minimal valid 'not_a_screen' entry."""
    return {
        "screen_id": screen_id,
        "type": "not_a_screen",
        "route": "/internal",
        "reason": reason,
    }


# ---------------------------------------------------------------------------
# ALLOWED_VERBS constant
# ---------------------------------------------------------------------------

class TestAllowedVerbs:
    def test_all_specified_verbs_present(self):
        expected = {
            "navigate", "fill", "click", "wait_for",
            "assert_present", "assert_absent", "assert_value",
        }
        assert ALLOWED_VERBS == expected

    def test_allowed_verbs_is_frozenset(self):
        assert isinstance(ALLOWED_VERBS, frozenset)


# ---------------------------------------------------------------------------
# Valid schema parse
# ---------------------------------------------------------------------------

class TestValidParse:
    def test_screen_entry_loaded(self, tmp_path):
        """A single valid 'screen' entry is parsed and returned."""
        core_dir = tmp_path / "screens"
        core_dir.mkdir()
        write_screens_file(
            core_dir / "home_screens.json",
            [make_screen("home")],
        )
        loader = ScreenLoaderService(str(core_dir), "/tmp/nonexistent")
        result = loader.load_screens()
        assert "core" in result
        assert len(result["core"]) == 1
        assert result["core"][0]["screen_id"] == "home"
        assert result["core"][0]["type"] == "screen"

    def test_not_a_screen_entry_loaded(self, tmp_path):
        """A 'not_a_screen' entry with a reason is accepted and returned."""
        core_dir = tmp_path / "screens"
        core_dir.mkdir()
        write_screens_file(
            core_dir / "excluded_screens.json",
            [make_not_a_screen("admin_internal")],
        )
        loader = ScreenLoaderService(str(core_dir), "/tmp/nonexistent")
        result = loader.load_screens()
        assert "core" in result
        assert result["core"][0]["screen_id"] == "admin_internal"
        assert result["core"][0]["type"] == "not_a_screen"

    def test_mixed_entries_both_loaded(self, tmp_path):
        """A file with both 'screen' and 'not_a_screen' entries is fully loaded."""
        core_dir = tmp_path / "screens"
        core_dir.mkdir()
        write_screens_file(
            core_dir / "mixed_screens.json",
            [make_screen("dashboard"), make_not_a_screen("admin_only")],
        )
        loader = ScreenLoaderService(str(core_dir), "/tmp/nonexistent")
        result = loader.load_screens()
        ids = [e["screen_id"] for e in result["core"]]
        assert "dashboard" in ids
        assert "admin_only" in ids

    def test_all_allowed_verbs_accepted(self, tmp_path):
        """Each allowed verb is accepted individually."""
        core_dir = tmp_path / "screens"
        core_dir.mkdir()
        for verb in sorted(ALLOWED_VERBS):
            entries = [make_screen(f"s_{verb}", steps=[{"verb": verb, "target": ".x"}])]
            write_screens_file(core_dir / f"{verb}_screens.json", entries)
        loader = ScreenLoaderService(str(core_dir), "/tmp/nonexistent")
        result = loader.load_screens()
        assert "core" in result
        loaded_ids = {e["screen_id"] for e in result["core"]}
        for verb in ALLOWED_VERBS:
            assert f"s_{verb}" in loaded_ids

    def test_empty_steps_list_accepted(self, tmp_path):
        """A 'screen' entry with an empty steps list is valid."""
        core_dir = tmp_path / "screens"
        core_dir.mkdir()
        write_screens_file(
            core_dir / "home_screens.json",
            [make_screen("home", steps=[])],
        )
        loader = ScreenLoaderService(str(core_dir), "/tmp/nonexistent")
        result = loader.load_screens()
        assert result["core"][0]["steps"] == []


# ---------------------------------------------------------------------------
# Duplicate-id rejection (FAIL-LOUD)
# ---------------------------------------------------------------------------

class TestDuplicateIdRejection:
    def test_duplicate_ids_across_sources_raises_runtime_error(self, tmp_path):
        """Duplicate screen_id across two plugin dirs raises RuntimeError at load."""
        plugins_dir = tmp_path / "plugins"
        plugin_a = plugins_dir / "plugin_a"
        plugin_b = plugins_dir / "plugin_b"
        plugin_a.mkdir(parents=True)
        plugin_b.mkdir(parents=True)

        write_screens_file(plugin_a / "plugin_a_screens.json", [make_screen("shared_id")])
        write_screens_file(plugin_b / "plugin_b_screens.json", [make_screen("shared_id")])

        loader = ScreenLoaderService("/tmp/nonexistent", str(plugins_dir))
        with pytest.raises(RuntimeError, match="shared_id"):
            loader.load_screens()

    def test_duplicate_error_names_both_sources(self, tmp_path):
        """RuntimeError message names both conflicting source names."""
        plugins_dir = tmp_path / "plugins"
        plugin_a = plugins_dir / "alpha"
        plugin_b = plugins_dir / "beta"
        plugin_a.mkdir(parents=True)
        plugin_b.mkdir(parents=True)

        write_screens_file(plugin_a / "alpha_screens.json", [make_screen("dup_id")])
        write_screens_file(plugin_b / "beta_screens.json", [make_screen("dup_id")])

        loader = ScreenLoaderService("/tmp/nonexistent", str(plugins_dir))
        with pytest.raises(RuntimeError) as exc_info:
            loader.load_screens()
        msg = str(exc_info.value)
        assert "alpha" in msg
        assert "beta" in msg

    def test_duplicate_ids_within_single_source_raises(self, tmp_path):
        """Duplicate screen_id within the same plugin also raises RuntimeError."""
        plugins_dir = tmp_path / "plugins"
        plugin_dir = plugins_dir / "myplugin"
        plugin_dir.mkdir(parents=True)

        entries = [make_screen("duplicate"), make_screen("duplicate")]
        write_screens_file(plugin_dir / "myplugin_screens.json", entries)

        loader = ScreenLoaderService("/tmp/nonexistent", str(plugins_dir))
        with pytest.raises(RuntimeError, match="duplicate"):
            loader.load_screens()

    def test_core_and_plugin_duplicate_raises(self, tmp_path):
        """Duplicate screen_id between core and a plugin raises RuntimeError."""
        core_dir = tmp_path / "screens"
        core_dir.mkdir()
        plugins_dir = tmp_path / "plugins"
        plugin_dir = plugins_dir / "myplugin"
        plugin_dir.mkdir(parents=True)

        write_screens_file(core_dir / "core_screens.json", [make_screen("shared")])
        write_screens_file(plugin_dir / "myplugin_screens.json", [make_screen("shared")])

        loader = ScreenLoaderService(str(core_dir), str(plugins_dir))
        with pytest.raises(RuntimeError, match="shared"):
            loader.load_screens()


# ---------------------------------------------------------------------------
# Unknown-verb rejection
# ---------------------------------------------------------------------------

class TestUnknownVerbRejection:
    def test_unknown_verb_raises_value_error(self, tmp_path):
        """A step with an unknown verb raises ValueError at parse time."""
        core_dir = tmp_path / "screens"
        core_dir.mkdir()
        write_screens_file(
            core_dir / "home_screens.json",
            [make_screen("home", steps=[{"verb": "teleport", "target": "/x"}])],
        )
        loader = ScreenLoaderService(str(core_dir), "/tmp/nonexistent")
        with pytest.raises(ValueError, match="teleport"):
            loader.load_screens()

    def test_unknown_verb_error_names_bad_verb(self, tmp_path):
        """ValueError message includes the offending verb name."""
        core_dir = tmp_path / "screens"
        core_dir.mkdir()
        write_screens_file(
            core_dir / "home_screens.json",
            [make_screen("home", steps=[{"verb": "explode", "target": "/x"}])],
        )
        loader = ScreenLoaderService(str(core_dir), "/tmp/nonexistent")
        with pytest.raises(ValueError) as exc_info:
            loader.load_screens()
        assert "explode" in str(exc_info.value)

    def test_none_verb_raises_value_error(self, tmp_path):
        """A step with a missing verb key raises ValueError."""
        core_dir = tmp_path / "screens"
        core_dir.mkdir()
        write_screens_file(
            core_dir / "home_screens.json",
            [make_screen("home", steps=[{"target": "/x"}])],  # no "verb" key
        )
        loader = ScreenLoaderService(str(core_dir), "/tmp/nonexistent")
        with pytest.raises(ValueError):
            loader.load_screens()


# ---------------------------------------------------------------------------
# not_a_screen entry validation
# ---------------------------------------------------------------------------

class TestNotAScreenValidation:
    def test_not_a_screen_with_reason_accepted(self, tmp_path):
        """not_a_screen entry with reason is accepted."""
        core_dir = tmp_path / "screens"
        core_dir.mkdir()
        write_screens_file(
            core_dir / "exc_screens.json",
            [make_not_a_screen("excluded", reason="Admin only")],
        )
        loader = ScreenLoaderService(str(core_dir), "/tmp/nonexistent")
        result = loader.load_screens()
        assert result["core"][0]["screen_id"] == "excluded"

    def test_not_a_screen_without_reason_raises_value_error(self, tmp_path):
        """not_a_screen entry missing the reason field raises ValueError."""
        core_dir = tmp_path / "screens"
        core_dir.mkdir()
        entry = {"screen_id": "no_reason", "type": "not_a_screen", "route": "/x"}
        write_screens_file(core_dir / "exc_screens.json", [entry])
        loader = ScreenLoaderService(str(core_dir), "/tmp/nonexistent")
        with pytest.raises(ValueError, match="reason"):
            loader.load_screens()


# ---------------------------------------------------------------------------
# Schema version skipping
# ---------------------------------------------------------------------------

class TestSchemaVersionSkipping:
    def test_wrong_schema_version_is_skipped(self, tmp_path, caplog):
        """File with unsupported schema_version is skipped with a warning."""
        core_dir = tmp_path / "screens"
        core_dir.mkdir()
        data = {"schema_version": "99.0", "screens": [make_screen("s")]}
        (core_dir / "bad_screens.json").write_text(json.dumps(data))

        loader = ScreenLoaderService(str(core_dir), "/tmp/nonexistent")
        result = loader.load_screens()
        assert result == {}

    def test_missing_schema_version_is_skipped(self, tmp_path):
        """File missing schema_version entirely is skipped."""
        core_dir = tmp_path / "screens"
        core_dir.mkdir()
        data = {"screens": [make_screen("s")]}
        (core_dir / "no_version_screens.json").write_text(json.dumps(data))

        loader = ScreenLoaderService(str(core_dir), "/tmp/nonexistent")
        result = loader.load_screens()
        assert result == {}

    def test_valid_and_invalid_schema_files_coexist(self, tmp_path):
        """A valid file and a bad-schema file in the same dir: only valid loaded."""
        core_dir = tmp_path / "screens"
        core_dir.mkdir()
        write_screens_file(core_dir / "good_screens.json", [make_screen("good_screen")])
        bad_data = {"schema_version": "0.0", "screens": [make_screen("bad_screen")]}
        (core_dir / "bad_screens.json").write_text(json.dumps(bad_data))

        loader = ScreenLoaderService(str(core_dir), "/tmp/nonexistent")
        result = loader.load_screens()
        assert "core" in result
        ids = [e["screen_id"] for e in result["core"]]
        assert "good_screen" in ids
        assert "bad_screen" not in ids


# ---------------------------------------------------------------------------
# Invalid JSON is skipped
# ---------------------------------------------------------------------------

class TestInvalidJsonSkipped:
    def test_invalid_json_in_core_is_skipped(self, tmp_path):
        """A malformed JSON file in core_screens_dir is skipped (no crash)."""
        core_dir = tmp_path / "screens"
        core_dir.mkdir()
        (core_dir / "broken_screens.json").write_text("not valid json {{{")

        loader = ScreenLoaderService(str(core_dir), "/tmp/nonexistent")
        result = loader.load_screens()
        assert result == {}

    def test_invalid_json_in_plugin_is_skipped(self, tmp_path):
        """A malformed JSON file in a plugin dir is skipped (no crash)."""
        plugins_dir = tmp_path / "plugins"
        plugin_dir = plugins_dir / "broken_plugin"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "broken_plugin_screens.json").write_text("{{broken")

        loader = ScreenLoaderService("/tmp/nonexistent", str(plugins_dir))
        result = loader.load_screens()
        assert "broken_plugin" not in result


# ---------------------------------------------------------------------------
# Empty / nonexistent directories
# ---------------------------------------------------------------------------

class TestEmptyOrMissingDirs:
    def test_both_dirs_nonexistent_returns_empty(self):
        """load_screens() returns {} when both dirs are missing."""
        loader = ScreenLoaderService(
            "/tmp/nonexistent_core",
            "/tmp/nonexistent_plugins",
        )
        result = loader.load_screens()
        assert result == {}

    def test_empty_core_dir_returns_empty(self, tmp_path):
        """load_screens() returns {} when core_screens_dir is empty."""
        core_dir = tmp_path / "screens"
        core_dir.mkdir()
        loader = ScreenLoaderService(str(core_dir), "/tmp/nonexistent")
        result = loader.load_screens()
        assert result == {}

    def test_empty_plugins_dir_returns_empty(self, tmp_path):
        """load_screens() returns {} when plugins_dir has no subdirs."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        loader = ScreenLoaderService("/tmp/nonexistent", str(plugins_dir))
        result = loader.load_screens()
        assert result == {}

    def test_plugin_dir_without_screens_file_is_skipped(self, tmp_path):
        """Plugin subdirectory without *_screens.json is skipped silently."""
        plugins_dir = tmp_path / "plugins"
        plugin_dir = plugins_dir / "noscreens"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "some_other_file.json").write_text('{}')

        loader = ScreenLoaderService("/tmp/nonexistent", str(plugins_dir))
        result = loader.load_screens()
        assert "noscreens" not in result


# ---------------------------------------------------------------------------
# Cache behaviour
# ---------------------------------------------------------------------------

class TestCacheBehaviour:
    def test_second_call_returns_same_object(self, tmp_path):
        """Second call to load_screens() returns the same object (cache hit)."""
        plugins_dir = tmp_path / "plugins"
        plugin_dir = plugins_dir / "plug"
        plugin_dir.mkdir(parents=True)
        write_screens_file(
            plugin_dir / "plug_screens.json",
            [make_screen("s1")],
        )

        loader = ScreenLoaderService("/tmp/nonexistent", str(plugins_dir))
        first = loader.load_screens()
        second = loader.load_screens()
        assert first is second

    def test_invalidate_cache_forces_reload(self, tmp_path):
        """invalidate_cache() clears the cache so the next call re-reads from disk."""
        plugins_dir = tmp_path / "plugins"
        plugin_dir = plugins_dir / "plug"
        plugin_dir.mkdir(parents=True)
        screens_file = plugin_dir / "plug_screens.json"

        write_screens_file(screens_file, [make_screen("original_screen")])
        loader = ScreenLoaderService("/tmp/nonexistent", str(plugins_dir))
        first = loader.load_screens()
        assert first["plug"][0]["screen_id"] == "original_screen"

        # Mutate on disk and invalidate
        write_screens_file(screens_file, [make_screen("updated_screen")])
        loader.invalidate_cache()

        second = loader.load_screens()
        assert second["plug"][0]["screen_id"] == "updated_screen"

    def test_invalidate_then_empty_returns_empty(self, tmp_path):
        """After invalidation, if files are removed, result is {}."""
        plugins_dir = tmp_path / "plugins"
        plugin_dir = plugins_dir / "plug"
        plugin_dir.mkdir(parents=True)
        screens_file = plugin_dir / "plug_screens.json"

        write_screens_file(screens_file, [make_screen("s1")])
        loader = ScreenLoaderService("/tmp/nonexistent", str(plugins_dir))
        loader.load_screens()

        screens_file.unlink()
        loader.invalidate_cache()
        result = loader.load_screens()
        assert result == {}


# ---------------------------------------------------------------------------
# Plugin discovery
# ---------------------------------------------------------------------------

class TestPluginDiscovery:
    def test_each_plugin_contributes_one_keyed_entry(self, tmp_path):
        """Each plugin dir with a *_screens.json contributes an entry keyed by dir name."""
        plugins_dir = tmp_path / "plugins"
        for name in ("plugin_a", "plugin_b"):
            d = plugins_dir / name
            d.mkdir(parents=True)
            write_screens_file(d / f"{name}_screens.json", [make_screen(f"{name}_home")])

        loader = ScreenLoaderService("/tmp/nonexistent", str(plugins_dir))
        result = loader.load_screens()
        assert "plugin_a" in result
        assert "plugin_b" in result
        assert result["plugin_a"][0]["screen_id"] == "plugin_a_home"
        assert result["plugin_b"][0]["screen_id"] == "plugin_b_home"

    def test_plugin_key_is_directory_name(self, tmp_path):
        """Plugin entries are keyed by the subdirectory name, not the filename."""
        plugins_dir = tmp_path / "plugins"
        plugin_dir = plugins_dir / "eyerate"
        plugin_dir.mkdir(parents=True)
        write_screens_file(plugin_dir / "eyerate_screens.json", [make_screen("er_dash")])

        loader = ScreenLoaderService("/tmp/nonexistent", str(plugins_dir))
        result = loader.load_screens()
        assert "eyerate" in result
        assert result["eyerate"][0]["screen_id"] == "er_dash"

    def test_non_directory_entries_in_plugins_dir_ignored(self, tmp_path):
        """Loose files in plugins_dir are not treated as plugins."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        (plugins_dir / "stray_file.txt").write_text("ignore me")
        plugin_dir = plugins_dir / "real_plugin"
        plugin_dir.mkdir()
        write_screens_file(plugin_dir / "real_plugin_screens.json", [make_screen("real")])

        loader = ScreenLoaderService("/tmp/nonexistent", str(plugins_dir))
        result = loader.load_screens()
        assert "stray_file.txt" not in result
        assert "real_plugin" in result


# ---------------------------------------------------------------------------
# Core dir merge: multiple *_screens.json files → single "core" list
# ---------------------------------------------------------------------------

class TestCoreDirMerge:
    def test_multiple_core_files_merged_into_core_entry(self, tmp_path):
        """Multiple *_screens.json in core_screens_dir are all loaded into 'core'."""
        core_dir = tmp_path / "screens"
        core_dir.mkdir()
        write_screens_file(core_dir / "home_screens.json", [make_screen("home")])
        write_screens_file(core_dir / "admin_screens.json", [make_screen("admin")])

        loader = ScreenLoaderService(str(core_dir), "/tmp/nonexistent")
        result = loader.load_screens()
        assert "core" in result
        ids = {e["screen_id"] for e in result["core"]}
        assert "home" in ids
        assert "admin" in ids

    def test_core_entry_is_flat_list(self, tmp_path):
        """The 'core' value is a flat list, not nested by file."""
        core_dir = tmp_path / "screens"
        core_dir.mkdir()
        write_screens_file(core_dir / "a_screens.json", [make_screen("s_a")])
        write_screens_file(core_dir / "b_screens.json", [make_screen("s_b")])

        loader = ScreenLoaderService(str(core_dir), "/tmp/nonexistent")
        result = loader.load_screens()
        # Should be a list, not a dict or nested list
        assert isinstance(result["core"], list)
        assert all(isinstance(e, dict) for e in result["core"])

    def test_non_screens_files_in_core_dir_ignored(self, tmp_path):
        """Files not matching *_screens.json in core_screens_dir are ignored."""
        core_dir = tmp_path / "screens"
        core_dir.mkdir()
        (core_dir / ".gitkeep").write_text("")
        (core_dir / "README.md").write_text("docs")
        write_screens_file(core_dir / "home_screens.json", [make_screen("home")])

        loader = ScreenLoaderService(str(core_dir), "/tmp/nonexistent")
        result = loader.load_screens()
        assert "core" in result
        assert len(result["core"]) == 1

    def test_core_and_plugins_both_present(self, tmp_path):
        """When both core and plugin screens exist, both appear in result."""
        core_dir = tmp_path / "screens"
        core_dir.mkdir()
        write_screens_file(core_dir / "home_screens.json", [make_screen("core_home")])

        plugins_dir = tmp_path / "plugins"
        plugin_dir = plugins_dir / "myplug"
        plugin_dir.mkdir(parents=True)
        write_screens_file(plugin_dir / "myplug_screens.json", [make_screen("plugin_dash")])

        loader = ScreenLoaderService(str(core_dir), str(plugins_dir))
        result = loader.load_screens()
        assert "core" in result
        assert "myplug" in result
        assert result["core"][0]["screen_id"] == "core_home"
        assert result["myplug"][0]["screen_id"] == "plugin_dash"
