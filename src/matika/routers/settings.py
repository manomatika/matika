import os
import json
import logging
import shutil
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Request, Form, Header, Depends, File, UploadFile, Response, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session, selectinload

from ..core.paths import BASE_DIR
from ..database import get_db, get_system_setting, get_user_setting, set_user_setting
from ..models import User, Role, Permission, SystemSetting
from ..core.constants import PageType
from ..auth.service import verify_password, get_password_hash
from ..auth.dependencies import login_required, validate_csrf
from ..security.service import check_page_permission

_MAX_IMPORT_BYTES = 10 * 1024 * 1024   # 10 MB
_MAX_PHOTO_BYTES  =  5 * 1024 * 1024   #  5 MB

# Common image magic-byte signatures
_IMAGE_MAGIC: list[tuple[bytes, int]] = [
    (b"\xff\xd8\xff", 0),          # JPEG
    (b"\x89PNG\r\n\x1a\n", 0),     # PNG
    (b"GIF87a", 0),                # GIF87
    (b"GIF89a", 0),                # GIF89
    (b"RIFF", 0),                  # WebP (checked further below)
    (b"\x00\x00\x01\x00", 0),      # ICO
]

def _is_image_by_magic(data: bytes) -> bool:
    for sig, offset in _IMAGE_MAGIC:
        if data[offset:offset + len(sig)] == sig:
            # Additional WebP check
            if sig == b"RIFF" and data[8:12] != b"WEBP":
                continue
            return True
    return False
from ..data_mgmt.export_import import get_activity_categories

router = APIRouter(prefix="/settings", tags=[PageType.SETTINGS])
logger = logging.getLogger(__name__)

@router.get("/user", response_class=HTMLResponse)
async def user_settings_page(request: Request, user: User = Depends(check_page_permission), db: Session = Depends(get_db)):
    user_default_menu = next(
        (s.value for s in user.settings if s.name == "default_menu"), ""
    )
    return request.app.state.templates.TemplateResponse(request, "user_settings.html", {
        "user": user,
        "user_default_menu": user_default_menu,
        "saved": request.query_params.get("saved"),
        "error_key": request.query_params.get("error"),
    })

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
        export_payload["roles"] = [{"name": r.name, "description": r.description, "is_system": False, "permissions": [{"path": p.page_path, "type": p.page_type, "level": p.level} for p in r.permissions]} for r in db.query(Role).filter(Role.is_system == False).options(selectinload(Role.permissions)).all()]
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
        raw = await file.read(_MAX_IMPORT_BYTES + 1)
        if len(raw) > _MAX_IMPORT_BYTES:
            raise Exception("File too large (max 10 MB)")
        data = json.loads(raw)
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
    timeout_seconds = int(get_system_setting(db, "session_idle_timeout", "1800"))
    return request.app.state.templates.TemplateResponse(request, "system_settings.html", {
        "user": user,
        "aggregate_log_lines": get_system_setting(db, "aggregate_log_lines", "100"),
        "aggregate_log_retention": get_system_setting(db, "aggregate_log_retention", "10"),
        "startup_log_lines": get_system_setting(db, "startup_log_lines", "100"),
        "startup_log_retention": get_system_setting(db, "startup_log_retention", "10"),
        "session_idle_timeout": timeout_seconds // 60,
    })

@router.post("/system")
async def save_system_settings(
    aggregate_log_lines: str = Form("100"), aggregate_log_retention: str = Form("10"),
    startup_log_lines: str = Form("100"), startup_log_retention: str = Form("10"),
    session_idle_timeout: str = Form("30"),
    user: User = Depends(login_required), db: Session = Depends(get_db)
):
    timeout_seconds = str(int(session_idle_timeout) * 60)
    settings = {
        "aggregate_log_lines": aggregate_log_lines, "aggregate_log_retention": aggregate_log_retention,
        "startup_log_lines": startup_log_lines, "startup_log_retention": startup_log_retention,
        "session_idle_timeout": timeout_seconds,
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
        return RedirectResponse(url="/settings/user?error=username_taken", status_code=303)
    user.username = new_username; db.commit()
    return RedirectResponse(url="/settings/user?saved=username", status_code=303)

@router.get("/user/change-password", response_class=HTMLResponse)
async def user_change_password_page(request: Request, user: User = Depends(check_page_permission)):
    return request.app.state.templates.TemplateResponse(request, "user_change_password.html", {"user": user})

@router.post("/user/change-password")
async def user_change_password(request: Request, current_password: str = Form(...), new_password: str = Form(...), confirm_password: str = Form(...), user: User = Depends(login_required), db: Session = Depends(get_db)):
    if not verify_password(current_password, user.hashed_password):
        return RedirectResponse(url="/settings/user?error=current_password_incorrect", status_code=303)
    if new_password != confirm_password:
        return RedirectResponse(url="/settings/user?error=passwords_mismatch", status_code=303)
    user.hashed_password = get_password_hash(new_password); db.commit()
    return RedirectResponse(url="/settings/user?saved=password", status_code=303)

@router.post("/user/default-menu")
async def save_default_menu(
    default_menu: str = Form(""),
    user: User = Depends(login_required),
    _csrf=Depends(validate_csrf),
    db: Session = Depends(get_db),
):
    set_user_setting(db, user.id, "default_menu", default_menu.strip())
    return RedirectResponse(url="/settings/user?saved=menu", status_code=303)


@router.get("/user/photo/{user_id}")
async def get_user_photo(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.photo_blob:
        raise HTTPException(status_code=404)
    return Response(content=user.photo_blob, media_type=user.photo_mime_type or "image/jpeg")

@router.post("/user/upload-photo")
async def upload_photo(file: UploadFile = File(...), user: User = Depends(login_required), db: Session = Depends(get_db)):
    content = await file.read(_MAX_PHOTO_BYTES + 1)
    if len(content) > _MAX_PHOTO_BYTES:
        raise HTTPException(status_code=400, detail="Image too large (max 5 MB)")
    if not _is_image_by_magic(content):
        raise HTTPException(status_code=400, detail="File is not a recognised image format")
    user.photo_blob = content
    user.photo_mime_type = file.content_type
    user.photo_url = f"/settings/user/photo/{user.id}"
    db.commit()
    return RedirectResponse(url="/settings/user?saved=photo", status_code=303)
