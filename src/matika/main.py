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
from .i18n import get_text
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

# Initialize plugin service
app_lug_service = AppLugService()

def init_plugins(db: Session):
    """Discovers and registers plugins into the FastAPI app."""
    plugins = app_lug_service.discover(db)
    for plugin in plugins:
        app.include_router(plugin.get_router())

# --- 1. LOGGING & INITIALIZATION ---
setup_startup_logging(IS_TESTING)
logger = logging.getLogger(__name__)
rotate_logs(IS_TESTING)

# Initialize database & cleanup logs
if not IS_TESTING:
    logger.info("Initializing database...")
    db_session = SessionLocal()
    init_db(db_session)
    # Discover and Load Plugins
    init_plugins(db_session)
    cleanup_logs(db_session, IS_TESTING)
    db_session.close()
    finalize_logging(IS_TESTING)
else:
    # During testing, we might need a separate discovery trigger
    # but for now we let tests handle it or call it here with a test session if needed.
    pass

# --- 2. APP SETUP ---
app = FastAPI(title="Matika")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=86400)

# Mount static and templates
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "src", "matika", "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "src", "matika", "templates"))
templates.env.filters["format_num"] = format_num

# Context Processors for Templates
@app.middleware("http")
async def add_app_lug_context(request: Request, call_next):
    # This might be cleaner than context_processors if we want it global
    # and easy to access in all templates.
    response = await call_next(request)
    return response

# Standard Jinja2 context processor
def plugin_context(request: Request):
    return {"plugin_menu_items": app_lug_service.get_all_menu_items()}

templates.context_processors.append(plugin_context)

# Exception Handlers
@app.exception_handler(403)
async def unauthorized_exception_handler(request: Request, exc: Exception):
    t = get_text(request.headers.get("accept-language"))
    return templates.TemplateResponse(
        request, "unauthorized.html", {"t": t, "user": getattr(request.state, "user", None)}, status_code=403
    )

# --- 3. ROUTERS ---
app.include_router(public.router)
app.include_router(settings.router)
app.include_router(admin.router)

# --- 4. CORE ENDPOINTS (Remaining global ones) ---
@app.get("/show-log", response_class=PlainTextResponse, tags=[PageType.INFO])
async def show_log(type: str = "app", db: Session = Depends(get_db)):
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

if __name__ == "__main__":
    import uvicorn
    import webbrowser
    from threading import Timer

    def open_browser():
        webbrowser.open("http://127.0.0.1:8000")

    # Only auto-open if not in testing mode
    if not IS_TESTING:
        Timer(1.5, open_browser).start()

    uvicorn.run(app, host="0.0.0.0", port=8000)
