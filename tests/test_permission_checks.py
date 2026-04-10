import pytest
from matika.database import Permission, PermissionLevel, Role, User, PageType, init_db

def test_admin_access_maintenance(client, db, test_admin):
    init_db(db)
    # Log in as admin
    client.post("/login", data={"email": test_admin.email, "password": "adminpassword"}, follow_redirects=False)
    
    # Access admin users page
    resp = client.get("/admin/users")
    assert resp.status_code == 200
    assert "Users" in resp.text

def test_user_denied_maintenance(client, db, test_user):
    user_role = db.query(Role).filter(Role.name == "User").first()
    if user_role not in test_user.roles:
        test_user.roles.append(user_role)
    db.commit()
    init_db(db)

    client.post("/login", data={"email": test_user.email, "password": "testpassword"}, follow_redirects=False)
    
    # Access admin users page -> should be 403
    resp = client.get("/admin/users")
    assert resp.status_code == 403
    assert "Access Denied" in resp.text or "Acceso Denegado" in resp.text

def test_user_access_settings(client, db, test_user):
    user_role = db.query(Role).filter(Role.name == "User").first()
    if user_role not in test_user.roles:
        test_user.roles.append(user_role)
    db.commit()
    init_db(db)

    client.post("/login", data={"email": test_user.email, "password": "testpassword"}, follow_redirects=False)
    
    # Access user settings -> should be allowed
    resp = client.get("/settings/user")
    assert resp.status_code == 200
    assert "User Settings" in resp.text

def test_explicit_user_override_denied(client, db, test_user):
    init_db(db)
    
    # Ensure user has NO roles that might grant it
    test_user.roles = []
    
    # Add explicit NONE for /settings/user for this specific user
    db.add(Permission(page_path="/settings/user", page_type=PageType.SETTINGS, user_id=test_user.id, level=PermissionLevel.NONE))
    db.commit()
    
    client.post("/login", data={"email": test_user.email, "password": "testpassword"}, follow_redirects=False)
    
    resp = client.get("/settings/user")
    assert resp.status_code == 403
