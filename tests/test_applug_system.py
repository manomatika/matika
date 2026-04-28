import pytest
import os
import json
import shutil
from matika.core.applug_service import AppLugService
from matika.database import Role, Permission, PageType, PermissionLevel
from matika.core.applug import BaseAppLug
from matika.core.paths import get_matika_version

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
        "matika_version": get_matika_version(),
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

    # Legacy *_menu.json — still discovered by MenuLoaderService.load_all()
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

    # Consolidated *_menus.json — used by load_applug_menus() for application hub
    menus_data = {
        "schema_version": "1.0",
        "menus": {
            "application": {
                "id": "test-main",
                "label_key": "test_item",
                "items": [
                    {"type": "Link", "label_key": "test_item", "href": "/test/plugin/page",
                     "roles": ["Admin", "User"]}
                ]
            }
        }
    }
    with open(os.path.join(p_path, "test_plugin_menus.json"), "w") as f:
        json.dump(menus_data, f)

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
    """get_menus_for_context includes plugin in selector and hub via *_menus.json."""
    service = AppLugService(plugins_dir=plugin_dir)
    service.discover(db)

    result = service.get_menus_for_context(user_roles=["Admin"], t={})

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
    manifest = {"id": "missing", "version": "1.0", "matika_version": get_matika_version(), "entry_point": "nonexistent:Class"}
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
        "matika_version": get_matika_version(),
        "name": "Named Plugin Full Name",
        "display_name": "Short Name",
        "entry_point": "plugin.MockPlugin",
    }
    with open(os.path.join(p_path, "applug.json"), "w") as f:
        json.dump(manifest, f)

    menus_data = {
        "schema_version": "1.0",
        "menus": {
            "application": {
                "id": "named-main",
                "label_key": "k",
                "items": [{"type": "Link", "label_key": "k", "href": "/named/page"}],
            }
        },
    }
    with open(os.path.join(p_path, "named_plugin_menus.json"), "w") as f:
        json.dump(menus_data, f)

    with open(os.path.join(p_path, "plugin.py"), "w") as f:
        f.write(MOCK_PLUGIN_CONTENT)

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
        "matika_version": get_matika_version(),
        "name": "Full Name Only",
        "entry_point": "plugin.MockPlugin",
    }
    with open(os.path.join(p_path, "applug.json"), "w") as f:
        json.dump(manifest, f)

    menus_data = {
        "schema_version": "1.0",
        "menus": {
            "application": {
                "id": "nodn-main",
                "label_key": "k",
                "items": [{"type": "Link", "label_key": "k", "href": "/nodn/page"}],
            }
        },
    }
    with open(os.path.join(p_path, "nodn_plugin_menus.json"), "w") as f:
        json.dump(menus_data, f)

    with open(os.path.join(p_path, "plugin.py"), "w") as f:
        f.write(MOCK_PLUGIN_CONTENT)

    service = AppLugService(plugins_dir=plugin_dir)
    service.discover(db)

    result = service.get_menus_for_context(user_roles=["Admin"], t={})
    item_labels = {e["id"]: e["label"] for e in result["selector"] if e.get("type") == "item"}
    assert item_labels.get("nodn_plugin") == "Full Name Only"


# ---------------------------------------------------------------------------
# matika_version compatibility contract
# ---------------------------------------------------------------------------

def test_missing_matika_version_skips_plugin(plugin_dir, db):
    """An applug.json without matika_version is refused at startup."""
    p_path = os.path.join(plugin_dir, "no_ver_plugin")
    os.makedirs(p_path)
    manifest = {
        "id": "no_ver_plugin",
        "version": "1.0",
        "entry_point": "plugin.MockPlugin",
        # matika_version intentionally absent
    }
    with open(os.path.join(p_path, "applug.json"), "w") as f:
        json.dump(manifest, f)
    with open(os.path.join(p_path, "plugin.py"), "w") as f:
        f.write(MOCK_PLUGIN_CONTENT)

    service = AppLugService(plugins_dir=plugin_dir)
    plugins = service.discover(db)

    loaded_ids = [p.id for p in plugins]
    assert "no_ver_plugin" not in loaded_ids


def test_mismatched_matika_version_skips_plugin(plugin_dir, db):
    """An applug.json with a matika_version that doesn't match running Matika is refused."""
    p_path = os.path.join(plugin_dir, "bad_ver_plugin")
    os.makedirs(p_path)
    manifest = {
        "id": "bad_ver_plugin",
        "version": "1.0",
        "matika_version": "0.0.0",   # deliberately wrong
        "entry_point": "plugin.MockPlugin",
    }
    with open(os.path.join(p_path, "applug.json"), "w") as f:
        json.dump(manifest, f)
    with open(os.path.join(p_path, "plugin.py"), "w") as f:
        f.write(MOCK_PLUGIN_CONTENT)

    service = AppLugService(plugins_dir=plugin_dir)
    plugins = service.discover(db)

    loaded_ids = [p.id for p in plugins]
    assert "bad_ver_plugin" not in loaded_ids


def test_correct_matika_version_loads_plugin(plugin_dir, db):
    """An applug.json with the correct matika_version loads successfully."""
    p_path = os.path.join(plugin_dir, "good_ver_plugin")
    os.makedirs(p_path)
    manifest = {
        "id": "good_ver_plugin",
        "version": "1.0",
        "matika_version": get_matika_version(),
        "entry_point": "plugin.MockPlugin",
    }
    with open(os.path.join(p_path, "applug.json"), "w") as f:
        json.dump(manifest, f)
    with open(os.path.join(p_path, "plugin.py"), "w") as f:
        f.write(MOCK_PLUGIN_CONTENT)

    service = AppLugService(plugins_dir=plugin_dir)
    plugins = service.discover(db)

    loaded_ids = [p.id for p in plugins]
    assert "good_ver_plugin" in loaded_ids


def test_validate_compatibility_error_message_is_informative(plugin_dir, db):
    """The RuntimeError from _validate_compatibility includes actionable text."""
    import pytest
    from matika.core.applug import BaseAppLug

    class ConcretePlugin(BaseAppLug):
        def on_load(self, db): pass
        def on_unload(self, db): pass

    with pytest.raises(RuntimeError, match="matika_version"):
        ConcretePlugin({"id": "test", "version": "1.0"})  # missing matika_version

    with pytest.raises(RuntimeError, match="0.0.0"):
        ConcretePlugin({"id": "test", "version": "1.0", "matika_version": "0.0.0"})  # wrong version


# ---------------------------------------------------------------------------
# MATIKA_ENV=development version check relaxation
# ---------------------------------------------------------------------------

class _ConcretePlugin(BaseAppLug):
    def on_load(self, db): pass
    def on_unload(self, db): pass


def test_dev_mode_dev_version_compatible_with_base_released_version(monkeypatch):
    """MATIKA_ENV=development: 0.0.3_dev is compatible with applug declaring 0.0.2."""
    monkeypatch.setenv("MATIKA_ENV", "development")
    monkeypatch.setattr("matika.core.applug.get_matika_version", lambda: "0.0.3_dev")
    plugin = _ConcretePlugin({"id": "p", "version": "1.0", "matika_version": "0.0.2"})
    assert plugin.matika_version == "0.0.2"


def test_dev_mode_dev_version_compatible_with_same_base_version(monkeypatch):
    """MATIKA_ENV=development: 0.0.3_dev is compatible with applug declaring 0.0.3."""
    monkeypatch.setenv("MATIKA_ENV", "development")
    monkeypatch.setattr("matika.core.applug.get_matika_version", lambda: "0.0.3_dev")
    plugin = _ConcretePlugin({"id": "p", "version": "1.0", "matika_version": "0.0.3"})
    assert plugin.matika_version == "0.0.3"


def test_strict_mode_dev_version_vs_released_refused(monkeypatch):
    """MATIKA_ENV not set: 0.0.3_dev vs 0.0.2 raises RuntimeError."""
    monkeypatch.delenv("MATIKA_ENV", raising=False)
    monkeypatch.setattr("matika.core.applug.get_matika_version", lambda: "0.0.3_dev")
    with pytest.raises(RuntimeError, match="0.0.2"):
        _ConcretePlugin({"id": "p", "version": "1.0", "matika_version": "0.0.2"})


def test_strict_mode_matching_released_version_passes(monkeypatch):
    """MATIKA_ENV not set: exact match 0.0.2 == 0.0.2 loads without error."""
    monkeypatch.delenv("MATIKA_ENV", raising=False)
    monkeypatch.setattr("matika.core.applug.get_matika_version", lambda: "0.0.2")
    plugin = _ConcretePlugin({"id": "p", "version": "1.0", "matika_version": "0.0.2"})
    assert plugin.matika_version == "0.0.2"


def test_non_development_env_enforces_strict_matching(monkeypatch):
    """MATIKA_ENV=production: strict matching enforced even with _dev running version."""
    monkeypatch.setenv("MATIKA_ENV", "production")
    monkeypatch.setattr("matika.core.applug.get_matika_version", lambda: "0.0.3_dev")
    with pytest.raises(RuntimeError, match="0.0.2"):
        _ConcretePlugin({"id": "p", "version": "1.0", "matika_version": "0.0.2"})

# ---------------------------------------------------------------------------
# Consolidated *_menus.json — full menu matrix
# ---------------------------------------------------------------------------

def _make_matrix_plugin(plugin_dir, db):
    """Create a plugin with application + User role + Admin role menus for matrix tests."""
    p_path = os.path.join(plugin_dir, "matrix_plugin")
    os.makedirs(p_path)

    manifest = {
        "id": "matrix_plugin",
        "version": "1.0",
        "matika_version": get_matika_version(),
        "name": "Matrix Plugin",
        "entry_point": "plugin.MockPlugin",
    }
    with open(os.path.join(p_path, "applug.json"), "w") as f:
        json.dump(manifest, f)

    menus_data = {
        "schema_version": "1.0",
        "menus": {
            "application": {
                "id": "matrix-app",
                "label_key": "menu_matrix",
                "items": [
                    {"type": "Link", "label_key": "item_matrix_page",
                     "href": "/matrix/page"}
                ]
            },
            "roles": [
                {
                    "role": "User",
                    "id": "matrix-user",
                    "label_key": "menu_matrix",
                    "items": [
                        {
                            "type": "Menu",
                            "label_key": "menu_matrix",
                            "items": [
                                {"type": "Link", "label_key": "item_matrix_page",
                                 "href": "/matrix/page"}
                            ]
                        }
                    ]
                },
                {
                    "role": "Admin",
                    "id": "matrix-admin",
                    "label_key": "menu_matrix",
                    "items": [
                        {
                            "type": "Menu",
                            "label_key": "menu_matrix",
                            "items": [
                                {"type": "Link", "label_key": "item_matrix_admin",
                                 "href": "/matrix/admin"}
                            ]
                        }
                    ]
                }
            ]
        }
    }
    with open(os.path.join(p_path, "matrix_plugin_menus.json"), "w") as f:
        json.dump(menus_data, f)

    with open(os.path.join(p_path, "plugin.py"), "w") as f:
        f.write(MOCK_PLUGIN_CONTENT)

    service = AppLugService(plugins_dir=plugin_dir)
    service.discover(db)
    return service


def test_application_hub_visible_to_user_role(plugin_dir, db):
    """Application hub entry appears for users with User role (no role restriction on app menu)."""
    service = _make_matrix_plugin(plugin_dir, db)
    result = service.get_menus_for_context(user_roles=["User"], t={})
    ids = [e["id"] for e in result["selector"] if e.get("type") == "item"]
    assert "matrix_plugin" in ids
    assert "matrix_plugin" in result["hubs"]


def test_application_hub_visible_to_admin_role(plugin_dir, db):
    """Application hub entry appears for users with Admin role."""
    service = _make_matrix_plugin(plugin_dir, db)
    result = service.get_menus_for_context(user_roles=["Admin"], t={})
    ids = [e["id"] for e in result["selector"] if e.get("type") == "item"]
    assert "matrix_plugin" in ids
    assert "matrix_plugin" in result["hubs"]


def test_user_role_hub_contains_plugin_user_menu(plugin_dir, db):
    """__role_User__ hub contains the plugin's User role menu items."""
    service = _make_matrix_plugin(plugin_dir, db)
    result = service.get_menus_for_context(user_roles=["User"], t={})
    user_hub = result["hubs"].get("__role_User__", [])
    all_hrefs = [
        item.get("href", "")
        for entry in user_hub
        for item in (entry.get("items") or [{"href": entry.get("href", "")}])
    ]
    assert any("/matrix/page" in h for h in all_hrefs), (
        f"Expected /matrix/page in User hub. Hub: {user_hub}"
    )


def test_admin_role_hub_contains_core_and_plugin_admin_menus(plugin_dir, db):
    """__role_Admin__ hub contains both core admin items and plugin Admin role items."""
    service = _make_matrix_plugin(plugin_dir, db)
    result = service.get_menus_for_context(user_roles=["Admin"], t={})
    admin_hub = result["hubs"].get("__role_Admin__", [])

    all_labels = [entry.get("label", "") for entry in admin_hub]
    # Core admin menu contributes its top-level menu label
    assert any(lbl in ("menu_admin", "Admin") for lbl in all_labels), (
        f"Expected core Admin menu label in Admin hub. Labels: {all_labels}"
    )

    all_hrefs = []
    for entry in admin_hub:
        for item in (entry.get("items") or []):
            all_hrefs.append(item.get("href", ""))
            for sub in (item.get("items") or []):
                all_hrefs.append(sub.get("href", ""))
    assert any("/matrix/admin" in h for h in all_hrefs), (
        f"Expected /matrix/admin in Admin hub. Hrefs: {all_hrefs}"
    )


def test_user_with_both_roles_sees_both_role_entries_in_selector(plugin_dir, db):
    """A user with both User and Admin roles sees __role_User__ and __role_Admin__ in selector."""
    service = _make_matrix_plugin(plugin_dir, db)
    result = service.get_menus_for_context(user_roles=["User", "Admin"], t={})
    ids = [e["id"] for e in result["selector"] if e.get("type") == "item"]
    assert "__role_User__" in ids
    assert "__role_Admin__" in ids


def test_user_only_role_does_not_see_admin_in_selector(plugin_dir, db):
    """A user with only User role does not see __role_Admin__ in selector."""
    service = _make_matrix_plugin(plugin_dir, db)
    result = service.get_menus_for_context(user_roles=["User"], t={})
    ids = [e["id"] for e in result["selector"] if e.get("type") == "item"]
    assert "__role_User__" in ids
    assert "__role_Admin__" not in ids


def test_admin_only_role_does_not_see_user_in_selector(plugin_dir, db):
    """A user with only Admin role does not see __role_User__ in selector."""
    service = _make_matrix_plugin(plugin_dir, db)
    result = service.get_menus_for_context(user_roles=["Admin"], t={})
    ids = [e["id"] for e in result["selector"] if e.get("type") == "item"]
    assert "__role_Admin__" in ids
    assert "__role_User__" not in ids


def test_permission_file_without_menus_file_logs_warning(plugin_dir, db, monkeypatch):
    """Startup warning is logged when a plugin has *_permission.json but no *_menus.json."""
    p_path = os.path.join(plugin_dir, "warn_plugin")
    os.makedirs(p_path)

    with open(os.path.join(p_path, "warn_plugin_permission.json"), "w") as f:
        json.dump({"permissions": []}, f)

    from matika.core.menu_loader import MenuLoaderService
    from matika.core.paths import BASE_DIR
    import matika.core.menu_loader as _ml_mod

    captured: list = []
    monkeypatch.setattr(_ml_mod.logger, "warning", lambda msg, *args, **kw: captured.append(msg % args))

    core_menus_dir = os.path.join(BASE_DIR, "src", "matika", "menus")
    loader = MenuLoaderService(core_menus_dir=core_menus_dir, plugins_dir=plugin_dir)
    loader.load_applug_menus()

    assert any("warn_plugin" in msg and "no *_menus.json" in msg for msg in captured), (
        f"Expected warning about missing *_menus.json. Captured: {captured}"
    )


def test_filter_items_removes_role_restricted_items_from_role_hub(plugin_dir, db):
    """filter_items() removes items whose roles list excludes the current user's role."""
    p_path = os.path.join(plugin_dir, "filter_plugin")
    os.makedirs(p_path)

    manifest = {
        "id": "filter_plugin",
        "version": "1.0",
        "matika_version": get_matika_version(),
        "name": "Filter Plugin",
        "entry_point": "plugin.MockPlugin",
    }
    with open(os.path.join(p_path, "applug.json"), "w") as f:
        json.dump(manifest, f)

    menus_data = {
        "schema_version": "1.0",
        "menus": {
            "roles": [
                {
                    "role": "User",
                    "id": "filter-user",
                    "label_key": "menu_filter",
                    "items": [
                        {
                            "type": "Menu",
                            "label_key": "menu_filter",
                            "items": [
                                {"type": "Link", "label_key": "item_allowed",
                                 "href": "/filter/allowed"},
                                {"type": "Link", "label_key": "item_admin_only",
                                 "href": "/filter/admin_only", "roles": ["Admin"]},
                            ]
                        }
                    ]
                }
            ]
        }
    }
    with open(os.path.join(p_path, "filter_plugin_menus.json"), "w") as f:
        json.dump(menus_data, f)

    with open(os.path.join(p_path, "plugin.py"), "w") as f:
        f.write(MOCK_PLUGIN_CONTENT)

    service = AppLugService(plugins_dir=plugin_dir)
    service.discover(db)

    result = service.get_menus_for_context(user_roles=["User"], t={})
    user_hub = result["hubs"].get("__role_User__", [])

    all_hrefs = []
    for entry in user_hub:
        for item in (entry.get("items") or []):
            all_hrefs.append(item.get("href", ""))
    assert "/filter/allowed" in all_hrefs, f"Allowed link missing from User hub. Hrefs: {all_hrefs}"
    assert "/filter/admin_only" not in all_hrefs, (
        f"Admin-only link must not appear in User hub. Hrefs: {all_hrefs}"
    )


def test_load_applug_menus_parses_application_and_roles(plugin_dir):
    """load_applug_menus() correctly parses application and roles from *_menus.json."""
    p_path = os.path.join(plugin_dir, "parse_plugin")
    os.makedirs(p_path)

    menus_data = {
        "schema_version": "1.0",
        "menus": {
            "application": {
                "id": "parse-app",
                "label_key": "menu_parse",
                "items": [{"type": "Link", "label_key": "k", "href": "/parse/page"}]
            },
            "roles": [
                {"role": "Admin", "id": "parse-admin", "label_key": "menu_parse", "items": []}
            ]
        }
    }
    with open(os.path.join(p_path, "parse_plugin_menus.json"), "w") as f:
        json.dump(menus_data, f)

    from matika.core.menu_loader import MenuLoaderService
    from matika.core.paths import BASE_DIR
    core_menus_dir = os.path.join(BASE_DIR, "src", "matika", "menus")
    loader = MenuLoaderService(core_menus_dir=core_menus_dir, plugins_dir=plugin_dir)
    result = loader.load_applug_menus()

    assert "parse_plugin" in result
    assert result["parse_plugin"]["application"]["id"] == "parse-app"
    assert "Admin" in result["parse_plugin"]["roles"]
    assert result["parse_plugin"]["roles"]["Admin"]["id"] == "parse-admin"
    assert "User" not in result["parse_plugin"]["roles"]


def test_load_applug_menus_returns_none_for_missing_application(plugin_dir):
    """load_applug_menus() returns application=None when the section is absent."""
    p_path = os.path.join(plugin_dir, "noapp_plugin")
    os.makedirs(p_path)

    menus_data = {
        "schema_version": "1.0",
        "menus": {
            "roles": [
                {"role": "Admin", "id": "noapp-admin", "label_key": "k", "items": []}
            ]
        }
    }
    with open(os.path.join(p_path, "noapp_plugin_menus.json"), "w") as f:
        json.dump(menus_data, f)

    from matika.core.menu_loader import MenuLoaderService
    from matika.core.paths import BASE_DIR
    core_menus_dir = os.path.join(BASE_DIR, "src", "matika", "menus")
    loader = MenuLoaderService(core_menus_dir=core_menus_dir, plugins_dir=plugin_dir)
    result = loader.load_applug_menus()

    assert result["noapp_plugin"]["application"] is None


def test_invalidate_cache_clears_both_caches(plugin_dir):
    """invalidate_cache() clears both the legacy and applug menu caches."""
    from matika.core.menu_loader import MenuLoaderService
    from matika.core.paths import BASE_DIR
    core_menus_dir = os.path.join(BASE_DIR, "src", "matika", "menus")
    loader = MenuLoaderService(core_menus_dir=core_menus_dir, plugins_dir=plugin_dir)

    loader.load_all()
    loader.load_applug_menus()
    assert loader._cache is not None
    assert loader._applug_cache is not None

    loader.invalidate_cache()
    assert loader._cache is None
    assert loader._applug_cache is None
