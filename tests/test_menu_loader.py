import pytest
import json
import os
from matika.core.menu_loader import (
    MenuLoaderService,
    menu_is_visible,
    filter_items,
    translate_items,
)
from matika.core.paths import BASE_DIR


# ---------------------------------------------------------------------------
# menu_is_visible
# ---------------------------------------------------------------------------

class TestMenuIsVisible:
    def test_no_roles_visible_to_unauthenticated(self):
        assert menu_is_visible({"id": "m", "type": "Application"}, []) is True

    def test_no_roles_visible_to_any_role(self):
        assert menu_is_visible({"id": "m", "type": "Application"}, ["Admin", "User"]) is True

    def test_required_role_hidden_when_user_has_none(self):
        assert menu_is_visible({"id": "m", "roles": ["Admin"]}, []) is False

    def test_required_role_hidden_when_user_has_different_role(self):
        assert menu_is_visible({"id": "m", "roles": ["Admin"]}, ["User"]) is False

    def test_required_role_visible_when_user_has_it(self):
        assert menu_is_visible({"id": "m", "roles": ["Admin"]}, ["Admin"]) is True

    def test_any_matching_role_is_sufficient(self):
        assert menu_is_visible({"id": "m", "roles": ["Admin", "Manager"]}, ["Manager"]) is True


# ---------------------------------------------------------------------------
# filter_items
# ---------------------------------------------------------------------------

class TestFilterItems:
    def test_link_no_roles_always_passes(self):
        items = [{"type": "Link", "label_key": "k", "href": "/x"}]
        assert filter_items(items, []) == items
        assert filter_items(items, ["Admin"]) == items

    def test_link_with_role_filtered_out_for_non_match(self):
        items = [{"type": "Link", "label_key": "k", "href": "/x", "roles": ["Admin"]}]
        assert filter_items(items, []) == []
        assert filter_items(items, ["User"]) == []

    def test_link_with_role_passes_for_matching_role(self):
        items = [{"type": "Link", "label_key": "k", "href": "/x", "roles": ["Admin"]}]
        result = filter_items(items, ["Admin"])
        assert len(result) == 1
        assert result[0]["href"] == "/x"

    def test_separator_kept_between_two_visible_items(self):
        items = [
            {"type": "Link", "label_key": "a", "href": "/a"},
            {"type": "Separator"},
            {"type": "Link", "label_key": "b", "href": "/b"},
        ]
        result = filter_items(items, [])
        assert len(result) == 3
        assert result[1]["type"] == "Separator"

    def test_trailing_separator_removed(self):
        items = [
            {"type": "Link", "label_key": "a", "href": "/a"},
            {"type": "Separator"},
        ]
        result = filter_items(items, [])
        assert result == [{"type": "Link", "label_key": "a", "href": "/a"}]

    def test_leading_separator_removed(self):
        items = [
            {"type": "Separator"},
            {"type": "Link", "label_key": "a", "href": "/a"},
        ]
        result = filter_items(items, [])
        assert result == [{"type": "Link", "label_key": "a", "href": "/a"}]

    def test_consecutive_separators_collapsed_to_one(self):
        items = [
            {"type": "Link", "label_key": "a", "href": "/a"},
            {"type": "Separator"},
            {"type": "Separator"},
            {"type": "Link", "label_key": "b", "href": "/b"},
        ]
        result = filter_items(items, [])
        separators = [i for i in result if i["type"] == "Separator"]
        assert len(separators) == 1

    def test_separator_removed_when_all_items_after_it_are_filtered(self):
        items = [
            {"type": "Link", "label_key": "a", "href": "/a"},
            {"type": "Separator"},
            {"type": "Link", "label_key": "b", "href": "/b", "roles": ["Admin"]},
        ]
        result = filter_items(items, [])
        assert result == [{"type": "Link", "label_key": "a", "href": "/a"}]

    def test_menu_type_dropped_when_all_children_filtered(self):
        items = [{"type": "Menu", "label_key": "sub", "items": [
            {"type": "Link", "label_key": "x", "href": "/x", "roles": ["Admin"]},
        ]}]
        assert filter_items(items, []) == []

    def test_menu_type_kept_with_visible_children(self):
        items = [{"type": "Menu", "label_key": "sub", "items": [
            {"type": "Link", "label_key": "x", "href": "/x"},
        ]}]
        result = filter_items(items, [])
        assert len(result) == 1
        assert result[0]["type"] == "Menu"
        assert len(result[0]["items"]) == 1

    def test_menu_type_children_filtered_recursively(self):
        items = [{"type": "Menu", "label_key": "sub", "items": [
            {"type": "Link", "label_key": "x", "href": "/x"},
            {"type": "Link", "label_key": "y", "href": "/y", "roles": ["Admin"]},
        ]}]
        result = filter_items(items, [])
        assert len(result) == 1
        assert len(result[0]["items"]) == 1
        assert result[0]["items"][0]["href"] == "/x"


# ---------------------------------------------------------------------------
# translate_items
# ---------------------------------------------------------------------------

class TestTranslateItems:
    def test_link_label_key_resolved(self):
        items = [{"type": "Link", "label_key": "item_home", "href": "/"}]
        result = translate_items(items, {"item_home": "Home"})
        assert result[0]["label"] == "Home"

    def test_missing_key_falls_back_to_key_name(self):
        items = [{"type": "Link", "label_key": "unknown_key", "href": "/x"}]
        result = translate_items(items, {})
        assert result[0]["label"] == "unknown_key"

    def test_label_key_not_in_output(self):
        items = [{"type": "Link", "label_key": "k", "href": "/x"}]
        result = translate_items(items, {"k": "K"})
        assert "label_key" not in result[0]

    def test_roles_stripped_from_output(self):
        items = [{"type": "Link", "label_key": "k", "href": "/x", "roles": ["Admin"]}]
        result = translate_items(items, {"k": "K"})
        assert "roles" not in result[0]

    def test_href_preserved(self):
        items = [{"type": "Link", "label_key": "k", "href": "/dashboard"}]
        result = translate_items(items, {"k": "K"})
        assert result[0]["href"] == "/dashboard"

    def test_open_new_tab_preserved_when_true(self):
        items = [{"type": "Link", "label_key": "k", "href": "/x", "open_new_tab": True}]
        result = translate_items(items, {"k": "K"})
        assert result[0].get("open_new_tab") is True

    def test_open_new_tab_omitted_when_false(self):
        items = [{"type": "Link", "label_key": "k", "href": "/x", "open_new_tab": False}]
        result = translate_items(items, {"k": "K"})
        assert "open_new_tab" not in result[0]

    def test_separator_passes_through_unchanged(self):
        items = [{"type": "Separator"}]
        result = translate_items(items, {})
        assert result == [{"type": "Separator"}]

    def test_menu_items_translated_recursively(self):
        items = [{
            "type": "Menu",
            "label_key": "parent",
            "items": [{"type": "Link", "label_key": "child", "href": "/c"}],
        }]
        t = {"parent": "Parent", "child": "Child"}
        result = translate_items(items, t)
        assert result[0]["label"] == "Parent"
        assert result[0]["items"][0]["label"] == "Child"


# ---------------------------------------------------------------------------
# MenuLoaderService
# ---------------------------------------------------------------------------

class TestMenuLoaderService:
    def test_loads_core_menus(self):
        """load_menus() returns core entry with admin role and system sections from real files."""
        core_dir = os.path.join(BASE_DIR, "src", "matika", "menus")
        loader = MenuLoaderService(core_menus_dir=core_dir, plugins_dir="/tmp/nonexistent")
        result = loader.load_menus()
        assert "core" in result
        assert result["core"]["roles"]["Admin"]["id"] == "core-admin"
        assert result["core"]["system"]["id"] == "core-help"

    def test_loads_plugin_menu_files(self, tmp_path):
        """load_menus() discovers *_menus.json in plugin directories."""
        plugin_dir = tmp_path / "plugins" / "myplugin"
        plugin_dir.mkdir(parents=True)
        menus_data = {
            "schema_version": "1.0",
            "menus": {
                "application": {"id": "my-app", "label_key": "lk", "items": []},
            },
        }
        (plugin_dir / "myplugin_menus.json").write_text(json.dumps(menus_data))

        loader = MenuLoaderService(
            core_menus_dir="/tmp/nonexistent",
            plugins_dir=str(tmp_path / "plugins"),
        )
        result = loader.load_menus()
        assert "myplugin" in result
        assert result["myplugin"]["application"]["id"] == "my-app"

    def test_skips_unsupported_schema(self, tmp_path, caplog):
        """load_menus() skips files with unsupported schema_version."""
        plugin_dir = tmp_path / "plugins" / "bad"
        plugin_dir.mkdir(parents=True)
        bad_data = {"schema_version": "99.0", "menus": {}}
        (plugin_dir / "bad_menus.json").write_text(json.dumps(bad_data))

        loader = MenuLoaderService(
            core_menus_dir="/tmp/nonexistent",
            plugins_dir=str(tmp_path / "plugins"),
        )
        result = loader.load_menus()
        assert "bad" not in result

    def test_skips_invalid_json(self, tmp_path):
        """load_menus() skips files with invalid JSON."""
        plugin_dir = tmp_path / "plugins" / "broken"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "broken_menus.json").write_text("not json {{{")

        loader = MenuLoaderService(
            core_menus_dir="/tmp/nonexistent",
            plugins_dir=str(tmp_path / "plugins"),
        )
        result = loader.load_menus()
        assert "broken" not in result

    def test_missing_directories_return_empty(self):
        """load_menus() returns {} when both directories are missing."""
        loader = MenuLoaderService(
            core_menus_dir="/tmp/nonexistent_core",
            plugins_dir="/tmp/nonexistent_plugins",
        )
        result = loader.load_menus()
        assert result == {}

    def test_load_menus_returns_cached_result_on_second_call(self, tmp_path):
        """Second call to load_menus() returns the same object (cache hit)."""
        plugin_dir = tmp_path / "plugins" / "plug"
        plugin_dir.mkdir(parents=True)
        menus_data = {
            "schema_version": "1.0",
            "menus": {"application": {"id": "p-app", "label_key": "k", "items": []}},
        }
        (plugin_dir / "plug_menus.json").write_text(json.dumps(menus_data))

        loader = MenuLoaderService(
            core_menus_dir="/tmp/nonexistent",
            plugins_dir=str(tmp_path / "plugins"),
        )
        first = loader.load_menus()
        second = loader.load_menus()
        assert first is second  # identical object — no re-read

    def test_invalidate_cache_forces_reload(self, tmp_path):
        """invalidate_cache() clears the cache so the next call re-reads from disk."""
        plugin_dir = tmp_path / "plugins" / "plug"
        plugin_dir.mkdir(parents=True)
        menus_file = plugin_dir / "plug_menus.json"
        menus_data = {
            "schema_version": "1.0",
            "menus": {"application": {"id": "p1", "label_key": "k", "items": []}},
        }
        menus_file.write_text(json.dumps(menus_data))

        loader = MenuLoaderService(
            core_menus_dir="/tmp/nonexistent",
            plugins_dir=str(tmp_path / "plugins"),
        )
        first = loader.load_menus()
        assert first["plug"]["application"]["id"] == "p1"

        # Mutate on disk and invalidate
        menus_data["menus"]["application"]["id"] = "p2"
        menus_file.write_text(json.dumps(menus_data))
        loader.invalidate_cache()

        second = loader.load_menus()
        assert second["plug"]["application"]["id"] == "p2"

    def test_core_admin_section_is_present(self):
        """core entry must have roles.Admin with id 'core-admin' for hub logic."""
        core_dir = os.path.join(BASE_DIR, "src", "matika", "menus")
        loader = MenuLoaderService(core_menus_dir=core_dir, plugins_dir="/tmp/nonexistent")
        result = loader.load_menus()
        admin_entry = result["core"]["roles"].get("Admin")
        assert admin_entry is not None
        assert admin_entry["id"] == "core-admin"

    def test_core_system_section_is_present(self):
        """core entry must have a system section with id 'core-help' for hub ordering logic."""
        core_dir = os.path.join(BASE_DIR, "src", "matika", "menus")
        loader = MenuLoaderService(core_menus_dir=core_dir, plugins_dir="/tmp/nonexistent")
        result = loader.load_menus()
        system = result["core"].get("system")
        assert system is not None
        assert system["id"] == "core-help"

    def test_help_menu_has_separator_between_items(self):
        """core system menu items must include a Separator between Show Log and About."""
        core_dir = os.path.join(BASE_DIR, "src", "matika", "menus")
        loader = MenuLoaderService(core_menus_dir=core_dir, plugins_dir="/tmp/nonexistent")
        result = loader.load_menus()
        system = result["core"]["system"]
        assert system is not None

        item_types = [i["type"] for i in system["items"]]
        assert "Separator" in item_types

        sep_idx = item_types.index("Separator")
        assert sep_idx > 0, "Separator must not be the first item"
        assert sep_idx < len(item_types) - 1, "Separator must not be the last item"

    def test_merges_multiple_core_menu_files(self, tmp_path):
        """Core dir with two *_menus.json files is merged into a single 'core' entry."""
        core_dir = tmp_path / "core"
        core_dir.mkdir()
        (core_dir / "admin_menus.json").write_text(json.dumps({
            "schema_version": "1.0",
            "menus": {
                "roles": [{"role": "Admin", "id": "core-admin", "label_key": "menu_admin", "items": []}],
            },
        }))
        (core_dir / "help_menus.json").write_text(json.dumps({
            "schema_version": "1.0",
            "menus": {
                "system": {"id": "core-help", "label_key": "menu_help", "items": []},
            },
        }))

        loader = MenuLoaderService(
            core_menus_dir=str(core_dir),
            plugins_dir="/tmp/nonexistent",
        )
        result = loader.load_menus()
        assert "core" in result
        assert result["core"]["roles"]["Admin"]["id"] == "core-admin"
        assert result["core"]["system"]["id"] == "core-help"

    def test_system_section_absent_for_plugin_without_it(self, tmp_path):
        """Plugin with only application and roles sections has system=None in result."""
        plugin_dir = tmp_path / "plugins" / "myplugin"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "myplugin_menus.json").write_text(json.dumps({
            "schema_version": "1.0",
            "menus": {
                "application": {"id": "my-app", "label_key": "lk", "items": []},
            },
        }))

        loader = MenuLoaderService(
            core_menus_dir="/tmp/nonexistent",
            plugins_dir=str(tmp_path / "plugins"),
        )
        result = loader.load_menus()
        assert result["myplugin"]["system"] is None
