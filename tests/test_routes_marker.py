"""
Tests for the [ROUTES: ...] startup log marker and _collect_screen_routes helper.

Verifies that _collect_screen_routes correctly includes user-facing GET routes
and excludes infra paths (/docs, /redoc, /openapi.json), POST-only routes,
static Mount objects, and paths ending in .json.
"""
import logging
import pytest
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from matika.main import _collect_screen_routes, init_plugins


# ---------------------------------------------------------------------------
# Pure-function tests on _collect_screen_routes
# ---------------------------------------------------------------------------

def test_screen_routes_includes_get_html_routes():
    app = FastAPI()

    @app.get("/login", response_class=HTMLResponse)
    async def login():
        ...

    @app.get("/home", response_class=HTMLResponse)
    async def home():
        ...

    routes = _collect_screen_routes(app)
    assert "/login" in routes
    assert "/home" in routes


def test_screen_routes_excludes_docs():
    """FastAPI auto-adds /docs, /redoc, /openapi.json — all must be absent."""
    app = FastAPI()
    routes = _collect_screen_routes(app)
    assert "/docs" not in routes
    assert "/redoc" not in routes
    assert "/openapi.json" not in routes


def test_screen_routes_excludes_post_only():
    app = FastAPI()

    @app.post("/form-submit")
    async def submit():
        ...

    routes = _collect_screen_routes(app)
    assert "/form-submit" not in routes


def test_screen_routes_excludes_static_mount(tmp_path):
    """Static file Mounts (e.g. /static) must be excluded."""
    app = FastAPI()
    app.mount("/static", StaticFiles(directory=str(tmp_path)), name="static")
    routes = _collect_screen_routes(app)
    assert "/static" not in routes
    # No mount path prefix should appear
    for r in routes:
        assert not r.startswith("/static")


def test_screen_routes_excludes_json_paths():
    """Routes whose path ends in .json must be excluded."""
    app = FastAPI()

    @app.get("/matika_screens.json")
    async def screens_json():
        return {}

    routes = _collect_screen_routes(app)
    assert "/matika_screens.json" not in routes


def test_screen_routes_result_is_sorted():
    """Returned list must be lexicographically sorted."""
    app = FastAPI()

    @app.get("/zebra", response_class=HTMLResponse)
    async def zebra():
        ...

    @app.get("/alpha", response_class=HTMLResponse)
    async def alpha():
        ...

    @app.get("/middle", response_class=HTMLResponse)
    async def middle():
        ...

    routes = _collect_screen_routes(app)
    assert routes == sorted(routes)


def test_screen_routes_get_and_post_route_is_included():
    """A route that accepts both GET and POST (e.g. a form page) should be included."""
    app = FastAPI()

    @app.api_route("/form-page", methods=["GET", "POST"], response_class=HTMLResponse)
    async def form_page():
        ...

    routes = _collect_screen_routes(app)
    assert "/form-page" in routes


# ---------------------------------------------------------------------------
# Integration test: [ROUTES: ...] log marker is emitted by init_plugins
# ---------------------------------------------------------------------------

def test_init_plugins_emits_routes_marker(caplog, db, test_app):
    """
    init_plugins (called via the test_app fixture) must emit exactly one
    [ROUTES: ...] log line.  We re-call it here on a fresh minimal app to
    assert on the log output without depending on production route lists.
    """
    mini_app = FastAPI()

    @mini_app.get("/ping", response_class=HTMLResponse)
    async def ping():
        ...

    # Borrow the AppLugService from the session-scoped test_app so we have a
    # real service (discover() is idempotent for a fresh session).
    mini_app.state.app_lug_service = test_app.state.app_lug_service

    with caplog.at_level(logging.INFO, logger="matika.main"):
        init_plugins(mini_app, db)

    marker_lines = [r.message for r in caplog.records if r.message.startswith("[ROUTES:")]
    assert len(marker_lines) >= 1, "Expected at least one [ROUTES: ...] log line"
    # /ping should appear; doc paths must not
    marker = marker_lines[-1]
    assert "/ping" in marker
    assert "/docs" not in marker
    assert "/redoc" not in marker
    assert "/openapi.json" not in marker
