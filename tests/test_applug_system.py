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

def test_load_menus_on_plugin_dir(plugin_dir, mock_plugin, db):
    """MenuLoaderService.load_menus() discovers *_menus.json in plugin directories."""
    from matika.core.menu_loader import MenuLoaderService
    from matika.core.paths import BASE_DIR

    core_menus_dir = os.path.join(BASE_DIR, "src", "matika", "menus")
    loader = MenuLoaderService(core_menus_dir=core_menus_dir, plugins_dir=plugin_dir)
    result = loader.load_menus()

    assert "test_plugin" in result
    plugin_data = result["test_plugin"]
    assert plugin_data["application"] is not None
    assert plugin_data["application"]["id"] == "test-main"

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
    """Admin role hub: aggregated Admin dropdown first, Help last."""
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


def test_mismatched_matika_version_skips_plugin(plugin_dir, db, monkeypatch):
    """An applug.json with a matika_version that doesn't match running Matika is refused."""
    monkeypatch.delenv("MATIKA_ENV", raising=False)
    monkeypatch.setattr("matika.core.applug.get_matika_version", lambda: "0.0.4")

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


def test_validate_compatibility_error_message_is_informative(plugin_dir, db, monkeypatch):
    """The RuntimeError from _validate_compatibility includes actionable text."""
    import pytest
    from matika.core.applug import BaseAppLug

    monkeypatch.delenv("MATIKA_ENV", raising=False)
    monkeypatch.setattr("matika.core.applug.get_matika_version", lambda: "0.0.4")

    class ConcretePlugin(BaseAppLug):
        def on_load(self, db): pass
        def on_unload(self, db): pass

    with pytest.raises(RuntimeError, match="matika_version"):
        ConcretePlugin({"id": "test", "version": "1.0"})  # missing matika_version

    with pytest.raises(RuntimeError, match="0.0.0"):
        ConcretePlugin({"id": "test", "version": "1.0", "matika_version": "0.0.0"})  # wrong version


# ---------------------------------------------------------------------------
# Compare-on-core + general pre-release awareness
#
# The version ladder X.Y.Z-dev < X.Y.Z-rc.N < X.Y.Z all resolve to core X.Y.Z.
# A pre-release runtime loads an AppLug pinned to its bare core. There is no
# MATIKA_ENV escape hatch — compatibility is decided purely on the bare core.
# ---------------------------------------------------------------------------

class _ConcretePlugin(BaseAppLug):
    def on_load(self, db): pass
    def on_unload(self, db): pass


def test_dev_runtime_loads_applug_pinned_to_bare_core(monkeypatch):
    """A -dev runtime (0.0.3-dev) loads an applug declaring its bare core 0.0.3."""
    monkeypatch.setattr("matika.core.applug.get_matika_version", lambda: "0.0.3-dev")
    plugin = _ConcretePlugin({"id": "p", "version": "1.0", "matika_version": "0.0.3"})
    assert plugin.matika_version == "0.0.3"


def test_rc_runtime_loads_applug_pinned_to_bare_core(monkeypatch):
    """An -rc.N runtime (0.0.3-rc.2) loads an applug declaring its bare core 0.0.3."""
    monkeypatch.setattr("matika.core.applug.get_matika_version", lambda: "0.0.3-rc.2")
    plugin = _ConcretePlugin({"id": "p", "version": "1.0", "matika_version": "0.0.3"})
    assert plugin.matika_version == "0.0.3"


def test_prerelease_runtime_with_different_core_refused(monkeypatch):
    """0.0.3-dev (core 0.0.3) vs applug pinned to 0.0.2 raises — cores differ."""
    monkeypatch.setattr("matika.core.applug.get_matika_version", lambda: "0.0.3-dev")
    with pytest.raises(RuntimeError, match="0.0.2"):
        _ConcretePlugin({"id": "p", "version": "1.0", "matika_version": "0.0.2"})


def test_final_runtime_matching_bare_core_passes(monkeypatch):
    """Final runtime 0.0.2 vs applug declaring 0.0.2 loads without error."""
    monkeypatch.setattr("matika.core.applug.get_matika_version", lambda: "0.0.2")
    plugin = _ConcretePlugin({"id": "p", "version": "1.0", "matika_version": "0.0.2"})
    assert plugin.matika_version == "0.0.2"


def test_final_runtime_mismatched_core_refused(monkeypatch):
    """Final runtime 0.0.3 vs applug pinned to 0.0.2 raises — cores differ."""
    monkeypatch.setattr("matika.core.applug.get_matika_version", lambda: "0.0.3")
    with pytest.raises(RuntimeError, match="0.0.2"):
        _ConcretePlugin({"id": "p", "version": "1.0", "matika_version": "0.0.2"})


def test_applug_pinned_to_prerelease_compares_on_core(monkeypatch):
    """Even if an applug erroneously pins a suffix, comparison is on bare core."""
    monkeypatch.setattr("matika.core.applug.get_matika_version", lambda: "0.0.3")
    plugin = _ConcretePlugin({"id": "p", "version": "1.0", "matika_version": "0.0.3-rc.1"})
    assert plugin.matika_version == "0.0.3-rc.1"


# ---------------------------------------------------------------------------
# _validate_compatibility — explicit PERMISSIVE vs REJECT directions
# (strict-parser pass: 0.0.4-rc.1 / 0.0.4-dev load applug pinned 0.0.4;
#  0.0.5-rc.1 vs applug 0.0.4 raises)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("running", ["0.0.4-rc.1", "0.0.4-dev"])
def test_validate_compatibility_permissive_prerelease_loads_bare_core(running, monkeypatch):
    """PERMISSIVE: a pre-release runtime loads an applug pinned to its bare core."""
    monkeypatch.setattr("matika.core.applug.get_matika_version", lambda: running)
    plugin = _ConcretePlugin({"id": "p", "version": "1.0", "matika_version": "0.0.4"})
    assert plugin.matika_version == "0.0.4"


def test_validate_compatibility_reject_different_core_prerelease(monkeypatch):
    """REJECT: running 0.0.5-rc.1 (core 0.0.5) vs applug pinned 0.0.4 raises."""
    monkeypatch.setattr("matika.core.applug.get_matika_version", lambda: "0.0.5-rc.1")
    with pytest.raises(RuntimeError, match="0.0.4"):
        _ConcretePlugin({"id": "p", "version": "1.0", "matika_version": "0.0.4"})


def test_validate_compatibility_surfaces_missing_version_error(monkeypatch):
    """A missing/unreadable VERSION surfaces the specific paths.py error (RULE B),
    NOT a re-swallowed sentinel and NOT a bare SemVer error."""
    def _raise():
        raise RuntimeError(
            "Matika VERSION file missing or unreadable at /abs/path/VERSION: boom"
        )
    monkeypatch.setattr("matika.core.applug.get_matika_version", _raise)
    with pytest.raises(RuntimeError, match="VERSION file missing or unreadable"):
        _ConcretePlugin({"id": "p", "version": "1.0", "matika_version": "0.0.4"})

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
    loader.load_menus()

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


def test_load_menus_parses_application_and_roles(plugin_dir):
    """load_menus() correctly parses application and roles from a plugin *_menus.json."""
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
    result = loader.load_menus()

    assert "parse_plugin" in result
    assert result["parse_plugin"]["application"]["id"] == "parse-app"
    assert "Admin" in result["parse_plugin"]["roles"]
    assert result["parse_plugin"]["roles"]["Admin"]["id"] == "parse-admin"
    assert "User" not in result["parse_plugin"]["roles"]


def test_load_menus_returns_none_for_missing_application(plugin_dir):
    """load_menus() returns application=None when the section is absent from a plugin file."""
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
    result = loader.load_menus()

    assert result["noapp_plugin"]["application"] is None


def test_invalidate_cache_clears_cache(plugin_dir):
    """invalidate_cache() clears the unified menu cache."""
    from matika.core.menu_loader import MenuLoaderService
    from matika.core.paths import BASE_DIR
    core_menus_dir = os.path.join(BASE_DIR, "src", "matika", "menus")
    loader = MenuLoaderService(core_menus_dir=core_menus_dir, plugins_dir=plugin_dir)

    loader.load_menus()
    assert loader._cache is not None

    loader.invalidate_cache()
    assert loader._cache is None


# ---------------------------------------------------------------------------
# Helpers for Admin dropdown aggregation tests
# ---------------------------------------------------------------------------

def _make_admin_plugin(plugin_dir, plugin_id, display_name, admin_items):
    """
    Create a minimal plugin with an application section and flat Admin role
    items (no Menu wrapper — items insert directly into the aggregated Admin
    dropdown).
    """
    p_path = os.path.join(plugin_dir, plugin_id)
    os.makedirs(p_path)

    manifest = {
        "id": plugin_id,
        "version": "1.0",
        "matika_version": get_matika_version(),
        "name": display_name,
        "display_name": display_name,
        "entry_point": "plugin.MockPlugin",
    }
    with open(os.path.join(p_path, "applug.json"), "w") as f:
        json.dump(manifest, f)

    menus_data = {
        "schema_version": "1.0",
        "menus": {
            "application": {
                "id": f"{plugin_id}-app",
                "label_key": f"menu_{plugin_id}",
                "items": [
                    {"type": "Link", "label_key": f"item_{plugin_id}_page",
                     "href": f"/{plugin_id}/page"}
                ],
            },
            "roles": [
                {
                    "role": "Admin",
                    "id": f"{plugin_id}-admin",
                    "label_key": f"menu_{plugin_id}",
                    "items": admin_items,
                }
            ],
        },
    }
    with open(os.path.join(p_path, f"{plugin_id}_menus.json"), "w") as f:
        json.dump(menus_data, f)

    with open(os.path.join(p_path, "plugin.py"), "w") as f:
        f.write(MOCK_PLUGIN_CONTENT)

    return p_path


def _admin_dropdown_from_hub(hub):
    """Return the Admin Menu entry from a hub list, or None."""
    return next(
        (m for m in hub if m.get("type") == "Menu" and m.get("label") == "Admin"),
        None,
    )


def _section_header_labels(dropdown):
    """Return labels of all SectionHeader items inside a dropdown's items list."""
    return [i["label"] for i in dropdown["items"] if i.get("type") == "SectionHeader"]


def _all_hrefs_in_dropdown(dropdown):
    """Collect hrefs from all direct and one-level-deep items in a dropdown."""
    hrefs = []
    for item in dropdown.get("items", []):
        if item.get("href"):
            hrefs.append(item["href"])
        for sub in item.get("items", []):
            if sub.get("href"):
                hrefs.append(sub["href"])
    return hrefs


# ---------------------------------------------------------------------------
# Admin dropdown aggregation — section header rules
# ---------------------------------------------------------------------------

def test_admin_dropdown_single_source_no_section_headers(plugin_dir, db):
    """Single source (System only, no plugin admin items) → no SectionHeaders."""
    # Plugin with application menu only — no roles section.
    p_path = os.path.join(plugin_dir, "norl_plugin")
    os.makedirs(p_path)
    manifest = {
        "id": "norl_plugin", "version": "1.0",
        "matika_version": get_matika_version(),
        "name": "NoRl Plugin", "entry_point": "plugin.MockPlugin",
    }
    with open(os.path.join(p_path, "applug.json"), "w") as f:
        json.dump(manifest, f)
    menus_data = {
        "schema_version": "1.0",
        "menus": {
            "application": {
                "id": "norl-app", "label_key": "menu_norl",
                "items": [{"type": "Link", "label_key": "item_norl", "href": "/norl/page"}],
            }
        },
    }
    with open(os.path.join(p_path, "norl_plugin_menus.json"), "w") as f:
        json.dump(menus_data, f)
    with open(os.path.join(p_path, "plugin.py"), "w") as f:
        f.write(MOCK_PLUGIN_CONTENT)

    service = AppLugService(plugins_dir=plugin_dir)
    service.discover(db)
    result = service.get_menus_for_context(user_roles=["Admin"], t={})

    admin_dd = _admin_dropdown_from_hub(result["hubs"]["__default__"])
    assert admin_dd is not None, "Admin dropdown must be present for Admin user"
    assert _section_header_labels(admin_dd) == [], (
        f"Single-source Admin dropdown must not have SectionHeaders. "
        f"Items: {admin_dd['items']}"
    )


def test_admin_dropdown_two_sources_has_section_headers(plugin_dir, db):
    """Two sources (System + one plugin) → both SectionHeaders present."""
    _make_admin_plugin(
        plugin_dir, "alpha_plugin", "Alpha",
        [{"type": "Link", "label_key": "item_alpha_admin", "href": "/alpha/admin"}],
    )
    service = AppLugService(plugins_dir=plugin_dir)
    service.discover(db)
    result = service.get_menus_for_context(user_roles=["Admin"], t={})

    admin_dd = _admin_dropdown_from_hub(result["hubs"]["__default__"])
    assert admin_dd is not None
    headers = _section_header_labels(admin_dd)
    assert "System" in headers, f"System header expected. Got: {headers}"
    assert "Alpha" in headers, f"Alpha header expected. Got: {headers}"


def test_admin_dropdown_three_sources_has_section_headers(plugin_dir, db):
    """Three sources (System + two plugins) → all three SectionHeaders present."""
    _make_admin_plugin(
        plugin_dir, "beta_plugin", "Beta",
        [{"type": "Link", "label_key": "item_beta_admin", "href": "/beta/admin"}],
    )
    _make_admin_plugin(
        plugin_dir, "gamma_plugin", "Gamma",
        [{"type": "Link", "label_key": "item_gamma_admin", "href": "/gamma/admin"}],
    )
    service = AppLugService(plugins_dir=plugin_dir)
    service.discover(db)
    result = service.get_menus_for_context(user_roles=["Admin"], t={})

    admin_dd = _admin_dropdown_from_hub(result["hubs"]["__role_Admin__"])
    assert admin_dd is not None
    headers = _section_header_labels(admin_dd)
    assert "System" in headers, f"System header missing. Got: {headers}"
    assert "Beta" in headers, f"Beta header missing. Got: {headers}"
    assert "Gamma" in headers, f"Gamma header missing. Got: {headers}"
    assert len(headers) == 3, f"Expected exactly 3 headers. Got: {headers}"


def test_admin_dropdown_header_order_system_first(plugin_dir, db):
    """System SectionHeader is always the first header in the dropdown."""
    _make_admin_plugin(
        plugin_dir, "delta_plugin", "Delta",
        [{"type": "Link", "label_key": "item_delta_admin", "href": "/delta/admin"}],
    )
    service = AppLugService(plugins_dir=plugin_dir)
    service.discover(db)
    result = service.get_menus_for_context(user_roles=["Admin"], t={})

    admin_dd = _admin_dropdown_from_hub(result["hubs"]["__default__"])
    assert admin_dd is not None
    headers = _section_header_labels(admin_dd)
    assert len(headers) >= 2
    assert headers[0] == "System", (
        f"System must be the first SectionHeader. Got order: {headers}"
    )


def test_user_role_hub_has_no_section_headers(plugin_dir, db):
    """User role hub dropdowns never contain SectionHeader items."""
    p_path = os.path.join(plugin_dir, "epsilon_plugin")
    os.makedirs(p_path)
    manifest = {
        "id": "epsilon_plugin", "version": "1.0",
        "matika_version": get_matika_version(),
        "name": "Epsilon", "display_name": "Epsilon",
        "entry_point": "plugin.MockPlugin",
    }
    with open(os.path.join(p_path, "applug.json"), "w") as f:
        json.dump(manifest, f)
    menus_data = {
        "schema_version": "1.0",
        "menus": {
            "application": {
                "id": "epsilon-app", "label_key": "menu_epsilon",
                "items": [{"type": "Link", "label_key": "item_epsilon", "href": "/epsilon/page"}],
            },
            "roles": [
                {
                    "role": "Admin",
                    "id": "epsilon-admin",
                    "label_key": "menu_epsilon",
                    "items": [
                        {"type": "Link", "label_key": "item_epsilon_admin", "href": "/epsilon/admin"}
                    ],
                },
                {
                    "role": "User",
                    "id": "epsilon-user",
                    "label_key": "menu_epsilon",
                    "items": [
                        {
                            "type": "Menu",
                            "label_key": "menu_epsilon",
                            "items": [
                                {"type": "Link", "label_key": "item_epsilon", "href": "/epsilon/page"}
                            ],
                        }
                    ],
                },
            ],
        },
    }
    with open(os.path.join(p_path, "epsilon_plugin_menus.json"), "w") as f:
        json.dump(menus_data, f)
    with open(os.path.join(p_path, "plugin.py"), "w") as f:
        f.write(MOCK_PLUGIN_CONTENT)

    service = AppLugService(plugins_dir=plugin_dir)
    service.discover(db)
    result = service.get_menus_for_context(user_roles=["User"], t={})
    user_hub = result["hubs"]["__role_User__"]

    all_items = []
    for entry in user_hub:
        all_items.extend(entry.get("items", []))

    section_headers = [i for i in all_items if i.get("type") == "SectionHeader"]
    assert section_headers == [], (
        f"User role hub must not contain SectionHeaders. Found: {section_headers}"
    )


def test_filter_items_respected_in_aggregated_admin_dropdown(plugin_dir, db):
    """Role-restricted items inside plugin admin section are filtered before aggregation."""
    p_path = os.path.join(plugin_dir, "zeta_plugin")
    os.makedirs(p_path)
    manifest = {
        "id": "zeta_plugin", "version": "1.0",
        "matika_version": get_matika_version(),
        "name": "Zeta", "display_name": "Zeta",
        "entry_point": "plugin.MockPlugin",
    }
    with open(os.path.join(p_path, "applug.json"), "w") as f:
        json.dump(manifest, f)
    menus_data = {
        "schema_version": "1.0",
        "menus": {
            "application": {
                "id": "zeta-app", "label_key": "menu_zeta",
                "items": [{"type": "Link", "label_key": "item_zeta", "href": "/zeta/page"}],
            },
            "roles": [
                {
                    "role": "Admin",
                    "id": "zeta-admin",
                    "label_key": "menu_zeta",
                    "items": [
                        {"type": "Link", "label_key": "item_zeta_all", "href": "/zeta/admin"},
                        {
                            "type": "Link",
                            "label_key": "item_zeta_super",
                            "href": "/zeta/super",
                            "roles": ["SuperAdmin"],
                        },
                    ],
                }
            ],
        },
    }
    with open(os.path.join(p_path, "zeta_plugin_menus.json"), "w") as f:
        json.dump(menus_data, f)
    with open(os.path.join(p_path, "plugin.py"), "w") as f:
        f.write(MOCK_PLUGIN_CONTENT)

    service = AppLugService(plugins_dir=plugin_dir)
    service.discover(db)
    result = service.get_menus_for_context(user_roles=["Admin"], t={})

    admin_dd = _admin_dropdown_from_hub(result["hubs"]["__default__"])
    assert admin_dd is not None
    hrefs = _all_hrefs_in_dropdown(admin_dd)
    assert "/zeta/admin" in hrefs, f"Unrestricted link must be present. Hrefs: {hrefs}"
    assert "/zeta/super" not in hrefs, (
        f"SuperAdmin-only link must be filtered out. Hrefs: {hrefs}"
    )


def test_default_hub_admin_dropdown_aggregates_all_sources(plugin_dir, db):
    """Default hub Admin dropdown contains System items and all plugin admin items."""
    _make_admin_plugin(
        plugin_dir, "eta_plugin", "Eta",
        [{"type": "Link", "label_key": "item_eta_admin", "href": "/eta/admin"}],
    )
    service = AppLugService(plugins_dir=plugin_dir)
    service.discover(db)
    result = service.get_menus_for_context(user_roles=["Admin"], t={})

    admin_dd = _admin_dropdown_from_hub(result["hubs"]["__default__"])
    assert admin_dd is not None
    hrefs = _all_hrefs_in_dropdown(admin_dd)
    assert "/admin/roles" in hrefs, f"System link must be present. Hrefs: {hrefs}"
    assert "/eta/admin" in hrefs, f"Plugin admin link must be present. Hrefs: {hrefs}"


def test_admin_role_hub_admin_dropdown_aggregates_all_sources(plugin_dir, db):
    """Admin role hub Admin dropdown aggregates System + all plugin admin items."""
    _make_admin_plugin(
        plugin_dir, "theta_plugin", "Theta",
        [{"type": "Link", "label_key": "item_theta_admin", "href": "/theta/admin"}],
    )
    service = AppLugService(plugins_dir=plugin_dir)
    service.discover(db)
    result = service.get_menus_for_context(user_roles=["Admin"], t={})

    admin_hub = result["hubs"]["__role_Admin__"]
    admin_dd = _admin_dropdown_from_hub(admin_hub)
    assert admin_dd is not None, f"Admin dropdown must be in Admin role hub. Hub: {admin_hub}"

    hrefs = _all_hrefs_in_dropdown(admin_dd)
    assert "/admin/roles" in hrefs, f"System link must be in Admin role hub. Hrefs: {hrefs}"
    assert "/theta/admin" in hrefs, f"Plugin link must be in Admin role hub. Hrefs: {hrefs}"


def test_plugin_app_hub_admin_dropdown_single_source_no_headers(plugin_dir, db):
    """Per-plugin app hub Admin dropdown: only plugin items, no System, no SectionHeaders."""
    _make_admin_plugin(
        plugin_dir, "iota_plugin", "Iota",
        [{"type": "Link", "label_key": "item_iota_admin", "href": "/iota/admin"}],
    )
    service = AppLugService(plugins_dir=plugin_dir)
    service.discover(db)
    result = service.get_menus_for_context(user_roles=["Admin"], t={})

    iota_hub = result["hubs"].get("iota_plugin", [])
    assert iota_hub, "iota_plugin hub must exist"

    admin_dd = _admin_dropdown_from_hub(iota_hub)
    assert admin_dd is not None, f"Admin dropdown must be in plugin hub. Hub: {iota_hub}"

    hrefs = _all_hrefs_in_dropdown(admin_dd)
    assert "/iota/admin" in hrefs, f"Plugin link must be present. Hrefs: {hrefs}"
    assert "/admin/roles" not in hrefs, (
        f"System link must NOT appear in plugin-only Admin dropdown. Hrefs: {hrefs}"
    )
    assert _section_header_labels(admin_dd) == [], (
        f"Single-source plugin hub Admin dropdown must not have SectionHeaders."
    )


def test_admin_dropdown_absent_for_non_admin_user(plugin_dir, db):
    """Non-admin users never see an Admin dropdown in the default hub."""
    _make_admin_plugin(
        plugin_dir, "kappa_plugin", "Kappa",
        [{"type": "Link", "label_key": "item_kappa_admin", "href": "/kappa/admin"}],
    )
    service = AppLugService(plugins_dir=plugin_dir)
    service.discover(db)
    result = service.get_menus_for_context(user_roles=["User"], t={})

    admin_dd = _admin_dropdown_from_hub(result["hubs"]["__default__"])
    assert admin_dd is None, (
        f"Non-admin user must not receive an Admin dropdown. Hub: {result['hubs']['__default__']}"
    )
