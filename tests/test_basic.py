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


# ---------------------------------------------------------------------------
# Home page (redesigned dashboard)
# ---------------------------------------------------------------------------

def test_home_page_renders_welcome(client, test_user):
    client.post("/login", data={"email": "test@example.com", "password": "testpassword"})
    resp = client.get("/")
    assert resp.status_code == 200
    assert "testuser" in resp.text

def test_home_page_shows_stats_for_admin(client, test_admin):
    client.post("/login", data={"email": "admin@example.com", "password": "adminpassword"})
    resp = client.get("/")
    assert resp.status_code == 200
    # Stats section should be present for admin
    assert "heading_system_overview" in resp.text or "System Overview" in resp.text

def test_home_page_no_stats_for_regular_user(client, test_user):
    client.post("/login", data={"email": "test@example.com", "password": "testpassword"})
    resp = client.get("/")
    assert resp.status_code == 200
    # Stats section must NOT appear for non-admin
    assert "hp-stats-row" not in resp.text


# ---------------------------------------------------------------------------
# About page (redesigned)
# ---------------------------------------------------------------------------

def test_about_page_shows_version(client):
    resp = client.get("/about")
    assert resp.status_code == 200
    # Version badge must be present
    assert "abt-version-badge" in resp.text

def test_about_page_shows_framework_components(client):
    resp = client.get("/about")
    assert "FastAPI" in resp.text
    assert "SQLAlchemy" in resp.text
    assert "Python" in resp.text

def test_about_page_shows_installed_plugins(client):
    resp = client.get("/about")
    assert resp.status_code == 200
    # mock_plugin is loaded in test environment
    assert "mock_plugin" in resp.text

def test_about_page_shows_copyright(client):
    resp = client.get("/about")
    assert "Tallman" in resp.text or "Copyright" in resp.text


# ---------------------------------------------------------------------------
# Product identity — FastAPI title + template surfaces
# ---------------------------------------------------------------------------

def test_fastapi_app_title_is_product_name():
    from matika.main import create_app
    assert create_app().title == "ManoMatika"


def test_about_page_app_name_is_product_name(client):
    resp = client.get("/about")
    assert resp.status_code == 200
    assert "ManoMatika" in resp.text


def test_about_page_heading_uses_product_name(client):
    resp = client.get("/about")
    # heading_about locale key renders "About ManoMatika"
    assert "About ManoMatika" in resp.text
