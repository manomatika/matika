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
    
    # Create manifest
    manifest = {
        "id": "test_plugin",
        "version": "1.0.0",
        "entry_point": "plugin:MockPlugin",
        "permissions": [
            {
                "page_path": "/test/plugin/page",
                "page_type": "Maintenance",
                "roles": {
                    "Admin": "Full",
                    "PluginRole": "Read"
                }
            }
        ],
        "menu_items": [
            {"label_key": "test_item", "href": "/test/plugin/page"}
        ]
    }
    with open(os.path.join(p_path, "applug.json"), "w") as f:
        json.dump(manifest, f)
        
    # Create plugin code
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
    
    # Check if PluginRole was auto-created
    role = db.query(Role).filter(Role.name == "PluginRole").first()
    assert role is not None
    
    # Check permissions
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

def test_plugin_menu_aggregation(plugin_dir, mock_plugin, db):
    service = AppLugService(plugins_dir=plugin_dir)
    service.discover(db)
    
    menu_items = service.get_all_menu_items()
    assert len(menu_items) == 1
    assert menu_items[0]["label_key"] == "test_item"

def test_resilience_to_faulty_plugins(plugin_dir, db):
    # Create a plugin with a broken manifest
    broken_path = os.path.join(plugin_dir, "broken_plugin")
    os.makedirs(broken_path)
    with open(os.path.join(broken_path, "applug.json"), "w") as f:
        f.write("invalid json")
        
    service = AppLugService(plugins_dir=plugin_dir)
    # This should not raise an exception
    plugins = service.discover(db)
    assert len(plugins) == 0

def test_resilience_to_missing_entry_point(plugin_dir, db):
    # Plugin with manifest but no code
    missing_path = os.path.join(plugin_dir, "missing_code")
    os.makedirs(missing_path)
    manifest = {"id": "missing", "version": "1.0", "entry_point": "nonexistent:Class"}
    with open(os.path.join(missing_path, "applug.json"), "w") as f:
        json.dump(manifest, f)
        
    service = AppLugService(plugins_dir=plugin_dir)
    # Should log error but not crash
    plugins = service.discover(db)
    assert len(plugins) == 0
