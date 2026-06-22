"""
Tests for the core matika_screens.json data file.

Validates that the file loads cleanly via ScreenLoaderService, that every entry
has the correct structure, and that expected screen_ids are present.
"""
import json
import os
import pytest

from matika.core.screen_loader import (
    ScreenLoaderService,
    SUPPORTED_SCHEMA,
    ALLOWED_VERBS,
)

# Derive canonical paths from this test file's location so the test always
# points at the worktree's own copy of the screens directory — regardless of
# which Python environment or editable-install path is active.
#
# Layout:  <worktree>/tests/test_matika_screens_data.py
#          <worktree>/src/matika/screens/matika_screens.json
_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_WORKTREE_ROOT = os.path.dirname(_TESTS_DIR)

SCREENS_DIR = os.path.join(_WORKTREE_ROOT, "src", "matika", "screens")
SCREENS_FILE = os.path.join(SCREENS_DIR, "matika_screens.json")

# Placeholder: there is no plugins dir in the core framework.
_NO_PLUGINS_DIR = os.path.join(_WORKTREE_ROOT, "src", "matika", "applug_plugins")


class TestMatikaSceensFileLoads:
    """ScreenLoaderService can parse matika_screens.json without errors."""

    def test_load_screens_returns_without_exception(self):
        """load_screens() completes without raising any exception."""
        loader = ScreenLoaderService(SCREENS_DIR, _NO_PLUGINS_DIR)
        result = loader.load_screens()
        assert result is not None

    def test_core_key_present(self):
        """The 'core' key is present in the result (file was found and parsed)."""
        loader = ScreenLoaderService(SCREENS_DIR, _NO_PLUGINS_DIR)
        result = loader.load_screens()
        assert "core" in result, (
            "'core' key missing — matika_screens.json may not have been found "
            f"in {SCREENS_DIR}"
        )

    def test_core_list_is_non_empty(self):
        """The 'core' list has at least one entry."""
        loader = ScreenLoaderService(SCREENS_DIR, _NO_PLUGINS_DIR)
        result = loader.load_screens()
        assert len(result["core"]) > 0


class TestEntryTypes:
    """Every entry in 'core' has a valid 'type' field."""

    def _get_entries(self):
        loader = ScreenLoaderService(SCREENS_DIR, _NO_PLUGINS_DIR)
        return loader.load_screens()["core"]

    def test_every_entry_has_a_type(self):
        for entry in self._get_entries():
            assert "type" in entry, (
                f"Entry '{entry.get('screen_id')}' is missing the 'type' field"
            )

    def test_every_type_is_valid(self):
        valid_types = {"screen", "not_a_screen"}
        for entry in self._get_entries():
            assert entry["type"] in valid_types, (
                f"Entry '{entry.get('screen_id')}' has unknown type '{entry['type']}'"
            )


class TestScreenEntryStructure:
    """Every 'screen' entry has required markers and steps."""

    def _get_screen_entries(self):
        loader = ScreenLoaderService(SCREENS_DIR, _NO_PLUGINS_DIR)
        return [e for e in loader.load_screens()["core"] if e.get("type") == "screen"]

    def test_every_screen_has_markers(self):
        for entry in self._get_screen_entries():
            assert "markers" in entry, (
                f"Screen entry '{entry.get('screen_id')}' is missing 'markers'"
            )
            assert isinstance(entry["markers"], list), (
                f"Screen entry '{entry.get('screen_id')}' 'markers' must be a list"
            )
            assert len(entry["markers"]) > 0, (
                f"Screen entry '{entry.get('screen_id')}' 'markers' must be non-empty"
            )

    def test_every_screen_has_steps_list(self):
        for entry in self._get_screen_entries():
            assert "steps" in entry, (
                f"Screen entry '{entry.get('screen_id')}' is missing 'steps'"
            )
            assert isinstance(entry["steps"], list), (
                f"Screen entry '{entry.get('screen_id')}' 'steps' must be a list"
            )

    def test_every_screen_step_has_valid_verb(self):
        for entry in self._get_screen_entries():
            for step in entry.get("steps", []):
                verb = step.get("verb")
                assert verb in ALLOWED_VERBS, (
                    f"Screen entry '{entry.get('screen_id')}' step has "
                    f"unknown verb '{verb}'"
                )

    def test_every_screen_has_at_least_a_navigate_step(self):
        for entry in self._get_screen_entries():
            verbs = [s.get("verb") for s in entry.get("steps", [])]
            assert "navigate" in verbs, (
                f"Screen entry '{entry.get('screen_id')}' has no 'navigate' step"
            )


class TestNotAScreenEntryStructure:
    """Every 'not_a_screen' entry has a non-empty reason."""

    def _get_not_a_screen_entries(self):
        loader = ScreenLoaderService(SCREENS_DIR, _NO_PLUGINS_DIR)
        return [
            e for e in loader.load_screens()["core"]
            if e.get("type") == "not_a_screen"
        ]

    def test_every_not_a_screen_has_reason(self):
        for entry in self._get_not_a_screen_entries():
            assert "reason" in entry, (
                f"not_a_screen entry '{entry.get('screen_id')}' is missing 'reason'"
            )
            assert isinstance(entry["reason"], str) and entry["reason"].strip(), (
                f"not_a_screen entry '{entry.get('screen_id')}' 'reason' "
                f"must be a non-empty string"
            )


class TestExpectedScreenIds:
    """Known screen_ids required by issue #85 are present."""

    def _get_ids(self):
        loader = ScreenLoaderService(SCREENS_DIR, _NO_PLUGINS_DIR)
        return {e["screen_id"] for e in loader.load_screens()["core"]}

    def test_home_present(self):
        assert "home" in self._get_ids()

    def test_login_present(self):
        assert "login" in self._get_ids()

    def test_admin_users_present(self):
        assert "admin_users" in self._get_ids()

    def test_admin_roles_present(self):
        assert "admin_roles" in self._get_ids()

    def test_admin_permissions_present(self):
        assert "admin_permissions" in self._get_ids()

    def test_system_settings_present(self):
        assert "system_settings" in self._get_ids()

    def test_admin_data_import_present(self):
        assert "admin_data_import" in self._get_ids()

    def test_admin_data_export_present(self):
        assert "admin_data_export" in self._get_ids()

    def test_change_password_present(self):
        assert "change_password" in self._get_ids()

    def test_user_settings_present(self):
        assert "user_settings" in self._get_ids()


class TestRawSchemaVersion:
    """The raw JSON file declares schema_version '1.0'."""

    def test_schema_version_is_1_0(self):
        with open(SCREENS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data.get("schema_version") == SUPPORTED_SCHEMA, (
            f"matika_screens.json schema_version is '{data.get('schema_version')}', "
            f"expected '{SUPPORTED_SCHEMA}'"
        )


class TestNoDuplicateScreenIds:
    """All screen_ids across the file are unique."""

    def test_no_duplicate_ids(self):
        loader = ScreenLoaderService(SCREENS_DIR, _NO_PLUGINS_DIR)
        entries = loader.load_screens()["core"]
        ids = [e.get("screen_id") for e in entries if e.get("screen_id")]
        assert len(ids) == len(set(ids)), (
            f"Duplicate screen_ids found: "
            f"{[sid for sid in ids if ids.count(sid) > 1]}"
        )
