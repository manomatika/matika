"""
CSRF validation contract tests.

Every test in this module monkeypatches _IS_TESTING=False so the real
validation logic runs. The existing _IS_TESTING bypass in conftest is
not affected — it only applies outside this module.
"""
import asyncio
import pytest
from unittest.mock import MagicMock
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

import matika.auth.dependencies as csrf_module
from matika.auth.dependencies import validate_csrf


# ---------------------------------------------------------------------------
# Module-wide fixture: disable the testing bypass for every test here
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def force_real_csrf_path(monkeypatch):
    """Patch _IS_TESTING=False so validate_csrf runs its real validation logic."""
    monkeypatch.setattr(csrf_module, "_IS_TESTING", False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_request(session_token=None):
    """Return a mock Request whose session contains the given CSRF token."""
    req = MagicMock()
    req.session = {}
    if session_token is not None:
        req.session["csrf_token"] = session_token
    return req


def _make_csrf_app():
    """Minimal FastAPI app with SessionMiddleware and one CSRF-protected endpoint."""
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-only-key")

    @app.get("/seed-session")
    async def seed(request: Request):
        request.session["csrf_token"] = "session-token"
        return {"ok": True}

    @app.post("/protected")
    async def protected(_csrf=Depends(validate_csrf)):
        return {"ok": True}

    return app


# ---------------------------------------------------------------------------
# 1. Missing csrf_token field → 403
# ---------------------------------------------------------------------------

def test_csrf_missing_field_raises_403():
    """validate_csrf raises 403 when csrf_token is absent from the POST body."""
    req = make_request(session_token="valid-token")
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(validate_csrf(request=req, csrf_token=None))
    assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# 2. Wrong token value → 403
# ---------------------------------------------------------------------------

def test_csrf_wrong_token_raises_403():
    """validate_csrf raises 403 when csrf_token does not match the session token."""
    req = make_request(session_token="valid-token")
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(validate_csrf(request=req, csrf_token="wrong-token"))
    assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# 3. Matching token → passes
# ---------------------------------------------------------------------------

def test_csrf_matching_token_passes():
    """validate_csrf does not raise when csrf_token matches the session token exactly."""
    req = make_request(session_token="valid-token")
    asyncio.run(validate_csrf(request=req, csrf_token="valid-token"))


# ---------------------------------------------------------------------------
# 4. Wrong field name ("csrftoken") → 403 at the HTTP level
# ---------------------------------------------------------------------------

def test_csrf_wrong_field_name_raises_403():
    """Submitting field 'csrftoken' (no underscore) is rejected with 403.

    FastAPI resolves validate_csrf's 'csrf_token' parameter by looking for a
    form field named 'csrf_token'. A form that sends 'csrftoken' results in
    csrf_token=None, which validate_csrf rejects. This test exercises the
    enforcement at the real HTTP boundary — it is the contract that caught the
    field-name mismatch bug introduced in commit da37335.
    """
    app = _make_csrf_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        client.get("/seed-session")
        resp = client.post("/protected", data={"csrftoken": "session-token"})
    assert resp.status_code == 403
