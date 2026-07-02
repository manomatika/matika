import pytest
import json
from io import BytesIO
from matika.database import Role, Permission, init_db, SystemSetting, PermissionLevel, PageType

def test_export_data_page(client, test_admin, db):
    client.post("/login", data={"email": test_admin.email, "password": "adminpassword"})
    response = client.get("/settings/export")
    assert response.status_code == 200
    assert "Export My Data" in response.text  # page heading uses heading_export_data, not link_export_data

def test_export_data_filtered(client, test_admin, db):
    client.post("/login", data={"email": test_admin.email, "password": "adminpassword"})
    
    # Test exporting ONLY roles
    data = {
        "filename": "only_roles.json",
        "include_roles": "on"
    }
    response = client.post("/settings/export", data=data)
    assert response.status_code == 200
    payload = response.json()
    
    assert "roles" in payload
    assert "securities" not in payload
    assert "system_settings" not in payload

def test_import_data_filtered(client, test_admin, db):
    client.post("/login", data={"email": test_admin.email, "password": "adminpassword"})
    
    export_payload = {
        "metadata": {"type": "user_data"},
        "roles": [
            {
                "name": "ImportedRole",
                "description": "Success",
                "permissions": []
            }
        ]
    }
    
    file_content = json.dumps(export_payload).encode("utf-8")
    files = {"file": ("test_import.json", BytesIO(file_content), "application/json")}
    
    # Import ONLY roles
    data = {
        "include_roles": "on"
    }
    
    response = client.post("/settings/import", files=files, data=data, follow_redirects=True)
    assert response.status_code == 200
    
    # Verify Role is there
    role = db.query(Role).filter(Role.name == "ImportedRole").first()
    assert role is not None

def test_system_export_import(client, test_admin, db):
    client.post("/login", data={"email": test_admin.email, "password": "adminpassword"})
    
    # 1. Test Export Page
    resp = client.get("/admin/settings/export")
    assert resp.status_code == 200
    assert "Export System Data" in resp.text

    # 2. Test Export POST
    data = {
        "filename": "sys_test.json",
        "include_logging": "on"
    }
    resp = client.post("/admin/settings/export", data=data)
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["metadata"]["type"] == "system_config"
    assert "aggregate_log_lines" in payload["system_settings"]
    # 3. Test Import
    payload["system_settings"]["aggregate_log_lines"] = "999"
    file_content = json.dumps(payload).encode("utf-8")
    files = {"file": ("sys_import.json", BytesIO(file_content), "application/json")}
    
    import_data = {
        "include_logging": "on"
    }
    resp = client.post("/admin/settings/import", files=files, data=import_data, follow_redirects=True)
    assert resp.status_code == 200
    
    # Verify change
    setting = db.query(SystemSetting).filter(SystemSetting.name == "aggregate_log_lines").first()
    assert setting.value == "999"

def test_system_export_include_roles(client, test_admin, db):
    client.post("/login", data={"email": test_admin.email, "password": "adminpassword"})
    
    data = {
        "filename": "sys_with_roles.json",
        "include_system_roles": "on"
    }
    resp = client.post("/admin/settings/export", data=data)
    assert resp.status_code == 200
    payload = resp.json()
    assert "roles" in payload
    assert any(r["name"] == "Admin" for r in payload["roles"])

def test_system_export_exclude_roles(client, test_admin, db):
    init_db(db)
    client.post("/login", data={"email": test_admin.email, "password": "adminpassword"})
    
    data = {
        "filename": "sys_no_roles.json",
        "include_system_roles": ""
    }
    resp = client.post("/admin/settings/export", data=data)
    assert resp.status_code == 200
    payload = resp.json()
    assert "roles" not in payload

def test_system_import_roles(client, test_admin, db):
    client.post("/login", data={"email": test_admin.email, "password": "adminpassword"})
    
    export_payload = {
        "metadata": {"type": "system_config"},
        "roles": [
            {
                "name": "Admin",
                "description": "Modified Admin Description",
                "is_system": True,
                "permissions": [
                    {"path": "/new/path", "type": "INFO", "level": "FULL"}
                ]
            }
        ]
    }
    
    file_content = json.dumps(export_payload).encode("utf-8")
    files = {"file": ("sys_roles_import.json", BytesIO(file_content), "application/json")}
    
    data = {"include_system_roles": "on"}
    
    resp = client.post("/admin/settings/import", files=files, data=data, follow_redirects=False)
    assert resp.status_code == 303
    
    # Verify change
    role = db.query(Role).filter(Role.name == "Admin").first()
    assert role.description == "Modified Admin Description"
    # Note: Import logic for system roles clears and re-adds permissions
    assert any(p.page_path == "/new/path" for p in role.permissions)
