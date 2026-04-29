import pytest
import os
import json
from io import BytesIO
from fastapi import Depends, HTTPException
from matika.core.logging_config import setup_startup_logging, rotate_logs, cleanup_logs, finalize_logging, LOG_DIR
from matika.data_mgmt.export_import import get_activity_categories
from matika.core import paths
from matika.database import PageType

def test_logging_rotation_and_cleanup(db):
    setup_startup_logging(is_testing=False)
    rotate_logs(is_testing=False)
    for i in range(5):
        with open(os.path.join(LOG_DIR, f"test_log_{i}.log"), "w") as f:
            f.write("test")
    cleanup_logs(db, is_testing=False)
    finalize_logging(is_testing=False)
    assert os.path.exists(LOG_DIR)

def test_export_import_categories(db):
    t = {"label_include_logging": "Logging", "label_include_system_roles": "Roles"}
    cats = get_activity_categories(db, "system_data", t)
    assert any(c["id"] == "logging" for c in cats)
    user_cats = get_activity_categories(db, "user_data", t)
    assert any(c["id"] == "roles" for c in user_cats)

def test_export_import_metadata_scanning(db, tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "BASE_DIR", str(tmp_path))
    metadata_dir = tmp_path / "src" / "matika" / "metadata"
    metadata_dir.mkdir(parents=True)
    meta = {"export_import": {"supports_user_data": True, "user_data_categories": [{"id": "extra", "name": "inc_extra", "label_key": "label_extra"}]}}
    with open(metadata_dir / "extra_maint_activity_metadata.json", "w") as f:
        json.dump(meta, f)
    t = {"label_extra": "Extra Data"}
    cats = get_activity_categories(db, "user_data", t)
    assert any(c["id"] == "extra" for c in cats)

def test_admin_settings_export_post(client, test_admin):
    client.post("/login", data={"email": test_admin.email, "password": "adminpassword"})
    data = {"filename": "full_export.json", "include_logging": "on", "include_system_roles": "on"}
    resp = client.post("/admin/settings/export", data=data)
    assert resp.status_code == 200
    assert resp.json()["metadata"]["type"] == "system_config"

def test_settings_import_roles_logic(client, test_admin, db):
    client.post("/login", data={"email": test_admin.email, "password": "adminpassword"})
    payload = {"metadata": {"type": "user_data"}, "roles": [{"name": "NewCustomRole", "description": "Custom", "permissions": [{"path": "/custom", "type": "Info", "level": "Full"}]}]}
    file_content = json.dumps(payload).encode("utf-8")
    files = {"file": ("test.json", BytesIO(file_content), "application/json")}
    resp = client.post("/settings/import", data={"include_roles": "on"}, files=files, follow_redirects=True)
    assert resp.status_code == 200
    from matika.database import Role
    role = db.query(Role).filter(Role.name == "NewCustomRole").first()
    assert role is not None

def test_admin_update_role_with_users(client, test_admin, test_user, db):
    client.post("/login", data={"email": test_admin.email, "password": "adminpassword"})
    from matika.database import Role
    role = Role(name="UserUpdateRole", description="Test")
    db.add(role); db.commit()
    resp = client.post(f"/admin/roles/update/{role.id}", data={"name": "NewName", "description": "NewDesc", "user_ids": f"{test_user.id}"}, follow_redirects=True)
    assert resp.status_code == 200
    db.refresh(role)
    assert role.name == "NewName"
    assert len(role.users) == 1

def test_admin_update_user_with_roles(client, test_admin, test_user, db):
    client.post("/login", data={"email": test_admin.email, "password": "adminpassword"})
    from matika.database import Role
    role = Role(name="ExtraRole", description="Test")
    db.add(role); db.commit()
    resp = client.post(f"/admin/users/update/{test_user.id}", data={"email": "new@new.com", "username": "newname", "role_ids": f"{role.id}", "force_password_change": "true"}, follow_redirects=True)
    assert resp.status_code == 200
    db.refresh(test_user)
    assert test_user.email == "new@new.com"
    assert role in test_user.roles

def test_user_upload_photo_not_image(client, test_user):
    client.post("/login", data={"email": test_user.email, "password": "testpassword"})
    files = {"file": ("test.txt", b"not an image", "text/plain")}
    resp = client.post("/settings/user/upload-photo", files=files)
    assert resp.status_code == 400

def test_user_get_photo_not_found(client, test_user):
    client.post("/login", data={"email": test_user.email, "password": "testpassword"})
    resp = client.get("/settings/user/photo/9999")
    assert resp.status_code == 404

def test_user_change_password_mismatch(client, test_user):
    client.post("/login", data={"email": test_user.email, "password": "testpassword"})
    resp = client.post("/settings/user/change-password", data={"current_password": "testpassword", "new_password": "newpassword123", "confirm_password": "wrong"})
    assert "Passwords do not match" in resp.text

def test_user_change_password_incorrect_current(client, test_user):
    client.post("/login", data={"email": test_user.email, "password": "testpassword"})
    resp = client.post("/settings/user/change-password", data={"current_password": "wrong", "new_password": "newpassword123", "confirm_password": "newpassword123"})
    assert "Current password is incorrect" in resp.text

def test_settings_import_roles_not_in_data(client, test_admin):
    client.post("/login", data={"email": test_admin.email, "password": "adminpassword"})
    payload = {"metadata": {"type": "user_data"}}
    file_content = json.dumps(payload).encode("utf-8")
    files = {"file": ("test.json", BytesIO(file_content), "application/json")}
    resp = client.post("/settings/import", data={"include_roles": "on"}, files=files, follow_redirects=True)
    assert resp.status_code == 200

def test_save_system_settings_full(client, test_admin):
    client.post("/login", data={"email": test_admin.email, "password": "adminpassword"})
    data = {"app_log_lines": "200", "app_log_retention": "20", "startup_log_lines": "200", "startup_log_retention": "20", "test_log_lines": "200", "test_log_retention": "20"}
    resp = client.post("/settings/system", data=data, follow_redirects=True)
    assert resp.status_code == 200

def test_admin_settings_import_invalid_type(client, test_admin):
    client.post("/login", data={"email": test_admin.email, "password": "adminpassword"})
    bad_payload = {"metadata": {"type": "wrong"}}
    file_content = json.dumps(bad_payload).encode("utf-8")
    files = {"file": ("bad.json", BytesIO(file_content), "application/json")}
    resp = client.post("/admin/settings/import", files=files, follow_redirects=True)
    assert "error=true" in str(resp.url)

def test_auth_service_token_logic():
    from matika.auth.service import create_access_token
    from datetime import timedelta
    token = create_access_token({"sub": "test"}, expires_delta=timedelta(minutes=5))
    assert token is not None

def test_main_unauthorized_handler(test_app):
    from fastapi.testclient import TestClient
    @test_app.get("/trigger-403", tags=[PageType.INFO])
    async def trigger_403(): raise HTTPException(status_code=403)
    c = TestClient(test_app)
    resp = c.get("/trigger-403")
    assert resp.status_code == 403
    assert "Access Denied" in resp.text

def test_applug_base_methods():
    from matika.core.applug import BaseAppLug
    class SimplePlugin(BaseAppLug):
        def on_load(self, db): pass
        def on_unload(self, db): pass
    from matika.core.paths import get_matika_version
    manifest = {"id": "simple", "version": "1.0", "matika_version": get_matika_version()}
    p = SimplePlugin(manifest)
    assert p.id == "simple"
    assert p.version == "1.0"
    assert p.matika_version == get_matika_version()
    assert p.get_router() is not None

def test_auth_setup_oauth():
    from matika.auth.service import setup_oauth
    oauth = setup_oauth()
    assert "google" in oauth._registry
    assert "github" in oauth._registry

def test_export_import_metadata_error(db, tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "BASE_DIR", str(tmp_path))
    metadata_dir = tmp_path / "src" / "matika" / "metadata"
    metadata_dir.mkdir(parents=True)
    with open(metadata_dir / "bad_maint_activity_metadata.json", "w") as f:
        f.write("invalid json")
    cats = get_activity_categories(db, "user_data", {})
    assert len(cats) >= 1

def test_auth_dependencies_no_user(test_app):
    from matika.auth.dependencies import login_required
    from fastapi.testclient import TestClient
    
    # Register route on the test_app instance
    @test_app.get("/must-login-test", tags=[PageType.INFO])
    async def must_login(user=Depends(login_required)): return {"ok": True}
    
    c = TestClient(test_app)
    resp = c.get("/must-login-test")
    assert resp.status_code == 401

def test_utils_load_metadata_no_file():
    from matika.core.utils import load_metadata
    meta = load_metadata("nothing", metadata_dir="/tmp/nonexistent")
    assert meta == {}

def test_applug_service_menus_structure():
    from matika.core.applug_service import AppLugService
    s = AppLugService()
    result = s.get_menus_for_context(user_roles=[], t={})
    assert isinstance(result, dict)
    assert "selector" in result
    assert "hubs" in result
    # Only "item"-type entries have an id; separators and headers do not.
    selector_item_ids = [e["id"] for e in result["selector"] if e.get("type") == "item"]
    assert "__default__" in selector_item_ids
    assert "__favorites__" in selector_item_ids
    assert "__default__" in result["hubs"]
    assert "__favorites__" in result["hubs"]
