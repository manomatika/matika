import pytest
from matika.database import Security, SecurityType, init_db

def test_duplicate_symbol_prevention(client, test_admin, db):
    init_db(db)
    # Log in as admin
    client.post("/login", data={"email": test_admin.email, "password": "adminpassword"}, follow_redirects=False)
    
    # Create a security
    data = {
        "symbol": "VOO",
        "name": "Vanguard S&P 500 ETF",
        "security_type": SecurityType.ETF.value
    }
    resp = client.post("/admin/securities/create", data=data, follow_redirects=True)
    assert resp.status_code == 200
    
    # Try to create the same symbol again
    resp = client.post("/admin/securities/create", data=data, follow_redirects=False)
    assert resp.status_code == 400
    assert "already exists" in resp.json()["detail"]

def test_symbol_case_insensitivity(client, test_admin, db):
    init_db(db)
    client.post("/login", data={"email": test_admin.email, "password": "adminpassword"}, follow_redirects=False)
    
    # Create initial
    client.post("/admin/securities/create", data={
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "security_type": SecurityType.STOCK.value
    })
    
    # Try lowercase version
    resp = client.post("/admin/securities/create", data={
        "symbol": "aapl",
        "name": "Apple Inc. Duplicate",
        "security_type": SecurityType.STOCK.value
    })
    assert resp.status_code == 400
