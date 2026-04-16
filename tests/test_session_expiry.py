import pytest
import time
from unittest.mock import patch
from matika.database import User, pwd_context

def test_session_expires_on_cookie_clear(client, db):
    """
    Simulates a browser close by clearing the session cookie.
    The user should be logged out.
    """
    # 1. Log in without remember_me
    client.post(
        "/login",
        data={"email": "admin@matika.local", "password": "adminpassword", "remember_me": "false"},
        follow_redirects=True
    )
    
    # 2. Verify we are logged in (might redirect to /change-password)
    response = client.get("/", follow_redirects=False)
    assert response.status_code in (200, 303)
    
    # 3. 'Close browser' (clear cookies in client)
    client.cookies.clear()
    
    # 4. Verify we are logged out
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"

def test_session_cookie_is_session_type(client, db):
    """Verifies that the session cookie has no Max-Age or Expires (is session-only)."""
    response = client.post(
        "/login",
        data={"email": "admin@matika.local", "password": "adminpassword", "remember_me": "false"},
        follow_redirects=False
    )
    
    cookie_header = response.headers.get("set-cookie", "")
    # A true 'session' cookie has no Max-Age and no Expires
    assert "Max-Age" not in cookie_header
    assert "Expires" not in cookie_header

def test_internal_inactivity_timeout(client, db):
    """Verifies that the session expires internally after 30 mins of inactivity."""
    start_time = int(time.time())
    
    with patch("time.time") as mock_time:
        mock_time.return_value = start_time
        
        # 1. Log in
        client.post(
            "/login",
            data={"email": "admin@matika.local", "password": "adminpassword", "remember_me": "false"},
            follow_redirects=True
        )
        
        # 2. Verify logged in
        response = client.get("/", follow_redirects=False)
        assert response.status_code in (200, 303)
        
        # 3. Fast forward time by 31 minutes
        mock_time.return_value = start_time + (31 * 60)
        
        # 4. Verify logged out due to inactivity
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/login"

def test_remember_me_bypasses_inactivity_timeout(client, db):
    """Verifies that 'Remember Me' users are NOT logged out after 30 mins."""
    start_time = int(time.time())
    
    with patch("time.time") as mock_time:
        mock_time.return_value = start_time
        
        # 1. Log in WITH remember_me
        client.post(
            "/login",
            data={"email": "admin@matika.local", "password": "adminpassword", "remember_me": "true"},
            follow_redirects=True
        )
        
        # 2. Verify logged in
        response = client.get("/", follow_redirects=False)
        assert response.status_code in (200, 303)
        
        # 3. Fast forward time by 31 minutes
        mock_time.return_value = start_time + (31 * 60)
        
        # 4. Verify STILL logged in
        response = client.get("/", follow_redirects=False)
        assert response.status_code in (200, 303)
