import pytest
import os
from matika.database import Role, Permission, PermissionLevel

def test_eyerate_plugin_discovery(test_app, db):
    service = test_app.state.app_lug_service
    assert any(p.id == "eyerate" for p in service.loaded_plugins.values())
    
    # Verify tables created
    from sqlalchemy import inspect
    inspector = inspect(db.get_bind())
    assert "securities" in inspector.get_table_names()

def test_eyerate_routes_registered(test_app):
    # Verify securities route is in the FastAPI app
    paths = [r.path for r in test_app.routes]
    assert "/admin/securities" in paths

def test_eyerate_permissions_provisioned(test_app, db):
    admin_role = db.query(Role).filter(Role.name == "Admin").first()
    perm = db.query(Permission).filter(
        Permission.role_id == admin_role.id,
        Permission.page_path == "/admin/securities"
    ).first()
    
    assert perm is not None
    assert perm.level == PermissionLevel.FULL

def test_eyerate_menu_items_presence(test_app):
    service = test_app.state.app_lug_service
    items = service.get_all_menu_items()
    assert any(item["href"] == "/admin/securities" for item in items)

def test_list_securities_authenticated(client, test_admin, db):
    # Log in
    client.post("/login", data={"email": test_admin.email, "password": "adminpassword"})
    
    # Access securities page
    resp = client.get("/admin/securities")
    assert resp.status_code == 200
    # Search for translated text or the raw key if not merged yet
    assert "Securities" in resp.text or "item_securities" in resp.text

def test_create_financial_security(client, test_admin, db):
    client.post("/login", data={"email": test_admin.email, "password": "adminpassword"})
    
    data = {
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "security_type": "Stock",
        "asset_class": "Large Cap Stock"
    }
    resp = client.post("/admin/securities/create", data=data, follow_redirects=True)
    assert resp.status_code == 200
    assert "AAPL" in resp.text
    
    # Verify in DB
    from eyerate.models import FinancialSecurity
    sec = db.query(FinancialSecurity).filter(FinancialSecurity.symbol == "AAPL").first()
    assert sec is not None
    assert sec.name == "Apple Inc."

def test_search_securities_mock(client, test_admin, db):
    client.post("/login", data={"email": test_admin.email, "password": "adminpassword"})
    
    # Add a security to search for
    from eyerate.models import FinancialSecurity
    db.add(FinancialSecurity(symbol="MSFT", name="Microsoft", financial_security_type="Stock"))
    db.commit()
    
    resp = client.get("/admin/securities/search?q=MSFT")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)

def test_dynamic_menu_rendering(client, test_admin, db):
    client.post("/login", data={"email": test_admin.email, "password": "adminpassword"})
    
    resp = client.get("/")
    assert resp.status_code == 200
    # Should see "Securities" or "item_securities" in the Activities dropdown
    assert "Securities" in resp.text or "item_securities" in resp.text
    assert "/admin/securities" in resp.text
