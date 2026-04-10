import pytest
from matika.database import User, Role, pwd_context

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
    assert response.status_code == 200
    assert "Username already taken" in response.text

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
