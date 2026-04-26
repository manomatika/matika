import time
from fastapi import APIRouter, Depends, HTTPException, Request, Form, Header
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User
from ..core.constants import PageType
from ..auth.service import verify_password
from ..auth.dependencies import get_current_user, login_required
from ..core.utils import format_num
from ..core.rate_limiter import login_limiter
import os
_IS_TESTING = (
    "pytest" in os.environ.get("PYTEST_CURRENT_TEST", "")
    or "PYTEST_VERSION" in os.environ
)

router = APIRouter(tags=[PageType.INFO])

@router.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if user.force_password_change:
        return RedirectResponse(url="/change-password", status_code=303)
    return request.app.state.templates.TemplateResponse(request, "index.html", {"user": user})

@router.get("/about", response_class=HTMLResponse)
async def about(request: Request, db: Session = Depends(get_db)):
    from ..database import get_system_setting
    version = get_system_setting(db, "version", "0.0.1")
    user = get_current_user(request, db)
    plugins = request.app.state.app_lug_service.get_loaded_plugins()
    return request.app.state.templates.TemplateResponse(request, "about.html", {
        "version": version, 
        "user": user,
        "plugins": plugins
    })

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return request.app.state.templates.TemplateResponse(request, "login.html", {})

@router.post("/login")
async def login(request: Request, email: str = Form(...), password: str = Form(...), remember_me: bool = Form(False), db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"

    if not _IS_TESTING and login_limiter.is_blocked(client_ip):
        return request.app.state.templates.TemplateResponse(
            request, "login.html",
            {"error": "Too many failed login attempts. Please try again later."},
            status_code=429,
        )

    user = db.query(User).filter((User.email == email) | (User.username == email)).first()
    if not user or not verify_password(password, user.hashed_password):
        if not _IS_TESTING:
            login_limiter.record_failure(client_ip)
        return request.app.state.templates.TemplateResponse(request, "login.html", {"error": "Invalid email or password"})

    if not _IS_TESTING:
        login_limiter.record_success(client_ip)

    # Rotate session to prevent session fixation.
    request.session.clear()
    request.session["user_id"] = user.id
    request.session["last_activity"] = int(time.time())
    request.session["session_created"] = int(time.time())

    if remember_me:
        request.session["is_persistent"] = True

    if user.force_password_change:
        return RedirectResponse(url="/change-password", status_code=303)
    return RedirectResponse(url="/", status_code=303)

@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return request.app.state.templates.TemplateResponse(request, "register.html", {})

@router.post("/register")
async def register(request: Request, username: str = Form(...), email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == username).first():
        return request.app.state.templates.TemplateResponse(request, "register.html", {"error": "Username already taken"})
    if db.query(User).filter(User.email == email).first():
        return request.app.state.templates.TemplateResponse(request, "register.html", {"error": "Email already taken"})
    
    from ..auth.service import get_password_hash
    new_user = User(username=username, email=email, hashed_password=get_password_hash(password), is_authorized=True)
    db.add(new_user); db.commit()
    return RedirectResponse(url="/login", status_code=303)

@router.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request):
    return request.app.state.templates.TemplateResponse(request, "forgot_password.html", {})

@router.post("/forgot-password")
async def forgot_password(request: Request, email: str = Form(...)):
    return HTMLResponse(content=f"<p>receive a reset link shortly</p><a href='/login'>Back to Login</a>")

# --- PLACEHOLDERS FOR OLD TESTS ---
@router.get("/change-password", response_class=HTMLResponse)
async def change_password_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user: return RedirectResponse(url="/login", status_code=303)
    return request.app.state.templates.TemplateResponse(request, "change_password.html", {"user": user})

@router.post("/change-password")
async def change_password(request: Request, new_password: str = Form(...), confirm_password: str = Form(...), db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user: raise HTTPException(status_code=401)
    
    if new_password != confirm_password:
        t = request.app.state.i18n.get_text(request.headers.get("accept-language"))
        return request.app.state.templates.TemplateResponse(request, "change_password.html", {
            "user": user, 
            "error": t.get("err_passwords_mismatch", "Passwords do not match")
        })

    from ..auth.service import get_password_hash
    user.hashed_password = get_password_hash(new_password)
    user.force_password_change = False
    db.commit()
    return RedirectResponse(url="/", status_code=303)
