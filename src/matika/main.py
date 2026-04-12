import logging
import os
from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session

# Local Imports
from .core.paths import BASE_DIR
from .database import SessionLocal, init_db, get_db, PageType, get_system_setting
from .i18n import I18nService
from .core.logging_config import (
    setup_startup_logging, rotate_logs, cleanup_logs, finalize_logging, 
    ACTIVE_LOG, STARTUP_LOG, LOG_DIR
)
from .core.utils import format_num
from .auth.service import setup_oauth
from .routers import public, settings, admin
from .core.applug_service import AppLugService

# Environment & Testing Check
IS_TESTING = "pytest" in os.environ.get("PYTEST_CURRENT_TEST", "") or "PYTEST_VERSION" in os.environ
SECRET_KEY = os.environ.get("SECRET_KEY", "a-very-secret-key-for-development")

def create_app() -> FastAPI:
    # --- 1. LOGGING & INITIALIZATION ---
    setup_startup_logging(IS_TESTING)
    logger = logging.getLogger(__name__)
    rotate_logs(IS_TESTING)

    # --- 2. APP SETUP ---
    app = FastAPI(title="Matika")
    app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=86400)

    # Mount static
    app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "src", "matika", "static")), name="static")
    
    # Fresh Services for each app instance
    templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "src", "matika", "templates"))
    i18n = I18nService()
    service = AppLugService(templates=templates, app=app)
    
    templates.env.filters["format_num"] = format_num
    templates.env.globals["getattr"] = getattr
    
    app.state.templates = templates
    app.state.i18n = i18n
    app.state.app_lug_service = service

    # Standard Jinja2 context processor
    def context_processor(request: Request):
        service = request.app.state.app_lug_service
        i18n = request.app.state.i18n
        return {
            "plugin_menu_items": service.get_all_menu_items(),
            "t": i18n.get_text(request.headers.get("accept-language")),
            "user": getattr(request.state, "user", None)
        }

    templates.context_processors.append(context_processor)

    # Exception Handlers
    @app.exception_handler(403)
    async def unauthorized_exception_handler(request: Request, exc: Exception):
        t = request.app.state.i18n.get_text(request.headers.get("accept-language"))
        return request.app.state.templates.TemplateResponse(
            request, "unauthorized.html", {"t": t, "user": getattr(request.state, "user", None)}, status_code=403
        )

    # --- 3. ROUTERS ---
    app.include_router(public.router)
    app.include_router(settings.router)
    app.include_router(admin.router)

    # --- 4. CORE ENDPOINTS ---
    @app.get("/show-log", response_class=PlainTextResponse, tags=[PageType.INFO])
    async def show_log(request: Request, type: str = "app", db: Session = Depends(get_db)):
        log_map = {
            "app": (ACTIVE_LOG, "app_log_lines"), 
            "startup": (STARTUP_LOG, "startup_log_lines"), 
            "test": (os.path.join(LOG_DIR, "test_Matika.log"), "test_log_lines")
        }
        path, setting = log_map.get(type, (ACTIVE_LOG, "app_log_lines"))
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
    app_instance.state.app_lug_service.discover(db)

# Initialize database & cleanup logs for real runs
if not IS_TESTING:
    logger = logging.getLogger(__name__)
    logger.info("Initializing database...")
    db_session = SessionLocal()
    init_db(db_session)
    init_plugins(app, db_session)
    cleanup_logs(db_session, IS_TESTING)
    db_session.close()
    finalize_logging(IS_TESTING)

if __name__ == "__main__":
    import uvicorn
    import webbrowser
    from threading import Timer

    def open_browser():
        webbrowser.open("http://127.0.0.1:8000")

    if not IS_TESTING:
        Timer(1.5, open_browser).start()

    uvicorn.run(app, host="0.0.0.0", port=8000)
