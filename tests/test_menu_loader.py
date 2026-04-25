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
        core_dir = os.path.join(BASE_DIR, "src", "matika", "menus")
        loader = MenuLoaderService(core_menus_dir=core_dir, plugins_dir="/tmp/nonexistent")
        result = loader.load_all()
        assert "core" in result
        core_ids = [m["id"] for m in result["core"]]
        assert "core-admin" in core_ids
        assert "core-help" in core_ids

    def test_loads_plugin_menu_files(self, tmp_path):
        plugin_dir = tmp_path / "plugins" / "myplugin"
        plugin_dir.mkdir(parents=True)
        menu_data = {
            "schema_version": "1.0",
            "menus": [{"id": "my-menu", "label_key": "lk", "type": "Application", "items": []}],
        }
        (plugin_dir / "myplugin_menu.json").write_text(json.dumps(menu_data))

        loader = MenuLoaderService(
            core_menus_dir="/tmp/nonexistent",
            plugins_dir=str(tmp_path / "plugins"),
        )
        result = loader.load_all()
        assert "myplugin" in result
        assert result["myplugin"][0]["id"] == "my-menu"

    def test_skips_unsupported_schema(self, tmp_path, caplog):
        plugin_dir = tmp_path / "plugins" / "bad"
        plugin_dir.mkdir(parents=True)
        bad_data = {"schema_version": "99.0", "menus": []}
        (plugin_dir / "bad_menu.json").write_text(json.dumps(bad_data))

        loader = MenuLoaderService(
            core_menus_dir="/tmp/nonexistent",
            plugins_dir=str(tmp_path / "plugins"),
        )
        result = loader.load_all()
        assert "bad" not in result

    def test_skips_invalid_json(self, tmp_path):
        plugin_dir = tmp_path / "plugins" / "broken"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "broken_menu.json").write_text("not json {{{")

        loader = MenuLoaderService(
            core_menus_dir="/tmp/nonexistent",
            plugins_dir=str(tmp_path / "plugins"),
        )
        result = loader.load_all()
        assert "broken" not in result

    def test_missing_directories_return_empty(self):
        loader = MenuLoaderService(
            core_menus_dir="/tmp/nonexistent_core",
            plugins_dir="/tmp/nonexistent_plugins",
        )
        result = loader.load_all()
        assert result == {}

    def test_load_all_returns_cached_result_on_second_call(self, tmp_path):
        """Second call to load_all() returns the same object (cache hit)."""
        plugin_dir = tmp_path / "plugins" / "plug"
        plugin_dir.mkdir(parents=True)
        menu_data = {
            "schema_version": "1.0",
            "menus": [{"id": "p-menu", "label_key": "k", "type": "Application", "items": []}],
        }
        (plugin_dir / "plug_menu.json").write_text(json.dumps(menu_data))

        loader = MenuLoaderService(
            core_menus_dir="/tmp/nonexistent",
            plugins_dir=str(tmp_path / "plugins"),
        )
        first = loader.load_all()
        second = loader.load_all()
        assert first is second  # identical object — no re-read

    def test_invalidate_cache_forces_reload(self, tmp_path):
        """invalidate_cache() clears the cache so the next call re-reads from disk."""
        plugin_dir = tmp_path / "plugins" / "plug"
        plugin_dir.mkdir(parents=True)
        menu_file = plugin_dir / "plug_menu.json"
        menu_data = {
            "schema_version": "1.0",
            "menus": [{"id": "p1", "label_key": "k", "type": "Application", "items": []}],
        }
        menu_file.write_text(json.dumps(menu_data))

        loader = MenuLoaderService(
            core_menus_dir="/tmp/nonexistent",
            plugins_dir=str(tmp_path / "plugins"),
        )
        first = loader.load_all()
        assert first["plug"][0]["id"] == "p1"

        # Mutate on disk and invalidate
        menu_data["menus"][0]["id"] = "p2"
        menu_file.write_text(json.dumps(menu_data))
        loader.invalidate_cache()

        second = loader.load_all()
        assert second["plug"][0]["id"] == "p2"

    def test_core_help_menu_has_system_type(self):
        """core-help menu must have type 'System' for hub ordering logic."""
        core_dir = os.path.join(BASE_DIR, "src", "matika", "menus")
        loader = MenuLoaderService(core_menus_dir=core_dir, plugins_dir="/tmp/nonexistent")
        result = loader.load_all()
        help_menu = next((m for m in result["core"] if m["id"] == "core-help"), None)
        assert help_menu is not None
        assert help_menu["type"] == "System"

    def test_core_admin_menu_has_role_type(self):
        """core-admin menu must have type 'Role' so it is not treated as Help."""
        core_dir = os.path.join(BASE_DIR, "src", "matika", "menus")
        loader = MenuLoaderService(core_menus_dir=core_dir, plugins_dir="/tmp/nonexistent")
        result = loader.load_all()
        admin_menu = next((m for m in result["core"] if m["id"] == "core-admin"), None)
        assert admin_menu is not None
        assert admin_menu["type"] == "Role"

    def test_help_menu_has_separator_between_items(self):
        """core-help menu items must include a Separator between Show Log and About."""
        core_dir = os.path.join(BASE_DIR, "src", "matika", "menus")
        loader = MenuLoaderService(core_menus_dir=core_dir, plugins_dir="/tmp/nonexistent")
        result = loader.load_all()
        help_menu = next((m for m in result["core"] if m["id"] == "core-help"), None)
        assert help_menu is not None

        item_types = [i["type"] for i in help_menu["items"]]
        assert "Separator" in item_types

        sep_idx = item_types.index("Separator")
        assert sep_idx > 0, "Separator must not be the first item"
        assert sep_idx < len(item_types) - 1, "Separator must not be the last item"
