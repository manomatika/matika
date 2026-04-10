import pytest

def test_root_authenticated(client, test_user):
    client.post(
        "/login",
        data={"email": "test@example.com", "password": "testpassword"}
    )
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 200
    assert "index.html" in response.template.name

def test_register_page(client):
    response = client.get("/register")
    assert response.status_code == 200
    assert "register.html" in response.template.name

def test_forgot_password_page(client):
    response = client.get("/forgot-password")
    assert response.status_code == 200
    assert "forgot_password.html" in response.template.name

def test_forgot_password_post(client):
    response = client.post("/forgot-password", data={"email": "test@example.com"})
    assert response.status_code == 200
    assert "receive a reset link shortly" in response.text
    assert "Back" in response.text
def test_login_page(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert "login.html" in response.template.name
