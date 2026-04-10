import pytest
from matika.database import User, pwd_context

def test_register_user(client, db):
    response = client.post(
        "/register",
        data={"username": "newuser", "email": "new@example.com", "password": "password123"},
        follow_redirects=True
    )
    assert response.status_code == 200
    assert "login.html" in response.template.name # Confirm redirection to login
    
    # Verify in DB
    user = db.query(User).filter(User.username == "newuser").first()
    assert user is not None
    assert user.email == "new@example.com"
    assert pwd_context.verify("password123", user.hashed_password)

def test_register_duplicate_username(client, test_user):
    response = client.post(
        "/register",
        data={"username": "testuser", "email": "other@example.com", "password": "password123"},
        follow_redirects=False
    )
    assert response.status_code == 200 # Returns form with error
    assert "Username already taken" in response.text

def test_login_success(client, test_user):
    response = client.post(
        "/login",
        data={"email": "test@example.com", "password": "testpassword"},
        follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"

def test_login_failure(client, test_user):
    response = client.post(
        "/login",
        data={"email": "test@example.com", "password": "wrongpassword"},
        follow_redirects=False
    )
    assert response.status_code == 200
    assert "Invalid email or password" in response.text
def test_logout(client, test_user):
    # Log in first
    client.post(
        "/login",
        data={"email": "test@example.com", "password": "testpassword"}
    )
    # Logout
    response = client.get("/logout", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/"

def test_force_password_change_redirect(client, db):
    # Create a user with force_password_change=True
    hashed_pwd = pwd_context.hash("forcepassword")
    user = User(
        username="forceuser",
        email="force@example.com",
        hashed_password=hashed_pwd,
        is_authorized=True,
        force_password_change=True
    )
    db.add(user)
    db.commit()
    
    # Log in
    client.post(
        "/login",
        data={"email": "force@example.com", "password": "forcepassword"},
        follow_redirects=True
    )
    
    # Accessing root should redirect to /change-password
    response = client.get("/", follow_redirects=True)
    assert "Change Password" in response.text or "heading_change_password" in response.text

def test_change_password_success(client, test_user):
    # Log in
    client.post(
        "/login",
        data={"email": "test@example.com", "password": "testpassword"}
    )
    
    # Change password
    response = client.post(
        "/change-password",
        data={"new_password": "newpassword123", "confirm_password": "newpassword123"},
        follow_redirects=True
    )
    assert response.status_code == 200
    assert "index.html" in response.template.name
    
    # Verify in DB
    from matika.database import SessionLocal
    # We need a new session or refresh to see changes made via client if they are in a different session context
    # But since we use the same 'db' fixture, it should be fine.
    # Wait, the client uses a different db session (the one yielded by get_db override).
    # But our fixture 'db' is what we yielded in the override.
    assert pwd_context.verify("newpassword123", test_user.hashed_password)
