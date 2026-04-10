import pytest
from matika.database import Security, SecurityType, AssetClass, init_db

def test_securities_list_basic(client, test_admin, db):
    init_db(db)
    # Log in as admin
    client.post("/login", data={"email": test_admin.email, "password": "adminpassword"}, follow_redirects=False)
    
    # Manually add a security to ensure it's in the DB session used by the route
    new_sec = Security(
        symbol="TEST", 
        name="Test Security", 
        security_type=SecurityType.STOCK,
        asset_class=AssetClass.LARGE_CAP_STOCK
    )
    db.add(new_sec)
    db.commit()

    # List
    resp = client.get("/admin/securities")
    assert resp.status_code == 200
    assert "TEST" in resp.text
    assert "Test Security" in resp.text
    assert AssetClass.LARGE_CAP_STOCK.value in resp.text

def test_maintenance_layout_elements(client, test_admin, db):
    init_db(db)
    client.post("/login", data={"email": test_admin.email, "password": "adminpassword"}, follow_redirects=False)
    
    resp = client.get("/admin/securities")
    assert resp.status_code == 200
    assert 'class="browse-panel"' in resp.text
    assert 'class="maintenance-panel"' in resp.text
    assert 'class="advanced-search-panel"' in resp.text
    assert 'class="button-bar-panel"' in resp.text
    assert 'class="maintenance-form"' in resp.text
    assert 'class="save-panel"' in resp.text

def test_securities_crud(client, test_admin, db):
    init_db(db)
    # Log in as admin
    client.post("/login", data={"email": test_admin.email, "password": "adminpassword"}, follow_redirects=False)
    
    # 1. Create
    resp = client.post("/admin/securities/create", data={
        "symbol": "VOO",
        "name": "Vanguard S&P 500 ETF",
        "security_type": SecurityType.ETF.value,
        "asset_class": AssetClass.LARGE_CAP_STOCK.value,
        "current_price": "450.00"
    }, follow_redirects=False)
    assert resp.status_code == 303
    
    sec = db.query(Security).filter(Security.symbol == "VOO").first()
    assert sec is not None
    assert sec.asset_class == AssetClass.LARGE_CAP_STOCK

    # 2. Update
    resp = client.post(f"/admin/securities/update/{sec.id}", data={
        "symbol": "VOO",
        "name": "Vanguard S&P 500 ETF Updated",
        "security_type": SecurityType.ETF.value,
        "asset_class": AssetClass.SMALL_CAP_STOCK.value,
        "current_price": "460.00"
    }, follow_redirects=False)
    assert resp.status_code == 303
    db.refresh(sec)
    assert sec.asset_class == AssetClass.SMALL_CAP_STOCK

    # 3. Delete
    resp = client.post(f"/admin/securities/delete/{sec.id}", follow_redirects=False)
    assert resp.status_code == 303
    deleted_sec = db.query(Security).filter(Security.id == sec.id).first()
    assert deleted_sec is None

def test_user_denied_securities(client, test_user, db):
    init_db(db)
    client.post("/login", data={"email": test_user.email, "password": "testpassword"}, follow_redirects=False)
    
    # User should be denied access to admin securities page
    resp = client.get("/admin/securities")
    assert resp.status_code == 403
