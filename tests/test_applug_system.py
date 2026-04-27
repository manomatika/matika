import pytest
import os
import json
import shutil
from matika.core.applug_service import AppLugService
from matika.database import Role, Permission, PageType, PermissionLevel
from matika.core.applug import BaseAppLug

# Mock Plugin for Testing
MOCK_PLUGIN_CONTENT = """
from matika.core.applug import BaseAppLug

class MockPlugin(BaseAppLug):
    def on_load(self, db):
        self.loaded = True
    def on_unload(self, db):
        self.unloaded = True
"""

@pytest.fixture
def plugin_dir(tmp_path):
    d = tmp_path / "plugins"
    d.mkdir()
    return str(d)

@pytest.fixture
def mock_plugin(plugin_dir):
    p_path = os.path.join(plugin_dir, "test_plugin")
    os.makedirs(p_path)

    manifest = {
        "id": "test_plugin",
        "version": "1.0.0",
        "entry_point": "plugin.MockPlugin",
        "permissions": [
            {
                "page_path": "/test/plugin/page",
                "page_type": "Maintenance",
                "roles": {
                    "Admin": "Full",
                    "PluginRole": "Read"
                }
            }
        ]
    }
    with open(os.path.join(p_path, "applug.json"), "w") as f:
        json.dump(manifest, f)

    menu_data = {
        "schema_version": "1.0",
        "menus": [
            {
                "id": "test-main",
                "label_key": "test_item",
                "type": "Application",
                "items": [
                    {"type": "Link", "label_key": "test_item", "href": "/test/plugin/page"}
                ]
            }
        ]
    }
    with open(os.path.join(p_path, "test_plugin_menu.json"), "w") as f:
        json.dump(menu_data, f)

    with open(os.path.join(p_path, "plugin.py"), "w") as f:
        f.write(MOCK_PLUGIN_CONTENT)

    return p_path

def test_plugin_discovery_and_load(plugin_dir, mock_plugin, db):
    service = AppLugService(plugins_dir=plugin_dir)
    plugins = service.discover(db)

    assert len(plugins) == 1
    assert plugins[0].id == "test_plugin"
    assert plugins[0].loaded is True

def test_plugin_entity_registration(plugin_dir, mock_plugin, db):
    service = AppLugService(plugins_dir=plugin_dir)
    service.discover(db)

    role = db.query(Role).filter(Role.name == "PluginRole").first()
    assert role is not None

    admin_role = db.query(Role).filter(Role.name == "Admin").first()
    admin_perm = db.query(Permission).filter(
        Permission.role_id == admin_role.id,
        Permission.page_path == "/test/plugin/page"
    ).first()
    assert admin_perm is not None
    assert admin_perm.level == PermissionLevel.FULL

    plugin_perm = db.query(Permission).filter(
        Permission.role_id == role.id,
        Permission.page_path == "/test/plugin/page"
    ).first()
    assert plugin_perm is not None
    assert plugin_perm.level == PermissionLevel.READ

def test_plugin_menu_loading(plugin_dir, mock_plugin, db):
    """MenuLoaderService discovers *_menu.json files in plugin directories."""
    from matika.core.menu_loader import MenuLoaderService
    from matika.core.paths import BASE_DIR

    core_menus_dir = os.path.join(BASE_DIR, "src", "matika", "menus")
    loader = MenuLoaderService(core_menus_dir=core_menus_dir, plugins_dir=plugin_dir)
    all_menus = loader.load_all()

    assert "test_plugin" in all_menus
    plugin_menus = all_menus["test_plugin"]
    assert len(plugin_menus) == 1
    assert plugin_menus[0]["id"] == "test-main"
    assert plugin_menus[0]["type"] == "Application"

def test_plugin_menus_in_context(plugin_dir, mock_plugin, db):
    """get_menus_for_context includes loaded plugin menus in the hub."""
    service = AppLugService(plugins_dir=plugin_dir)
    service.discover(db)

    result = service.get_menus_for_context(user_roles=["Admin"], t={})

    # Only "item"-type entries have an id field in the new discriminated selector.
    selector_item_ids = [e["id"] for e in result["selector"] if e.get("type") == "item"]
    assert "test_plugin" in selector_item_ids
    assert "test_plugin" in result["hubs"]

def test_resilience_to_faulty_plugins(plugin_dir, db):
    broken_path = os.path.join(plugin_dir, "broken_plugin")
    os.makedirs(broken_path)
    with open(os.path.join(broken_path, "applug.json"), "w") as f:
        f.write("invalid json")

    service = AppLugService(plugins_dir=plugin_dir)
    plugins = service.discover(db)
    assert len(plugins) == 0

def test_resilience_to_missing_entry_point(plugin_dir, db):
    missing_path = os.path.join(plugin_dir, "missing_code")
    os.makedirs(missing_path)
    manifest = {"id": "missing", "version": "1.0", "entry_point": "nonexistent:Class"}
    with open(os.path.join(missing_path, "applug.json"), "w") as f:
        json.dump(manifest, f)

    service = AppLugService(plugins_dir=plugin_dir)
    plugins = service.discover(db)
    assert len(plugins) == 0

def test_plugin_localization_merging(plugin_dir, db):
    p_path = os.path.join(plugin_dir, "loc_plugin")
    loc_dir = os.path.join(p_path, "src", "loc_plugin", "locales")
    os.makedirs(loc_dir)

    manifest = {"id": "loc_plugin", "version": "1.0", "entry_point": "plugin.MockPlugin"}
    with open(os.path.join(p_path, "applug.json"), "w") as f:
        json.dump(manifest, f)

    with open(os.path.join(loc_dir, "en.json"), "w") as f:
        json.dump({"plugin_custom_key": "Plugin Value", "item_home": "Home Override"}, f)

    from matika.i18n import I18nService
    i18n = I18nService()

    import matika.i18n
    from pathlib import Path
    original_root = matika.i18n.ROOT_DIR
    matika.i18n.ROOT_DIR = str(Path(plugin_dir).parent)

    data = i18n.load_language("en")
    assert data is not None
    assert data["plugin_custom_key"] == "Plugin Value"
    assert data["item_home"] == "Home Override"

    matika.i18n.ROOT_DIR = original_root

def test_plugin_on_unload(plugin_dir, mock_plugin, db):
    service = AppLugService(plugins_dir=plugin_dir)
    plugins = service.discover(db)
    plugin = plugins[0]
    plugin.on_unload(db)
    assert plugin.unloaded is True


# ---------------------------------------------------------------------------
# _filter_by_paths
# ---------------------------------------------------------------------------

class TestFilterByPaths:
    """Unit tests for AppLugService._filter_by_paths (role menu building helper)."""

    def _svc(self, plugin_dir):
        return AppLugService(plugins_dir=plugin_dir)

    def test_link_included_when_href_accessible(self, plugin_dir):
        svc = self._svc(plugin_dir)
        items = [{"type": "Link", "label_key": "k", "href": "/admin/page"}]
        result = svc._filter_by_paths(items, {"/admin/page"})
        assert len(result) == 1
        assert result[0]["href"] == "/admin/page"

    def test_link_excluded_when_href_not_accessible(self, plugin_dir):
        svc = self._svc(plugin_dir)
        items = [{"type": "Link", "label_key": "k", "href": "/admin/page"}]
        assert svc._filter_by_paths(items, set()) == []
        assert svc._filter_by_paths(items, {"/other"}) == []

    def test_menu_container_kept_when_children_accessible(self, plugin_dir):
        svc = self._svc(plugin_dir)
        items = [{"type": "Menu", "label_key": "sub", "items": [
            {"type": "Link", "label_key": "x", "href": "/x"},
        ]}]
        result = svc._filter_by_paths(items, {"/x"})
        assert len(result) == 1
        assert result[0]["type"] == "Menu"
        assert len(result[0]["items"]) == 1

    def test_menu_container_dropped_when_no_children_accessible(self, plugin_dir):
        svc = self._svc(plugin_dir)
        items = [{"type": "Menu", "label_key": "sub", "items": [
            {"type": "Link", "label_key": "x", "href": "/x"},
        ]}]
        assert svc._filter_by_paths(items, set()) == []

    def test_separator_cleaned_at_edges(self, plugin_dir):
        svc = self._svc(plugin_dir)
        items = [
            {"type": "Link", "label_key": "a", "href": "/a"},
            {"type": "Separator"},
            {"type": "Link", "label_key": "b", "href": "/b"},
        ]
        # Only /a accessible → trailing separator removed
        result = svc._filter_by_paths(items, {"/a"})
        assert result == [{"type": "Link", "label_key": "a", "href": "/a"}]

    def test_mixed_accessible_and_filtered(self, plugin_dir):
        svc = self._svc(plugin_dir)
        items = [
            {"type": "Link", "label_key": "a", "href": "/a"},
            {"type": "Link", "label_key": "b", "href": "/b"},
        ]
        result = svc._filter_by_paths(items, {"/a"})
        assert len(result) == 1
        assert result[0]["href"] == "/a"


# ---------------------------------------------------------------------------
# _build_role_menus and role menu cache
# ---------------------------------------------------------------------------

def test_build_role_menus_populates_cache(plugin_dir, mock_plugin, db):
    """After discover(), _role_menu_cache contains entries for roles with non-NONE permissions."""
    service = AppLugService(plugins_dir=plugin_dir)
    service.discover(db)  # calls _build_role_menus internally

    # Admin and User are seeded by init_db and have non-NONE permissions
    assert "Admin" in service._role_menu_cache
    assert "User" in service._role_menu_cache

def test_build_role_menus_excludes_role_with_no_permissions(plugin_dir, db):
    """A role that has no non-NONE permissions is not included in the cache."""
    service = AppLugService(plugins_dir=plugin_dir)

    # Seed a role with no permissions
    empty_role = Role(name="EmptyRole", description="No perms", is_system=False)
    db.add(empty_role)
    db.commit()

    service.discover(db)
    assert "EmptyRole" not in service._role_menu_cache

def test_role_hub_ordering(plugin_dir, mock_plugin, db):
    """Role hub items: plugin menus first, core non-help second, Help last."""
    service = AppLugService(plugins_dir=plugin_dir)
    service.discover(db)

    result = service.get_menus_for_context(user_roles=["Admin"], t={})
    admin_hub = result["hubs"].get("__role_Admin__", [])

    assert len(admin_hub) >= 1
    # Help menu must be last
    last = admin_hub[-1]
    assert last["label"] == "menu_help" or "help" in last.get("id", "").lower() or "Help" in last.get("label", "")

def test_application_hub_has_help_last(plugin_dir, mock_plugin, db):
    """Application (per-plugin) hubs always have the Help menu appended as the last entry."""
    service = AppLugService(plugins_dir=plugin_dir)
    service.discover(db)

    result = service.get_menus_for_context(user_roles=["Admin"], t={})
    plugin_hub = result["hubs"].get("test_plugin", [])

    # Hub must contain at least the plugin's own menu + Help
    assert len(plugin_hub) >= 2
    last = plugin_hub[-1]
    # The last entry comes from core-help (System type)
    assert "help" in last.get("id", "").lower() or last.get("label") in ("menu_help", "Help")

def test_display_name_used_in_selector_over_name(plugin_dir, db):
    """display_name in manifest takes precedence over name for Application selector label."""
    p_path = os.path.join(plugin_dir, "named_plugin")
    os.makedirs(p_path)

    manifest = {
        "id": "named_plugin",
        "version": "1.0",
        "name": "Named Plugin Full Name",
        "display_name": "Short Name",
        "entry_point": "plugin.MockPlugin",
    }
    with open(os.path.join(p_path, "applug.json"), "w") as f:
        json.dump(manifest, f)

    menu_data = {
        "schema_version": "1.0",
        "menus": [{"id": "named-main", "label_key": "k", "type": "Application",
                   "items": [{"type": "Link", "label_key": "k", "href": "/named/page"}]}],
    }
    with open(os.path.join(p_path, "named_plugin_menu.json"), "w") as f:
        json.dump(menu_data, f)

    with open(os.path.join(p_path, "plugin.py"), "w") as f:
        f.write(MOCK_PLUGIN_CONTENT)

    # Seed permission so the page is accessible
    admin_role = db.query(Role).filter(Role.name == "Admin").first()
    db.add(Permission(
        page_path="/named/page", page_type=PageType.MAINTENANCE,
        role_id=admin_role.id, level=PermissionLevel.FULL, is_system=True,
    ))
    db.commit()

    service = AppLugService(plugins_dir=plugin_dir)
    service.discover(db)

    result = service.get_menus_for_context(user_roles=["Admin"], t={})
    item_labels = {e["id"]: e["label"] for e in result["selector"] if e.get("type") == "item"}
    assert item_labels.get("named_plugin") == "Short Name"

def test_display_name_falls_back_to_name(plugin_dir, db):
    """When display_name is absent the selector uses name."""
    p_path = os.path.join(plugin_dir, "nodn_plugin")
    os.makedirs(p_path)

    manifest = {
        "id": "nodn_plugin",
        "version": "1.0",
        "name": "Full Name Only",
        "entry_point": "plugin.MockPlugin",
    }
    with open(os.path.join(p_path, "applug.json"), "w") as f:
        json.dump(manifest, f)

    menu_data = {
        "schema_version": "1.0",
        "menus": [{"id": "nodn-main", "label_key": "k", "type": "Application",
                   "items": [{"type": "Link", "label_key": "k", "href": "/nodn/page"}]}],
    }
    with open(os.path.join(p_path, "nodn_plugin_menu.json"), "w") as f:
        json.dump(menu_data, f)

    with open(os.path.join(p_path, "plugin.py"), "w") as f:
        f.write(MOCK_PLUGIN_CONTENT)

    admin_role = db.query(Role).filter(Role.name == "Admin").first()
    db.add(Permission(
        page_path="/nodn/page", page_type=PageType.MAINTENANCE,
        role_id=admin_role.id, level=PermissionLevel.FULL, is_system=True,
    ))
    db.commit()

    service = AppLugService(plugins_dir=plugin_dir)
    service.discover(db)

    result = service.get_menus_for_context(user_roles=["Admin"], t={})
    item_labels = {e["id"]: e["label"] for e in result["selector"] if e.get("type") == "item"}
    assert item_labels.get("nodn_plugin") == "Full Name Only"
