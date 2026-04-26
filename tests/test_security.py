"""
Security control tests — verifying authentication requirements, rate limiting,
file upload limits, magic-byte checks, and security headers.
"""
import io
import pytest
from matika.models import User, Role
from matika.auth.service import get_password_hash


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def login_as(client, email: str, password: str):
    client.post("/login", data={"email": email, "password": password})


def admin_user(db):
    pwd = get_password_hash("adminpw")
    u = User(username="sec_admin", email="sec_admin@example.com",
             hashed_password=pwd, is_authorized=True, force_password_change=False)
    u.roles.append(db.query(Role).filter(Role.name == "Admin").first())
    db.add(u); db.commit(); db.refresh(u)
    return u


# ---------------------------------------------------------------------------
# C1 — Admin POST routes require authentication
# ---------------------------------------------------------------------------

class TestAdminPostAuth:
    """Every admin POST must return 401/403 for unauthenticated callers."""

    def test_create_role_requires_auth(self, client):
        r = client.post("/admin/roles/create", data={"name": "Evil", "description": ""})
        assert r.status_code in (401, 403)

    def test_update_role_requires_auth(self, client):
        r = client.post("/admin/roles/update/1", data={"name": "Evil", "description": ""})
        assert r.status_code in (401, 403)

    def test_delete_role_requires_auth(self, client):
        r = client.post("/admin/roles/delete/1")
        assert r.status_code in (401, 403)

    def test_create_permission_requires_auth(self, client):
        r = client.post("/admin/permissions/create",
                        data={"page_path": "/admin/users", "subject": "role:1", "level": "Full"})
        assert r.status_code in (401, 403)

    def test_delete_permission_requires_auth(self, client):
        r = client.post("/admin/permissions/delete-subject",
                        data={"page_path": "/admin/users", "subject": "role:1"})
        assert r.status_code in (401, 403)

    def test_create_user_requires_auth(self, client):
        r = client.post("/admin/users/create",
                        data={"email": "evil@x.com", "username": "evil", "password": "pw"})
        assert r.status_code in (401, 403)

    def test_update_user_requires_auth(self, client):
        r = client.post("/admin/users/update/1", data={"email": "evil@x.com"})
        assert r.status_code in (401, 403)

    def test_delete_user_requires_auth(self, client):
        r = client.post("/admin/users/delete/1")
        assert r.status_code in (401, 403)

    def test_force_pw_change_requires_auth(self, client):
        r = client.post("/admin/users/force-password-change/1")
        assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# H2 — /show-log requires authentication
# ---------------------------------------------------------------------------

def test_show_log_requires_auth(client):
    r = client.get("/show-log")
    assert r.status_code in (401, 403)


def test_show_log_accessible_to_authenticated_user(client, test_user):
    login_as(client, "test@example.com", "testpassword")
    r = client.get("/show-log")
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# H3 — File upload size limits
# ---------------------------------------------------------------------------

def test_photo_upload_rejects_oversized_file(client, test_user):
    login_as(client, "test@example.com", "testpassword")
    big = b"\xff\xd8\xff" + b"X" * (5 * 1024 * 1024 + 1)   # valid JPEG magic + overflow
    r = client.post(
        "/settings/user/upload-photo",
        files={"file": ("photo.jpg", io.BytesIO(big), "image/jpeg")},
    )
    assert r.status_code == 400
    assert "too large" in r.text.lower()


def test_photo_upload_rejects_non_image_magic_bytes(client, test_user):
    login_as(client, "test@example.com", "testpassword")
    fake = b"PK\x03\x04" + b"not an image"   # ZIP magic (not an image)
    r = client.post(
        "/settings/user/upload-photo",
        files={"file": ("evil.jpg", io.BytesIO(fake), "image/jpeg")},
    )
    assert r.status_code == 400


def test_photo_upload_accepts_valid_jpeg(client, test_user):
    login_as(client, "test@example.com", "testpassword")
    # Minimal valid JPEG magic bytes
    tiny_jpeg = (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        b"\xff\xd9"
    )
    r = client.post(
        "/settings/user/upload-photo",
        files={"file": ("photo.jpg", io.BytesIO(tiny_jpeg), "image/jpeg")},
        follow_redirects=False,
    )
    # 303 redirect = success
    assert r.status_code == 303


def test_import_rejects_oversized_file(client, test_user):
    login_as(client, "test@example.com", "testpassword")
    big_json = b'{"metadata":{"type":"user_data"},' + b'"x":' + b"0," * (11 * 1024 * 1024)
    r = client.post(
        "/settings/import",
        files={"file": ("import.json", io.BytesIO(big_json), "application/json")},
        data={"include_roles": "false"},
        follow_redirects=False,  # capture the 303 redirect directly
    )
    # Oversized file → redirect to error URL
    assert r.status_code == 303
    assert "error=true" in r.headers.get("location", "")


# ---------------------------------------------------------------------------
# M1 — Security headers
# ---------------------------------------------------------------------------

def test_security_headers_present(client):
    r = client.get("/login")
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert "Referrer-Policy" in r.headers


# ---------------------------------------------------------------------------
# M2 — Rate limiter unit tests (integration test skipped: IS_TESTING bypasses limiter)
# ---------------------------------------------------------------------------

class TestRateLimiter:
    def _limiter(self, max_attempts=3, window=60, lockout=300):
        from matika.core.rate_limiter import RateLimiter
        return RateLimiter(window=window, max_attempts=max_attempts, lockout=lockout)

    def test_not_blocked_initially(self):
        rl = self._limiter()
        assert rl.is_blocked("1.2.3.4") is False

    def test_blocked_after_threshold(self):
        rl = self._limiter(max_attempts=3)
        for _ in range(3):
            rl.record_failure("1.2.3.4")
        assert rl.is_blocked("1.2.3.4") is True

    def test_success_clears_record(self):
        rl = self._limiter(max_attempts=3)
        for _ in range(2):
            rl.record_failure("1.2.3.4")
        rl.record_success("1.2.3.4")
        assert rl.is_blocked("1.2.3.4") is False

    def test_different_ips_independent(self):
        rl = self._limiter(max_attempts=3)
        for _ in range(3):
            rl.record_failure("1.1.1.1")
        assert rl.is_blocked("1.1.1.1") is True
        assert rl.is_blocked("2.2.2.2") is False
