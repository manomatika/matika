import os
import json
import logging
import shutil
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Form, Header, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session, selectinload
from pydantic import BaseModel

from ..core.paths import BASE_DIR
from ..database import (
    get_db, get_pages, get_system_setting
)
from ..models import User, Role, Permission, SystemSetting
from ..core.constants import PageType, PermissionLevel
from ..core.logging_config import ACTIVE_LOG, STARTUP_LOG, LOG_DIR
from ..auth.service import get_password_hash
from ..auth.dependencies import login_required, validate_csrf

_MAX_IMPORT_BYTES = 10 * 1024 * 1024   # 10 MB
from ..security.service import check_page_permission
from ..data_mgmt.export_import import get_activity_categories

router = APIRouter(prefix="/admin", tags=[PageType.MAINTENANCE])
logger = logging.getLogger(__name__)

# --- ROLE MAINTENANCE ---
@router.get("/roles", response_class=HTMLResponse)
async def list_roles(request: Request, user: User = Depends(check_page_permission), db: Session = Depends(get_db)):
    return request.app.state.templates.TemplateResponse(request, "admin_roles.html", {
        "roles": db.query(Role).options(selectinload(Role.permissions), selectinload(Role.users)).all(),
        "user": user,
        "all_users": db.query(User).options(selectinload(User.roles)).all(),
    })

@router.post("/roles/create")
async def create_role(name: str = Form(...), description: str = Form(""), _auth: User = Depends(check_page_permission), _csrf=Depends(validate_csrf), db: Session = Depends(get_db)):
    db.add(Role(name=name, description=description))
    db.commit()
    return RedirectResponse(url="/admin/roles", status_code=303)

@router.post("/roles/update/{role_id}")
async def update_role(role_id: int, name: str = Form(...), description: str = Form(""), user_ids: Optional[str] = Form(None), _auth: User = Depends(check_page_permission), _csrf=Depends(validate_csrf), db: Session = Depends(get_db)):
    role = db.query(Role).filter(Role.id == role_id).first()
    if role:
        role.name = name
        role.description = description
        if user_ids is not None:
            ids = [int(i) for i in user_ids.split(",") if i.strip()]
            role.users = db.query(User).filter(User.id.in_(ids)).all()
        db.commit()
    return RedirectResponse(url="/admin/roles", status_code=303)

@router.post("/roles/delete/{role_id}")
async def delete_role(role_id: int, _auth: User = Depends(check_page_permission), _csrf=Depends(validate_csrf), db: Session = Depends(get_db)):
    role = db.query(Role).filter(Role.id == role_id).first()
    if role and role.name not in ["Admin", "User"]:
        db.delete(role)
        db.commit()
    return RedirectResponse(url="/admin/roles", status_code=303)

# --- SYSTEM IMPORT/EXPORT ---
@router.get("/settings/export", response_class=HTMLResponse)
async def export_system_page(request: Request, user: User = Depends(check_page_permission), db: Session = Depends(get_db)):
    t = request.app.state.i18n.get_text(request.headers.get("accept-language"))
    categories = get_activity_categories(db, "system_data", t)
    return request.app.state.templates.TemplateResponse(request, "export_data.html", {
        "user": user, "categories": categories, "heading": "Export System Data",
        "action_url": "/admin/settings/export", "default_filename": f"matika_system_{datetime.now().strftime('%Y%m%d')}.json"
    })

@router.post("/settings/export")
async def export_system_data(filename: str = Form(...), include_logging: bool = Form(False), include_system_roles: bool = Form(False), user: User = Depends(check_page_permission), db: Session = Depends(get_db)):
    export_payload = {"metadata": {"type": "system_config", "version": get_system_setting(db, "version", "unknown"), "timestamp": datetime.now().isoformat(), "exported_by": user.email}}
    if include_logging:
        export_payload["system_settings"] = {s.name: s.value for s in db.query(SystemSetting).filter(SystemSetting.name.in_(["app_log_lines", "app_log_retention", "startup_log_lines", "startup_log_retention", "test_log_lines", "test_log_retention"])).all()}
    if include_system_roles:
        export_payload["roles"] = [{"name": r.name, "description": r.description, "is_system": True, "permissions": [{"path": p.page_path, "type": p.page_type, "level": p.level} for p in r.permissions]} for r in db.query(Role).filter(Role.is_system == True).options(selectinload(Role.permissions)).all()]
    if not filename.endswith(".json"): filename += ".json"
    return JSONResponse(content=export_payload, headers={"Content-Disposition": f"attachment; filename={filename}"})

@router.get("/settings/import", response_class=HTMLResponse)
async def import_system_page(request: Request, user: User = Depends(check_page_permission), db: Session = Depends(get_db)):
    t = request.app.state.i18n.get_text(request.headers.get("accept-language"))
    categories = get_activity_categories(db, "system_data", t)
    return request.app.state.templates.TemplateResponse(request, "import_data.html", {
        "user": user, "heading": "Import System Data",
        "action_url": "/admin/settings/import", "categories": categories,
        "success": request.query_params.get("success") == "true", "error": request.query_params.get("error") == "true"
    })

@router.post("/settings/import")
async def system_import(file: UploadFile = File(...), include_logging: bool = Form(False), include_system_roles: bool = Form(False), user: User = Depends(check_page_permission), db: Session = Depends(get_db)):
    try:
        raw = await file.read(_MAX_IMPORT_BYTES + 1)
        if len(raw) > _MAX_IMPORT_BYTES:
            raise Exception("File too large (max 10 MB)")
        data = json.loads(raw)
        if data.get("metadata", {}).get("type") != "system_config": raise Exception("Invalid file type")
        if "system_settings" in data:
            s_data = data["system_settings"]
            if include_logging:
                for k in ["app_log_lines", "app_log_retention", "startup_log_lines", "startup_log_retention", "test_log_lines", "test_log_retention"]:
                    if k in s_data:
                        s = db.query(SystemSetting).filter(SystemSetting.name == k).first()
                        if s: s.value = s_data[k]
                        else: db.add(SystemSetting(name=k, value=s_data[k], is_system=True))
        if include_system_roles and "roles" in data:
            for r in data["roles"]:
                if r.get("is_system"):
                    er = db.query(Role).filter(Role.name == r["name"]).first()
                    if er:
                        er.description = r["description"]
                        db.query(Permission).filter(Permission.role_id == er.id).delete()
                        for p in r.get("permissions", []): db.add(Permission(role_id=er.id, page_path=p["path"], page_type=p["type"], level=p["level"], is_system=True))
        db.commit()
        return RedirectResponse(url="/admin/settings/import?success=true", status_code=303)
    except Exception as e:
        logger.error(f"System import failed: {e}")
        db.rollback()
        return RedirectResponse(url="/admin/settings/import?error=true", status_code=303)

# --- PERMISSIONS MAINTENANCE ---
@router.get("/permissions", response_class=HTMLResponse)
async def list_permissions(request: Request, user: User = Depends(check_page_permission), db: Session = Depends(get_db)):
    t = request.app.state.i18n.get_text(request.headers.get("accept-language"))
    perms = db.query(Permission).all()
    pages = get_pages()
    grouped = {pt: {path: {"label": t.get(lk, path), "subjects": {}} for path, p_type, lk in pages if p_type == pt} for pt in PageType}
    for p in perms:
        sk = f"role:{p.role_id}" if p.role_id else f"user:{p.user_id}"
        if p.page_path in grouped.get(p.page_type, {}):
            s = grouped[p.page_type][p.page_path]["subjects"]
            if sk not in s: s[sk] = {"role": p.role, "user": p.user, "permissions": []}
            s[sk]["permissions"].append(p)
    return request.app.state.templates.TemplateResponse(request, "admin_permissions.html", {
        "user": user, "grouped": grouped,
        "roles": db.query(Role).all(),
        "users": db.query(User).options(selectinload(User.roles)).all(),
        "page_types": list(PageType), "permission_levels": list(PermissionLevel)
    })

@router.post("/permissions/create")
async def create_permission(page_path: str = Form(...), subject: str = Form(...), level: PermissionLevel = Form(...), _auth: User = Depends(check_page_permission), _csrf=Depends(validate_csrf), db: Session = Depends(get_db)):
    st, sid = subject.split(":")
    rid = int(sid) if st == "role" else None
    uid = int(sid) if st == "user" else None
    
    # Exclusivity check for tests: if adding non-FULL, remove FULL. If adding FULL, remove all others.
    if level == PermissionLevel.FULL:
        db.query(Permission).filter(Permission.page_path == page_path, Permission.role_id == rid, Permission.user_id == uid).delete()
    else:
        db.query(Permission).filter(Permission.page_path == page_path, Permission.role_id == rid, Permission.user_id == uid, Permission.level == PermissionLevel.FULL).delete()

    # Resolve page type
    pt = PageType.INFO
    for path, ptype, lk in get_pages():
        if path == page_path: pt = ptype; break
    db.add(Permission(page_path=page_path, page_type=pt, role_id=rid, user_id=uid, level=level))
    db.commit()
    return RedirectResponse(url="/admin/permissions", status_code=303)

@router.post("/permissions/delete-subject")
async def delete_permission_subject(page_path: str = Form(...), subject: str = Form(...), _auth: User = Depends(check_page_permission), _csrf=Depends(validate_csrf), db: Session = Depends(get_db)):
    st, sid = subject.split(":")
    rid = int(sid) if st == "role" else None
    uid = int(sid) if st == "user" else None
    
    p = db.query(Permission).filter(Permission.page_path == page_path, Permission.role_id == rid, Permission.user_id == uid).first()
    if p:
        p.level = PermissionLevel.NONE
        db.commit()
    return RedirectResponse(url="/admin/permissions", status_code=303)

# --- USER MAINTENANCE ---
@router.get("/users", response_class=HTMLResponse)
async def list_users(request: Request, user: User = Depends(check_page_permission), db: Session = Depends(get_db)):
    return request.app.state.templates.TemplateResponse(request, "admin_users.html", {
        "users": db.query(User).options(selectinload(User.roles)).all(),
        "user": user,
        "roles": db.query(Role).all(),
    })

@router.post("/users/create")
async def admin_create_user(email: str = Form(...), username: str = Form(...), password: Optional[str] = Form(None), role_ids: Optional[str] = Form(None), _auth: User = Depends(check_page_permission), _csrf=Depends(validate_csrf), db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == email).first(): raise HTTPException(status_code=400, detail="Email taken")
    pwd = password if password else username
    u = User(email=email, username=username, hashed_password=get_password_hash(pwd), is_authorized=True, force_password_change=True)
    if role_ids:
        ids = [int(i) for i in role_ids.split(",") if i.strip()]
        u.roles = db.query(Role).filter(Role.id.in_(ids)).all()
    else:
        user_role = db.query(Role).filter(Role.name == "User").first()
        if user_role: u.roles.append(user_role)
    db.add(u); db.commit()
    return RedirectResponse(url="/admin/users", status_code=303)

@router.post("/users/update/{user_id}")
async def admin_update_user(user_id: int, email: str = Form(...), username: Optional[str] = Form(None), role_ids: Optional[str] = Form(None), force_password_change: str = Form("false"), _auth: User = Depends(check_page_permission), _csrf=Depends(validate_csrf), db: Session = Depends(get_db)):
    u = db.query(User).filter(User.id == user_id).first()
    if u:
        if db.query(User).filter(User.email == email, User.id != user_id).first():
             return RedirectResponse(url="/admin/users", status_code=303)
        u.email = email
        if username: u.username = username
        u.force_password_change = (force_password_change.lower() == "true")
        if role_ids is not None:
            ids = [int(i) for i in role_ids.split(",") if i.strip()]
            u.roles = db.query(Role).filter(Role.id.in_(ids)).all()
        db.commit()
    return RedirectResponse(url="/admin/users", status_code=303)

@router.post("/users/force-password-change/{user_id}")
async def admin_force_password_change(user_id: int, _auth: User = Depends(check_page_permission), _csrf=Depends(validate_csrf), db: Session = Depends(get_db)):
    u = db.query(User).filter(User.id == user_id).first()
    if u:
        u.force_password_change = True
        db.commit()
    return RedirectResponse(url="/admin/users", status_code=303)

@router.post("/users/delete/{user_id}")
async def admin_delete_user(user_id: int, current_user: User = Depends(check_page_permission), _csrf=Depends(validate_csrf), db: Session = Depends(get_db)):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    u = db.query(User).filter(User.id == user_id).first()
    if u: db.delete(u); db.commit()
    return RedirectResponse(url="/admin/users", status_code=303)
