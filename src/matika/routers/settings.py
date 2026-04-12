import os
import json
import logging
import shutil
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Request, Form, Header, Depends, File, UploadFile, Response, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session

from ..core.paths import BASE_DIR
from ..database import get_db, User, Role, Permission, SystemSetting, PageType, get_system_setting
from ..auth.service import verify_password, get_password_hash
from ..auth.dependencies import login_required
from ..security.service import check_page_permission
from ..data_mgmt.export_import import get_activity_categories

router = APIRouter(prefix="/settings", tags=[PageType.SETTINGS])
logger = logging.getLogger(__name__)

@router.get("/user", response_class=HTMLResponse)
async def user_settings_page(request: Request, user: User = Depends(check_page_permission)):
    return request.app.state.templates.TemplateResponse(request, "user_settings.html", {"user": user})

@router.get("/export", response_class=HTMLResponse)
async def export_data_page(request: Request, user: User = Depends(check_page_permission), db: Session = Depends(get_db)):
    t = request.app.state.i18n.get_text(request.headers.get("accept-language"))
    categories = get_activity_categories(db, "user_data", t)
    return request.app.state.templates.TemplateResponse(request, "export_data.html", {
        "user": user, "heading": t.get("heading_export_data"),
        "action_url": "/settings/export", "categories": categories,
        "default_filename": f"matika_user_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    })

@router.post("/export")
async def export_data(filename: str = Form(...), include_roles: bool = Form(False), user: User = Depends(check_page_permission), db: Session = Depends(get_db)):
    export_payload = {"metadata": {"type": "user_data", "version": get_system_setting(db, "version", "unknown"), "timestamp": datetime.now().isoformat(), "exported_by": user.email}}
    if include_roles:
        export_payload["roles"] = [{"name": r.name, "description": r.description, "is_system": False, "permissions": [{"path": p.page_path, "type": p.page_type, "level": p.level} for p in r.permissions]} for r in db.query(Role).filter(Role.is_system == False).all()]
    if not filename.endswith(".json"): filename += ".json"
    return JSONResponse(content=export_payload, headers={"Content-Disposition": f"attachment; filename={filename}"})

@router.get("/import", response_class=HTMLResponse)
async def import_data_page(request: Request, user: User = Depends(check_page_permission), db: Session = Depends(get_db)):
    t = request.app.state.i18n.get_text(request.headers.get("accept-language"))
    return request.app.state.templates.TemplateResponse(request, "import_data.html", {
        "user": user, "heading": t.get("heading_import_data"),
        "action_url": "/settings/import", "categories": get_activity_categories(db, "user_data", t),
        "success": request.query_params.get("success") == "true", "error": request.query_params.get("error") == "true"
    })

@router.post("/import")
async def import_data(file: UploadFile = File(...), include_roles: bool = Form(False), user: User = Depends(check_page_permission), db: Session = Depends(get_db)):
    try:
        data = json.loads(await file.read())
        if data.get("metadata", {}).get("type") != "user_data": raise Exception("Invalid file type")
        if include_roles and "roles" in data:
            for r in data["roles"]:
                existing = db.query(Role).filter(Role.name == r["name"]).first()
                if not existing:
                    nr = Role(name=r["name"], description=r["description"], is_system=False)
                    db.add(nr); db.flush()
                    for p in r.get("permissions", []): db.add(Permission(role_id=nr.id, page_path=p["path"], page_type=p["type"], level=p["level"], is_system=False))
        db.commit()
        return RedirectResponse(url="/settings/import?success=true", status_code=303)
    except Exception as e:
        logger.error(f"Import failed: {e}")
        db.rollback()
        return RedirectResponse(url="/settings/import?error=true", status_code=303)

@router.get("/system", response_class=HTMLResponse)
async def system_settings_page(request: Request, user: User = Depends(check_page_permission), db: Session = Depends(get_db)):
    return request.app.state.templates.TemplateResponse(request, "system_settings.html", {
        "user": user,
        "app_log_lines": get_system_setting(db, "app_log_lines", "100"),
        "app_log_retention": get_system_setting(db, "app_log_retention", "10"),
        "startup_log_lines": get_system_setting(db, "startup_log_lines", "100"),
        "startup_log_retention": get_system_setting(db, "startup_log_retention", "10"),
        "test_log_lines": get_system_setting(db, "test_log_lines", "100"),
        "test_log_retention": get_system_setting(db, "test_log_retention", "10"),
    })

@router.post("/system")
async def save_system_settings(
    app_log_lines: str = Form("100"), app_log_retention: str = Form("10"),
    startup_log_lines: str = Form("100"), startup_log_retention: str = Form("10"),
    test_log_lines: str = Form("100"), test_log_retention: str = Form("10"),
    user: User = Depends(login_required), db: Session = Depends(get_db)
):
    settings = {
        "app_log_lines": app_log_lines, "app_log_retention": app_log_retention,
        "startup_log_lines": startup_log_lines, "startup_log_retention": startup_log_retention,
        "test_log_lines": test_log_lines, "test_log_retention": test_log_retention,
    }
    for n, v in settings.items():
        s = db.query(SystemSetting).filter(SystemSetting.name == n).first()
        if s: s.value = v
        else: db.add(SystemSetting(name=n, value=v, is_system=True))
    db.commit()
    return RedirectResponse(url="/settings/system", status_code=303)

@router.get("/user/change-username", response_class=HTMLResponse)
async def user_change_username_page(request: Request, user: User = Depends(check_page_permission)):
    return request.app.state.templates.TemplateResponse(request, "user_change_username.html", {"user": user})

@router.post("/user/change-username")
async def user_change_username(request: Request, new_username: str = Form(...), user: User = Depends(login_required), db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == new_username).first():
        t = request.app.state.i18n.get_text(request.headers.get("accept-language"))
        return request.app.state.templates.TemplateResponse(request, "user_change_username.html", {"user": user, "error": t.get("err_username_taken")})
    user.username = new_username; db.commit()
    return RedirectResponse(url="/settings/user", status_code=303)

@router.get("/user/change-password", response_class=HTMLResponse)
async def user_change_password_page(request: Request, user: User = Depends(check_page_permission)):
    return request.app.state.templates.TemplateResponse(request, "user_change_password.html", {"user": user})

@router.post("/user/change-password")
async def user_change_password(request: Request, current_password: str = Form(...), new_password: str = Form(...), confirm_password: str = Form(...), user: User = Depends(login_required), db: Session = Depends(get_db)):
    t = request.app.state.i18n.get_text(request.headers.get("accept-language"))
    if not verify_password(current_password, user.hashed_password):
        return request.app.state.templates.TemplateResponse(request, "user_change_password.html", {"user": user, "error": t.get("err_current_password_incorrect")})
    if new_password != confirm_password:
        return request.app.state.templates.TemplateResponse(request, "user_change_password.html", {"user": user, "error": t.get("err_passwords_mismatch")})
    user.hashed_password = get_password_hash(new_password); db.commit()
    return RedirectResponse(url="/settings/user", status_code=303)

@router.get("/user/photo/{user_id}")
async def get_user_photo(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.photo_blob:
        raise HTTPException(status_code=404)
    return Response(content=user.photo_blob, media_type=user.photo_mime_type or "image/jpeg")

@router.post("/user/upload-photo")
async def upload_photo(file: UploadFile = File(...), user: User = Depends(login_required), db: Session = Depends(get_db)):
    if not file.content_type.startswith("image/"): raise HTTPException(status_code=400, detail="Not an image")
    content = await file.read()
    user.photo_blob = content
    user.photo_mime_type = file.content_type
    user.photo_url = f"/settings/user/photo/{user.id}"
    db.commit()
    return RedirectResponse(url="/settings/user", status_code=303)
