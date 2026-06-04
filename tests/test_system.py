import pytest
import os
from matika.models import SystemSetting
from matika.database import get_system_setting

def test_system_settings_page(client, test_admin):
    # Log in
    client.post(
        "/login",
        data={"email": test_admin.email, "password": "adminpassword"}
    )
    
    response = client.get("/settings/system")
    assert response.status_code == 200
    assert "system_settings.html" in response.template.name
    assert "100" in response.text

def test_save_system_settings(client, test_admin, db):
    # Log in
    client.post(
        "/login",
        data={"email": test_admin.email, "password": "adminpassword"}
    )
    
    # Save settings
    response = client.post(
        "/settings/system",
        data={"app_log_lines": "250"},
        follow_redirects=True
    )
    assert response.status_code == 200

    # Verify in DB
    setting = db.query(SystemSetting).filter(SystemSetting.name == "app_log_lines").first()
    assert setting.value == "250"

def test_save_security_settings(client, test_admin, db):
    # Log in
    client.post(
        "/login",
        data={"email": test_admin.email, "password": "adminpassword"}
    )
    
    # Save security settings (45 minutes)
    response = client.post(
        "/settings/system",
        data={"session_idle_timeout": "45"},
        follow_redirects=True
    )
    assert response.status_code == 200

    # Verify in DB (should be 45 * 60 = 2700 seconds)
    setting = db.query(SystemSetting).filter(SystemSetting.name == "session_idle_timeout").first()
    assert setting.value == "2700"

def test_show_log(client, test_admin):
    # Log in
    client.post(
        "/login",
        data={"email": test_admin.email, "password": "adminpassword"}
    )
    
    # Create a dummy log file if it doesn't exist
    LOG_DIR = "logs"
    ACTIVE_LOG = os.path.join(LOG_DIR, "matika.log")
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(ACTIVE_LOG, "w") as f:
        f.write("Test log line 1\nTest log line 2\n")
    
    response = client.get("/show-log")
    assert response.status_code == 200
    assert "Test log line 2" in response.text

def test_unauthorized_access(client):
    # Try to access root without login
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    
    # Try to access settings without login
    response = client.get("/settings/user", follow_redirects=False)
    assert response.status_code == 401 # FastAPI raises HTTPException for login_required
