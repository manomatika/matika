import pytest
import os
from matika.main import app_lug_service, app, init_plugins
from matika.database import Role, Permission, PermissionLevel

@pytest.fixture(autouse=True)
def setup_plugin_service(db):
    # Force the service to use our local plugins directory for tests
    app_lug_service.plugins_dir = os.path.expanduser("~/Matika/plugins")
    # Reset loaded plugins to ensure clean discovery
    app_lug_service.loaded_plugins = {}
    init_plugins(db)
    yield

def test_eyerate_plugin_discovery(db):
    # The plugin was linked to ~/Matika/plugins/eyerate
    # It should be discoverable
    assert any(p.id == "eyerate" for p in app_lug_service.loaded_plugins.values())
    
    # Verify tables created
    from sqlalchemy import inspect
    inspector = inspect(db.get_bind())
    assert "securities" in inspector.get_table_names()

def test_eyerate_routes_registered():
    # Verify securities route is in the FastAPI app
    # After discovery, the routers should be included
    from matika.main import app
    paths = [r.path for r in app.routes]
    assert "/admin/securities" in paths

def test_eyerate_permissions_provisioned(db):
    admin_role = db.query(Role).filter(Role.name == "Admin").first()
    perm = db.query(Permission).filter(
        Permission.role_id == admin_role.id,
        Permission.page_path == "/admin/securities"
    ).first()
    
    assert perm is not None
    assert perm.level == PermissionLevel.FULL

def test_eyerate_menu_items_presence():
    items = app_lug_service.get_all_menu_items()
    assert any(item["href"] == "/admin/securities" for item in items)
