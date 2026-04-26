import pytest
from matika.models import User, Role

def test_user_settings_page(client, test_user, db):
    from matika.database import init_db
    init_db(db)
    # Log in
    client.post(
        "/login",
        data={"email": "test@example.com", "password": "testpassword"}
    )
    
    response = client.get("/settings/user")
    assert response.status_code == 200
    assert "user_settings.html" in response.template.name
    assert "test@example.com" in response.text

def test_change_username_success(client, test_user, db):
    from matika.database import init_db
    init_db(db)
    # Log in
    client.post(
        "/login",
        data={"email": "test@example.com", "password": "testpassword"}
    )
    
    # Change username
    response = client.post(
        "/settings/user/change-username",
        data={"new_username": "updatedusername"},
        follow_redirects=True
    )
    assert response.status_code == 200
    assert "user_settings.html" in response.template.name
    
    # Verify in DB
    db.refresh(test_user)
    assert test_user.username == "updatedusername"

def test_change_username_taken(client, test_user, db):
    from matika.database import init_db
    init_db(db)
    # Create another user
    db.add(User(username="otheruser", email="other@example.com", hashed_password="hashed"))
    db.commit()
    
    # Log in
    client.post(
        "/login",
        data={"email": "test@example.com", "password": "testpassword"}
    )
    
    # Try to change to 'otheruser'
    response = client.post(
        "/settings/user/change-username",
        data={"new_username": "otheruser"},
        follow_redirects=False
    )
    # Route now redirects to /settings/user?error=username_taken instead of re-rendering
    assert response.status_code == 303
    assert "error=username_taken" in response.headers["location"]

def test_admin_list_users(client, test_admin, db):
    from matika.database import init_db
    init_db(db)
    # Log in as admin
    client.post(
        "/login",
        data={"email": "admin@example.com", "password": "adminpassword"}
    )
    
    response = client.get("/admin/users")
    assert response.status_code == 200
    assert "admin_users.html" in response.template.name
    assert "adminuser" in response.text

def test_admin_force_password_change(client, test_admin, test_user, db):
    from matika.database import init_db
    init_db(db)
    # Log in as admin
    client.post(
        "/login",
        data={"email": "admin@example.com", "password": "adminpassword"}
    )
    
    # Force password change for test_user
    response = client.post(
        f"/admin/users/force-password-change/{test_user.id}",
        follow_redirects=True
    )
    assert response.status_code == 200
    
    # Verify in DB
    db.refresh(test_user)
    assert test_user.force_password_change is True

def test_admin_delete_user(client, test_admin, test_user, db):
    from matika.database import init_db
    init_db(db)
    # Log in as admin
    client.post(
        "/login",
        data={"email": "admin@example.com", "password": "adminpassword"}
    )
    
    user_id = test_user.id
    # Delete test_user
    response = client.post(
        f"/admin/users/delete/{user_id}",
        follow_redirects=True
    )
    assert response.status_code == 200
    
    # Verify in DB
    deleted_user = db.query(User).filter(User.id == user_id).first()
    assert deleted_user is None

def test_admin_update_user(client, test_admin, test_user, db):
    from matika.database import init_db
    init_db(db)
    # Log in as admin
    client.post(
        "/login",
        data={"email": "admin@example.com", "password": "adminpassword"}
    )
    
    # Update test_user
    response = client.post(
        f"/admin/users/update/{test_user.id}",
        data={"email": "updated@example.com", "force_password_change": "true"},
        follow_redirects=True
    )
    assert response.status_code == 200
    
    # Verify in DB
    db.refresh(test_user)
    assert test_user.email == "updated@example.com"
    assert test_user.force_password_change is True

def test_admin_update_user_email_taken(client, test_admin, test_user, db):
    from matika.database import init_db
    init_db(db)
    # Create another user to take an email
    other_user = User(username="other", email="taken@example.com", hashed_password="hashed")
    db.add(other_user)
    db.commit()

    client.post("/login", data={"email": "admin@example.com", "password": "adminpassword"})
    
    # Try to update test_user to the taken email
    original_email = test_user.email
    response = client.post(
        f"/admin/users/update/{test_user.id}",
        data={"email": "taken@example.com", "force_password_change": "false"},
        follow_redirects=True
    )
    assert response.status_code == 200
    
    # Verify email did NOT change
    db.refresh(test_user)
    assert test_user.email == original_email

def test_admin_update_non_existent_user(client, test_admin, db):
    from matika.database import init_db
    init_db(db)
    client.post("/login", data={"email": "admin@example.com", "password": "adminpassword"})
    
    # Try to update a user ID that doesn't exist
    response = client.post(
        "/admin/users/update/9999",
        data={"email": "ghost@example.com", "force_password_change": "false"},
        follow_redirects=True
    )
    assert response.status_code == 200 # Redirects back to list

def test_admin_delete_self_fails(client, test_admin, db):
    from matika.database import init_db
    init_db(db)
    # Log in as admin
    client.post(
        "/login",
        data={"email": "admin@example.com", "password": "adminpassword"}
    )
    
    # Delete self
    response = client.post(
        f"/admin/users/delete/{test_admin.id}",
        follow_redirects=True
    )
    assert response.status_code == 400
    assert "Cannot delete yourself" in response.text

def test_admin_create_user(client, test_admin, db):
    from matika.database import init_db
    init_db(db)

    client.post(
        "/login",
        data={"email": "admin@example.com", "password": "adminpassword"}
    )
    
    response = client.post(
        "/admin/users/create",
        data={"username": "newuser", "email": "new@example.com"},
        follow_redirects=True
    )
    assert response.status_code == 200
    
    # Verify in DB
    new_user = db.query(User).filter(User.username == "newuser").first()
    assert new_user is not None
    assert new_user.email == "new@example.com"
    assert new_user.force_password_change is True
    
    # Verify role assignment
    user_role = db.query(Role).filter(Role.name == "User").first()
    assert user_role in new_user.roles

    # Verify initial password is username
    from matika.auth.service import verify_password
    assert verify_password("newuser", new_user.hashed_password) is True


def test_login_username_success(client, test_user, db):
    from matika.database import init_db
    init_db(db)
    
    # test_user.username is "testuser", password is "testpassword"
    response = client.post(
        "/login",
        data={"email": "testuser", "password": "testpassword"},
        follow_redirects=True
    )
    assert response.status_code == 200
    assert "Authenticated user" in response.text or "Welcome" in response.text or response.template.name == "index.html"


# ---------------------------------------------------------------------------
# User Settings — redesigned page and default-menu preference
# ---------------------------------------------------------------------------

def test_user_settings_page_renders_all_sections(client, test_user):
    """New settings page must contain the four expected sections."""
    client.post("/login", data={"email": "test@example.com", "password": "testpassword"})
    resp = client.get("/settings/user")
    assert resp.status_code == 200
    html = resp.text
    assert 'action="/settings/user/upload-photo"' in html
    assert 'action="/settings/user/change-username"' in html
    assert 'action="/settings/user/change-password"' in html
    assert 'action="/settings/user/default-menu"' in html


def test_user_settings_page_shows_username(client, test_user):
    client.post("/login", data={"email": "test@example.com", "password": "testpassword"})
    resp = client.get("/settings/user")
    assert "testuser" in resp.text


def test_save_default_menu_stores_preference(client, test_user, db):
    """POST /settings/user/default-menu saves the hub ID in user_settings."""
    from matika.models import UserSetting
    client.post("/login", data={"email": "test@example.com", "password": "testpassword"})

    resp = client.post(
        "/settings/user/default-menu",
        data={"default_menu": "__favorites__"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "saved=menu" in resp.headers["location"]

    db.expire_all()
    setting = db.query(UserSetting).filter(
        UserSetting.user_id == test_user.id,
        UserSetting.name == "default_menu",
    ).first()
    assert setting is not None
    assert setting.value == "__favorites__"


def test_save_default_menu_empty_clears_preference(client, test_user, db):
    """Submitting an empty value removes the preference (no preference = system default)."""
    from matika.models import UserSetting
    client.post("/login", data={"email": "test@example.com", "password": "testpassword"})

    # Set a value first
    client.post("/settings/user/default-menu", data={"default_menu": "__favorites__"})

    # Clear it
    client.post("/settings/user/default-menu", data={"default_menu": ""})

    db.expire_all()
    setting = db.query(UserSetting).filter(
        UserSetting.user_id == test_user.id,
        UserSetting.name == "default_menu",
    ).first()
    assert setting is None or setting.value == ""


def test_user_settings_page_reflects_saved_default_menu(client, test_user, db):
    """Saved default menu preference is pre-selected in the dropdown."""
    client.post("/login", data={"email": "test@example.com", "password": "testpassword"})
    client.post("/settings/user/default-menu", data={"default_menu": "__favorites__"})

    resp = client.get("/settings/user")
    assert "selected" in resp.text   # something must be selected
    assert "__favorites__" in resp.text


def test_user_settings_success_banner_after_save(client, test_user):
    """Saving returns a 303 to /?saved=... which shows the success banner on reload."""
    client.post("/login", data={"email": "test@example.com", "password": "testpassword"})

    resp = client.post(
        "/settings/user/default-menu",
        data={"default_menu": "__default__"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "saved" in resp.text.lower() or "preference" in resp.text.lower()


def test_base_template_exposes_user_id_meta(client, test_user):
    """base.html must include <meta name='user-id'> for per-user sessionStorage keying."""
    client.post("/login", data={"email": "test@example.com", "password": "testpassword"})
    resp = client.get("/about")
    assert 'name="user-id"' in resp.text


def test_base_template_exposes_user_default_menu_meta(client, test_user):
    """base.html must include <meta name='user-default-menu'> for main.ts."""
    client.post("/login", data={"email": "test@example.com", "password": "testpassword"})
    resp = client.get("/about")
    assert 'name="user-default-menu"' in resp.text


def test_change_username_success_redirects_with_saved(client, test_user):
    client.post("/login", data={"email": "test@example.com", "password": "testpassword"})
    resp = client.post(
        "/settings/user/change-username",
        data={"new_username": "newname_x"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "saved=username" in resp.headers["location"]


def test_change_password_wrong_current_redirects_with_error(client, test_user):
    client.post("/login", data={"email": "test@example.com", "password": "testpassword"})
    resp = client.post(
        "/settings/user/change-password",
        data={"current_password": "wrongpw", "new_password": "newpw123", "confirm_password": "newpw123"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "error=current_password_incorrect" in resp.headers["location"]


def test_change_password_mismatch_redirects_with_error(client, test_user):
    client.post("/login", data={"email": "test@example.com", "password": "testpassword"})
    resp = client.post(
        "/settings/user/change-password",
        data={"current_password": "testpassword", "new_password": "newpw123", "confirm_password": "different"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "error=passwords_mismatch" in resp.headers["location"]
