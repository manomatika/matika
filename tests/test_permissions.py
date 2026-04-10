import pytest
from matika.database import Permission, PermissionLevel, Role, User, PageType

def test_seeding_defaults(db):
    # We want to test init_db seeding without locking the DB.
    from matika.database import init_db
    init_db(db)
    
    admin_role = db.query(Role).filter(Role.name == "Admin").first()
    user_role = db.query(Role).filter(Role.name == "User").first()
    
    # Issue 4: Admin role gets FULL for all pages
    admin_perms = db.query(Permission).filter(Permission.role_id == admin_role.id).all()
    assert len(admin_perms) >= 17
    for p in admin_perms:
        assert p.level == PermissionLevel.FULL

    # Issue 4: User role gets NONE for admin menu pages, FULL for others
    admin_menu_pages = ["/admin/roles", "/admin/permissions", "/admin/users", "/settings/system", "/admin/settings/export", "/admin/settings/import"]
    user_perms = db.query(Permission).filter(Permission.role_id == user_role.id).all()
    for p in user_perms:
        if p.page_path in admin_menu_pages:
            assert p.level == PermissionLevel.NONE
        else:
            assert p.level == PermissionLevel.FULL

def test_permission_logic_exclusivity(client, db, test_admin):
    # Log in as admin
    client.post("/login", data={"email": test_admin.email, "password": "adminpassword"}, follow_redirects=False)
    
    admin_role = db.query(Role).filter(Role.name == "Admin").first()
    test_path = "/admin/users"
    
    # 1. Start with FULL (seeded in conftest or init_db)
    # Actually conftest seeds Admin/User roles but maybe not permissions.
    # Let's ensure we have a baseline.
    db.add(Permission(page_path=test_path, page_type=PageType.MAINTENANCE, role_id=admin_role.id, level=PermissionLevel.FULL))
    db.commit()

    # 2. Add READ -> Should delete FULL and add READ
    resp = client.post("/admin/permissions/create", data={
        "page_path": test_path,
        "subject": f"role:{admin_role.id}",
        "level": PermissionLevel.READ.value
    }, follow_redirects=False)
    assert resp.status_code == 303
    
    perms = db.query(Permission).filter(Permission.page_path == test_path, Permission.role_id == admin_role.id).all()
    assert len(perms) == 1
    assert perms[0].level == PermissionLevel.READ
    
    # 3. Add UPDATE -> Should have READ and UPDATE
    client.post("/admin/permissions/create", data={
        "page_path": test_path,
        "subject": f"role:{admin_role.id}",
        "level": PermissionLevel.UPDATE.value
    }, follow_redirects=False)
    perms = db.query(Permission).filter(Permission.page_path == test_path, Permission.role_id == admin_role.id).all()
    assert len(perms) == 2
    levels = {p.level for p in perms}
    assert levels == {PermissionLevel.READ, PermissionLevel.UPDATE}
    
    # 4. Add FULL -> Should delete READ and UPDATE and add ONLY FULL
    client.post("/admin/permissions/create", data={
        "page_path": test_path,
        "subject": f"role:{admin_role.id}",
        "level": PermissionLevel.FULL.value
    }, follow_redirects=False)
    perms = db.query(Permission).filter(Permission.page_path == test_path, Permission.role_id == admin_role.id).all()
    assert len(perms) == 1
    assert perms[0].level == PermissionLevel.FULL

    # 5. Add NONE -> Should delete FULL and add ONLY NONE
    client.post("/admin/permissions/create", data={
        "page_path": test_path,
        "subject": f"role:{admin_role.id}",
        "level": PermissionLevel.NONE.value
    }, follow_redirects=False)
    perms = db.query(Permission).filter(Permission.page_path == test_path, Permission.role_id == admin_role.id).all()
    assert len(perms) == 1
    assert perms[0].level == PermissionLevel.NONE

def test_at_least_one_permission(client, db, test_admin):
    client.post("/login", data={"email": test_admin.email, "password": "adminpassword"}, follow_redirects=False)
    admin_role = db.query(Role).filter(Role.name == "Admin").first()
    test_path = "/admin/users"
    
    # Clearing permissions should reset to NONE
    client.post("/admin/permissions/delete-subject", data={
        "page_path": test_path,
        "subject": f"role:{admin_role.id}"
    }, follow_redirects=False)
    
    perms = db.query(Permission).filter(Permission.page_path == test_path, Permission.role_id == admin_role.id).all()
    assert len(perms) == 1
    assert perms[0].level == PermissionLevel.NONE
