import pytest
from matika.models import User
from matika.auth.service import verify_password, get_password_hash

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
    assert verify_password("password123", user.hashed_password)

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
    hashed_pwd = get_password_hash("forcepassword")
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
    assert verify_password("newpassword123", test_user.hashed_password)


def test_force_password_change_login_redirects_to_form(client, db):
    """Login with force_password_change=True must redirect directly to /change-password."""
    hashed_pwd = get_password_hash("testpw")
    user = User(
        username="fpuser",
        email="fp@example.com",
        hashed_password=hashed_pwd,
        is_authorized=True,
        force_password_change=True,
    )
    db.add(user)
    db.commit()

    # Login must redirect to /change-password, not /
    resp = client.post(
        "/login",
        data={"email": "fp@example.com", "password": "testpw"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/change-password"


def test_force_password_change_page_renders_form(client, db):
    """The /change-password page must render the password form, not an empty dialog."""
    hashed_pwd = get_password_hash("testpw")
    user = User(
        username="fpuser2",
        email="fp2@example.com",
        hashed_password=hashed_pwd,
        is_authorized=True,
        force_password_change=True,
    )
    db.add(user)
    db.commit()

    client.post("/login", data={"email": "fp2@example.com", "password": "testpw"})
    resp = client.get("/change-password")
    assert resp.status_code == 200

    # The actual form fields must be present — not just a title/heading
    assert 'action="/change-password"' in resp.text
    assert 'name="new_password"' in resp.text
    assert 'name="confirm_password"' in resp.text
    assert 'type="password"' in resp.text


def test_fresh_login_meta_tag_present_after_login(client, test_user):
    """After login the first page render must include the fresh-login meta tag."""
    # follow_redirects=False so the redirect (and its page render) does not
    # consume the flag before our explicit GET / below.
    client.post("/login", data={"email": "test@example.com", "password": "testpassword"}, follow_redirects=False)
    response = client.get("/")
    assert response.status_code == 200
    assert '<meta name="fresh-login" content="true">' in response.text


def test_fresh_login_meta_tag_cleared_after_first_render(client, test_user):
    """The fresh-login meta tag must not appear on subsequent page renders."""
    client.post("/login", data={"email": "test@example.com", "password": "testpassword"}, follow_redirects=False)
    client.get("/")  # consumes the flag
    response = client.get("/")
    assert response.status_code == 200
    assert 'name="fresh-login"' not in response.text


def test_fresh_login_meta_tag_present_after_logout_and_relogin(client, test_user):
    """After logout and re-login the fresh-login meta tag must appear again."""
    client.post("/login", data={"email": "test@example.com", "password": "testpassword"}, follow_redirects=False)
    client.get("/")  # consume first flag
    client.get("/logout")
    client.post("/login", data={"email": "test@example.com", "password": "testpassword"}, follow_redirects=False)
    response = client.get("/")
    assert response.status_code == 200
    assert '<meta name="fresh-login" content="true">' in response.text


def test_force_password_change_flag_cleared_after_change(client, db):
    """After a successful password change, force_password_change must be False in the DB."""
    hashed_pwd = get_password_hash("oldpw")
    user = User(
        username="fpuser3",
        email="fp3@example.com",
        hashed_password=hashed_pwd,
        is_authorized=True,
        force_password_change=True,
    )
    db.add(user)
    db.commit()

    client.post("/login", data={"email": "fp3@example.com", "password": "oldpw"})
    resp = client.post(
        "/change-password",
        data={"new_password": "newpw1234", "confirm_password": "newpw1234"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"

    db.refresh(user)
    assert user.force_password_change is False
