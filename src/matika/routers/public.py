import os
import logging
from typing import Optional
from fastapi import APIRouter, Request, Form, Header, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from fastapi.templating import Jinja2Templates

from ..i18n import get_text
from ..core.paths import BASE_DIR
from ..database import get_db, User, PageType
from ..auth.service import verify_password, get_password_hash
from ..auth.dependencies import get_current_user

router = APIRouter(tags=[PageType.INFO])
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "src", "matika", "templates"))

@router.get("/", response_class=HTMLResponse)
async def read_root(request: Request, accept_language: str = Header(None), user: Optional[User] = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if user.force_password_change:
        return RedirectResponse(url="/change-password", status_code=303)
    t = get_text(accept_language)
    return templates.TemplateResponse(request, "index.html", {"t": t, "user": user})

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, accept_language: str = Header(None)):
    t = get_text(accept_language)
    return templates.TemplateResponse(request, "register.html", {"t": t})

@router.post("/register")
async def register_user(request: Request, username: str = Form(...), email: str = Form(...), password: str = Form(...), accept_language: str = Header(None), db: Session = Depends(get_db)):
    t = get_text(accept_language)
    if db.query(User).filter(User.username == username).first():
        return templates.TemplateResponse(request, "register.html", {"t": t, "error": t.get("err_username_taken")})
    hashed_password = get_password_hash(password)
    new_user = User(username=username, email=email, hashed_password=hashed_password, is_authorized=True)
    db.add(new_user); db.commit()
    return RedirectResponse(url="/login", status_code=303)

@router.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request, accept_language: str = Header(None)):
    t = get_text(accept_language)
    return templates.TemplateResponse(request, "forgot_password.html", {"t": t})

@router.post("/forgot-password")
async def forgot_password(email: str = Form(...), accept_language: str = Header(None)):
    t = get_text(accept_language)
    return HTMLResponse(content=f"<p>{t.get('msg_forgot_pw_sent')}</p><a href='/login'>{t.get('btn_back')}</a>")

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, accept_language: str = Header(None), error: str = None):
    t = get_text(accept_language)
    return templates.TemplateResponse(request, "login.html", {"t": t, "error": error})

@router.post("/login")
async def login(request: Request, email: str = Form(...), password: str = Form(...), accept_language: str = Header(None), db: Session = Depends(get_db)):
    user = db.query(User).filter((User.email == email) | (User.username == email)).first()
    t = get_text(accept_language)
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse(request, "login.html", {"t": t, "error": t.get("err_invalid_login")})
    request.session["user_id"] = user.id
    if user.force_password_change:
        return RedirectResponse(url="/change-password", status_code=303)
    return RedirectResponse(url="/", status_code=303)

@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)

@router.get("/change-password", response_class=HTMLResponse)
async def change_password_page(request: Request, accept_language: str = Header(None), user: User = Depends(get_current_user)):
    t = get_text(accept_language)
    if not user: return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request, "change_password.html", {"t": t, "user": user})

@router.post("/change-password")
async def change_password(request: Request, new_password: str = Form(...), confirm_password: str = Form(...), accept_language: str = Header(None), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = get_text(accept_language)
    if not user: return RedirectResponse(url="/login", status_code=303)
    if new_password != confirm_password:
        return templates.TemplateResponse(request, "change_password.html", {"t": t, "user": user, "error": t.get("err_passwords_mismatch")})
    user.hashed_password = get_password_hash(new_password)
    user.force_password_change = False
    db.commit()
    return RedirectResponse(url="/", status_code=303)

@router.get("/about", response_class=HTMLResponse)
async def about_page(request: Request, accept_language: str = Header(None), db: Session = Depends(get_db), user: Optional[User] = Depends(get_current_user)):
    from ..database import get_system_setting
    return templates.TemplateResponse(request, "about.html", {"t": get_text(accept_language), "version": get_system_setting(db, "version", "Unknown"), "user": user})
