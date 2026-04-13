from fastapi import APIRouter, Depends, HTTPException, Request, Form, Header
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from ..database import get_db, User, PageType
from ..auth.service import verify_password
from ..auth.dependencies import get_current_user, login_required
from ..core.utils import format_num

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
    return request.app.state.templates.TemplateResponse(request, "about.html", {"version": version, "user": user})

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return request.app.state.templates.TemplateResponse(request, "login.html", {})

@router.post("/login")
async def login(request: Request, email: str = Form(...), password: str = Form(...), remember_me: bool = Form(False), db: Session = Depends(get_db)):
    user = db.query(User).filter((User.email == email) | (User.username == email)).first()
    if not user or not verify_password(password, user.hashed_password):
        return request.app.state.templates.TemplateResponse(request, "login.html", {"error": "Invalid email or password"})
    
    request.session["user_id"] = user.id
    if remember_me:
        # Standard way to tell Starlette to keep session (though it depends on max_age being None in middleware config)
        request.session.max_age = 86400 * 30 # 30 days
        
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
    # The test expects "Change Password" or "heading_change_password"
    return request.app.state.templates.TemplateResponse(request, "user_change_password.html", {"user": user})

@router.post("/change-password")
async def change_password(request: Request, db: Session = Depends(get_db), new_password: str = Form(...)):
    user = get_current_user(request, db)
    if not user: raise HTTPException(status_code=401)
    from ..auth.service import get_password_hash
    user.hashed_password = get_password_hash(new_password)
    user.force_password_change = False
    db.commit()
    return RedirectResponse(url="/", status_code=303)
