import logging
import os
import secrets
from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.routing import Mount
from sqlalchemy.orm import Session

# Local Imports
from .core.paths import BASE_DIR, get_matika_version
from .database import SessionLocal, init_db, get_db, get_system_setting
from .core.constants import PageType
from .i18n import I18nService
from .core import logging_setup
from .core.utils import format_num
from .auth.service import setup_oauth
from .routers import public, settings, admin
from .core.applug_service import AppLugService

# Environment & Testing Check
IS_TESTING = "pytest" in os.environ.get("PYTEST_CURRENT_TEST", "") or "PYTEST_VERSION" in os.environ

# SECRET_KEY is required — hard-fail if not set.
SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "CRITICAL: SECRET_KEY environment variable is not set. "
        "The application cannot start. Set it in your environment or .env file."
    )


_NON_SCREEN_PATHS = {"/openapi.json", "/docs", "/redoc"}


def _collect_screen_routes(app_instance: FastAPI) -> list[str]:
    """Return sorted list of user-facing GET routes, excluding infra/doc/static paths."""
    paths = []
    for route in app_instance.routes:
        if isinstance(route, Mount):
            continue
        if not isinstance(route, APIRoute):
            continue
        path = route.path
        if path in _NON_SCREEN_PATHS:
            continue
        if path.endswith(".json"):
            continue
        if not (route.methods and "GET" in route.methods):
            continue
        paths.append(path)
    return sorted(paths)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds defensive HTTP security headers to every response."""
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


def create_app() -> FastAPI:
    # --- 1. LOGGING & INITIALIZATION ---
    # Phase 1 (startup) of the unified logging authority. A no-op under tests so
    # the suite never installs file handlers; the runtime handoff (phase 2) runs
    # at module load below for real (non-test) processes.
    logging_setup.begin_startup_phase(is_testing=IS_TESTING)
    logger = logging.getLogger(__name__)

    # --- 2. APP SETUP ---
    from .auth.dependencies import get_current_user, login_required

    def inject_user_to_state(request: Request, db: Session = Depends(get_db)):
        """Global dependency to ensure request.state.user is always populated."""
        if request.url.path.startswith("/static"):
            return
        request.state.user = get_current_user(request, db)

    app = FastAPI(title="ManoMatika", dependencies=[Depends(inject_user_to_state)])

    # Middlewares — outermost runs first on request, last on response.
    # max_age=None → session cookie (cleared on browser close).
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=None)

    # Mount static
    app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "src", "matika", "static")), name="static")

    # Fresh Services for each app instance
    templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "src", "matika", "templates"))
    i18n = I18nService()
    service = AppLugService(templates=templates, app=app)

    templates.env.filters["format_num"] = format_num
    templates.env.globals["getattr"] = getattr
    templates.env.globals["hasattr"] = hasattr
    templates.env.globals["isinstance"] = isinstance
    templates.env.globals["str"] = str

    app.state.templates = templates
    app.state.i18n = i18n
    app.state.app_lug_service = service

    # Standard Jinja2 context processor
    def context_processor(request: Request):
        svc = request.app.state.app_lug_service
        i18n_svc = request.app.state.i18n
        user = getattr(request.state, "user", None)
        t = i18n_svc.get_text(request.headers.get("accept-language"))
        user_roles = [r.name for r in user.roles] if user else []
        menus_data = svc.get_menus_for_context(user_roles, t)

        # CSRF token: generate once per session, reuse thereafter.
        csrf_token = request.session.get("csrf_token")
        if not csrf_token:
            csrf_token = secrets.token_urlsafe(32)
            request.session["csrf_token"] = csrf_token

        # User default menu preference (from user_settings table, eager-loaded).
        user_default_menu = ""
        if user:
            for s in user.settings:
                if s.name == "default_menu":
                    user_default_menu = s.value or ""
                    break

        # Consume the one-time fresh_login flag — fires on the first page render
        # after login or logout, then is gone so only one page sees it.
        fresh_login = bool(request.session.pop("fresh_login", False))

        return {
            "menus_data": menus_data,
            "t": t,
            "user": user,
            "csrf_token": csrf_token,
            "user_id": user.id if user else "",
            "user_default_menu": user_default_menu,
            "fresh_login": fresh_login,
        }

    templates.context_processors.append(context_processor)

    # Exception Handlers
    @app.exception_handler(403)
    async def unauthorized_exception_handler(request: Request, exc: Exception):
        t = request.app.state.i18n.get_text(request.headers.get("accept-language"))
        return request.app.state.templates.TemplateResponse(
            request, "unauthorized.html", {"t": t, "user": getattr(request.state, "user", None)}, status_code=403
        )

    # Health probe — unauthenticated, no DB calls, used by launcher readiness gate
    @app.get("/healthz", include_in_schema=False, tags=[PageType.INFO])
    async def healthz():
        return {"product": "ManoMatika", "version": get_matika_version(), "status": "ok"}

    # --- 3. ROUTERS ---
    app.include_router(public.router)
    app.include_router(settings.router)
    app.include_router(admin.router)

    # --- 4. CORE ENDPOINTS ---
    @app.get("/show-log", response_class=PlainTextResponse, tags=[PageType.INFO])
    async def show_log(
        request: Request,
        type: str = "aggregate",
        db: Session = Depends(get_db),
        _user=Depends(login_required),          # authenticated users only
    ):
        log_map = {
            "aggregate": (logging_setup.aggregate_log_path(), "aggregate_log_lines"),
            "startup": (logging_setup.startup_log_path(), "startup_log_lines"),
        }
        path, setting = log_map.get(
            type, (logging_setup.aggregate_log_path(), "aggregate_log_lines")
        )
        if os.path.exists(path):
            with open(path, "r") as f:
                lines = f.readlines()
                count = int(get_system_setting(db, setting, "100"))
                return "".join(lines[-count:])
        return f"Log file not found: {path}"

    return app


# Main instance
app = create_app()


def init_plugins(app_instance: FastAPI, db: Session):
    """Discovers and registers plugins into the FastAPI app instance."""
    logger = logging.getLogger(__name__)
    logger.info("Discovering plugins...")
    app_instance.state.app_lug_service.discover(db)
    logger.info(f"Loaded plugins: {len(app_instance.state.app_lug_service.loaded_plugins)}")
    screen_routes = _collect_screen_routes(app_instance)
    logger.info(f"[ROUTES: {', '.join(screen_routes)}]")


# Initialize database & cleanup logs for real runs
if not IS_TESTING:
    logger = logging.getLogger(__name__)
    logger.info("Initializing database...")
    db_session = SessionLocal()
    init_db(db_session)
    init_plugins(app, db_session)
    # Phase 2 (runtime) handoff: flush the buffered startup history into the
    # runtime-aggregate sink (same run_id), then prune dated files per-sink by
    # each sink's own retention count.
    logging_setup.prune_logs(
        {
            "aggregate": int(get_system_setting(db_session, "aggregate_log_retention", "10")),
            "startup": int(get_system_setting(db_session, "startup_log_retention", "10")),
        },
        is_testing=IS_TESTING,
    )
    db_session.close()
    logging_setup.begin_runtime_phase(is_testing=IS_TESTING)

if __name__ == "__main__":
    import uvicorn
    import webbrowser
    from threading import Timer

    def open_browser():
        webbrowser.open("http://127.0.0.1:8000")

    if not IS_TESTING:
        Timer(1.5, open_browser).start()

    uvicorn.run(app, host="0.0.0.0", port=8000)
