import os
import json
import logging
import shutil
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Request, Form, Header, Depends, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from ..i18n import get_text
from ..core.paths import BASE_DIR
from ..database import (
    get_db, User, Security, Role, Permission, SystemSetting, PageType, 
    PermissionLevel, get_pages, SecurityType, AssetClass, get_system_setting
)
from ..core.utils import load_metadata
from ..core.logging_config import ACTIVE_LOG, STARTUP_LOG, LOG_DIR
from ..auth.service import get_password_hash
from ..auth.dependencies import login_required
from ..security.service import check_page_permission
from ..data_mgmt.export_import import get_activity_categories

router = APIRouter(prefix="/admin", tags=[PageType.MAINTENANCE])
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "src", "matika", "templates"))
logger = logging.getLogger(__name__)

# --- USER MAINTENANCE ---
@router.get("/users", response_class=HTMLResponse)
async def list_users(request: Request, accept_language: str = Header(None), user: User = Depends(check_page_permission), db: Session = Depends(get_db)):
    t = get_text(accept_language)
    return templates.TemplateResponse(request, "admin_users.html", {"t": t, "users": db.query(User).all(), "user": user})

@router.post("/users/create")
async def create_user(username: str = Form(...), email: str = Form(...), db: Session = Depends(get_db)):
    nu = User(username=username, email=email, hashed_password=get_password_hash(username), is_authorized=True, force_password_change=True)
    ur = db.query(Role).filter(Role.name == "User").first()
    if ur: nu.roles.append(ur)
    db.add(nu); db.commit(); return RedirectResponse(url="/admin/users", status_code=303)

@router.post("/users/update/{user_id}")
async def update_user(user_id: int, email: str = Form(...), force_password_change: bool = Form(False), db: Session = Depends(get_db)):
    target_user = db.query(User).filter(User.id == user_id).first()
    if target_user:
        existing = db.query(User).filter(User.email == email, User.id != user_id).first()
        if not existing:
            target_user.email = email; target_user.force_password_change = force_password_change; db.commit()
    return RedirectResponse(url="/admin/users", status_code=303)

@router.post("/users/delete/{user_id}")
async def delete_user(user_id: int, user: User = Depends(login_required), db: Session = Depends(get_db)):
    if user.id == user_id: raise HTTPException(status_code=400, detail="Cannot delete yourself.")
    tu = db.query(User).filter(User.id == user_id).first()
    if tu: tu.roles = []; db.delete(tu); db.commit()
    return RedirectResponse(url="/admin/users", status_code=303)

@router.post("/users/force-password-change/{user_id}")
async def force_password_change(user_id: int, db: Session = Depends(get_db)):
    target_user = db.query(User).filter(User.id == user_id).first()
    if target_user:
        target_user.force_password_change = True
        db.commit()
    return RedirectResponse(url="/admin/users", status_code=303)

# --- ROLE MAINTENANCE ---
@router.get("/roles", response_class=HTMLResponse)
async def list_roles(request: Request, accept_language: str = Header(None), user: User = Depends(check_page_permission), db: Session = Depends(get_db)):
    t = get_text(accept_language)
    return templates.TemplateResponse(request, "admin_roles.html", {"t": t, "roles": db.query(Role).all(), "user": user, "all_users": db.query(User).all()})

@router.post("/roles/create")
async def create_role(name: str = Form(...), description: str = Form(""), db: Session = Depends(get_db)):
    db.add(Role(name=name, description=description)); db.commit(); return RedirectResponse(url="/admin/roles", status_code=303)

@router.post("/roles/update/{role_id}")
async def update_role(role_id: int, name: str = Form(...), description: str = Form(""), user_ids: Optional[str] = Form(None), db: Session = Depends(get_db)):
    role = db.query(Role).filter(Role.id == role_id).first()
    if role:
        role.name = name; role.description = description
        if user_ids is not None:
            role.users = []
            if user_ids.strip(): role.users.extend(db.query(User).filter(User.id.in_([int(i) for i in user_ids.split(",") if i.strip()])).all())
        db.commit()
    return RedirectResponse(url="/admin/roles", status_code=303)

@router.post("/roles/delete/{role_id}")
async def delete_role(role_id: int, db: Session = Depends(get_db)):
    role = db.query(Role).filter(Role.id == role_id).first()
    if role and role.name not in ["Admin", "User"]: db.delete(role); db.commit()
    return RedirectResponse(url="/admin/roles", status_code=303)

# --- SECURITY MAINTENANCE ---
@router.get("/securities", response_class=HTMLResponse)
async def list_securities(request: Request, accept_language: str = Header(None), user: User = Depends(check_page_permission), db: Session = Depends(get_db)):
    t = get_text(accept_language)
    return templates.TemplateResponse(request, "admin_securities.html", {
        "t": t, "title": t.get("item_securities"), "user": user, "securities": db.query(Security).all(),
        "security_types": list(SecurityType), "asset_classes": list(AssetClass), "metadata": load_metadata("securities", Security)
    })

@router.post("/securities/create")
async def create_security(symbol: str = Form(...), name: str = Form(...), security_type: SecurityType = Form(...), asset_class: Optional[AssetClass] = Form(None), previous_close: Optional[str] = Form(None), open_price: Optional[str] = Form(None), current_price: Optional[str] = Form(None), nav: Optional[str] = Form(None), range_52_week: Optional[str] = Form(None), avg_volume: Optional[str] = Form(None), yield_30_day: Optional[str] = Form(None), yield_7_day: Optional[str] = Form(None), db: Session = Depends(get_db)):
    if db.query(Security).filter(Security.symbol == symbol.upper()).first(): raise HTTPException(status_code=400, detail="already exists")
    db.add(Security(symbol=symbol.upper(), name=name, security_type=security_type, asset_class=asset_class, previous_close=previous_close, open_price=open_price, current_price=current_price, nav=nav, range_52_week=range_52_week, avg_volume=avg_volume, yield_30_day=yield_30_day, yield_7_day=yield_7_day))
    db.commit(); return RedirectResponse(url="/admin/securities", status_code=303)

@router.post("/securities/update/{sec_id}")
async def update_security(sec_id: int, symbol: str = Form(...), name: str = Form(...), security_type: SecurityType = Form(...), asset_class: Optional[AssetClass] = Form(None), previous_close: Optional[str] = Form(None), open_price: Optional[str] = Form(None), current_price: Optional[str] = Form(None), nav: Optional[str] = Form(None), range_52_week: Optional[str] = Form(None), avg_volume: Optional[str] = Form(None), yield_30_day: Optional[str] = Form(None), yield_7_day: Optional[str] = Form(None), db: Session = Depends(get_db)):
    sec = db.query(Security).filter(Security.id == sec_id).first()
    if sec:
        sec.symbol = symbol; sec.name = name; sec.security_type = security_type; sec.asset_class = asset_class
        sec.previous_close = previous_close; sec.open_price = open_price; sec.current_price = current_price
        sec.nav = nav; sec.range_52_week = range_52_week; sec.avg_volume = avg_volume
        sec.yield_30_day = yield_30_day; sec.yield_7_day = yield_7_day; db.commit()
    return RedirectResponse(url="/admin/securities", status_code=303)

@router.post("/securities/delete/{sec_id}")
async def delete_security(sec_id: int, db: Session = Depends(get_db)):
    sec = db.query(Security).filter(Security.id == sec_id).first()
    if sec: db.delete(sec); db.commit()
    return RedirectResponse(url="/admin/securities", status_code=303)

# --- SECURITY ENDPOINTS & BULK ---
@router.get("/securities/search")
async def search_securities(q: str, db: Session = Depends(get_db)):
    from ..main import get_security_endpoint
    return await get_security_endpoint(db).search(q)

@router.get("/securities/lookup")
async def lookup_security(symbol: str, db: Session = Depends(get_db)):
    from ..main import get_security_endpoint
    data = await get_security_endpoint(db).lookup(symbol)
    if not data: raise HTTPException(status_code=404, detail="Not found")
    return data

class BulkCreateRequest(BaseModel): symbols: List[str]
@router.post("/securities/bulk_create")
async def bulk_create_securities(request: BulkCreateRequest, db: Session = Depends(get_db)):
    from ..main import get_security_endpoint
    ep = get_security_endpoint(db); added = []; errors = []
    for s in request.symbols:
        s = s.upper().strip()
        if not s: continue
        if db.query(Security).filter(Security.symbol == s).first():
            errors.append(f"{s} already exists")
            continue
        try:
            d = await ep.lookup(s)
            if d:
                db.add(Security(symbol=s, name=d.get("name", s), security_type=d.get("security_type", SecurityType.STOCK), asset_class=d.get("asset_class"), current_price=d.get("current_price"), previous_close=d.get("previous_close"), open_price=d.get("open_price"), nav=d.get("nav"), range_52_week=d.get("range_52_week"), avg_volume=d.get("avg_volume"), yield_30_day=d.get("yield_30_day"), yield_7_day=d.get("yield_7_day")))
                added.append(s)
            else: errors.append(f"{s} not found")
        except Exception as e: errors.append(f"Error {s}: {e}")
    db.commit(); return {"added": added, "errors": errors}

class BulkDeleteRequest(BaseModel): symbols: List[str]
@router.post("/securities/bulk_delete")
async def bulk_delete_securities(request: BulkDeleteRequest, db: Session = Depends(get_db)):
    c = db.query(Security).filter(Security.symbol.in_([s.upper().strip() for s in request.symbols])).delete(synchronize_session=False)
    db.commit(); return {"deleted": c}

@router.post("/securities/test_endpoint")
async def test_security_endpoint(endpoint: str = Form(...), api_key: Optional[str] = Form(None)):
    from ..securities.endpoints import YahooScraperEndpoint, FinnhubEndpoint, AlphaVantageEndpoint
    try:
        if endpoint == "finnhub": ep = FinnhubEndpoint(api_key=api_key or "")
        elif endpoint == "alphavantage": ep = AlphaVantageEndpoint(api_key=api_key or "")
        else: ep = YahooScraperEndpoint()
        d = await ep.lookup("VOO")
        return {"success": True} if d and d.get("symbol") == "VOO" else {"success": False, "error": "No data"}
    except Exception as e: return {"success": False, "error": str(e)}

# --- SYSTEM IMPORT/EXPORT ---
@router.get("/settings/export", response_class=HTMLResponse)
async def system_export_page(request: Request, accept_language: str = Header(None), user: User = Depends(check_page_permission), db: Session = Depends(get_db)):
    t = get_text(accept_language)
    categories = get_activity_categories(db, "system_data", t)
    return templates.TemplateResponse(request, "export_data.html", {
        "t": t, "user": user, "heading": t.get("heading_system_export"),
        "action_url": "/admin/settings/export", "categories": categories,
        "default_filename": f"matika_system_config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    })

@router.post("/settings/export")
async def system_export(filename: str = Form(...), include_logging: bool = Form(False), include_endpoints: bool = Form(False), include_system_roles: bool = Form(False), user: User = Depends(check_page_permission), db: Session = Depends(get_db)):
    export_payload = {"metadata": {"type": "system_config", "version": get_system_setting(db, "version", "unknown"), "timestamp": datetime.now().isoformat()}}
    settings_data = {}
    if include_logging:
        for k in ["app_log_lines", "app_log_retention", "startup_log_lines", "startup_log_retention", "test_log_lines", "test_log_retention"]:
            s = db.query(SystemSetting).filter(SystemSetting.name == k).first()
            if s: settings_data[k] = s.value
    if include_endpoints:
        for k in ["security_data_endpoint", "security_data_api_key"]:
            s = db.query(SystemSetting).filter(SystemSetting.name == k).first()
            if s: settings_data[k] = s.value
    export_payload["system_settings"] = settings_data
    if include_system_roles:
        export_payload["roles"] = [{"name": r.name, "description": r.description, "is_system": True, "permissions": [{"path": p.page_path, "type": p.page_type, "level": p.level} for p in r.permissions]} for r in db.query(Role).filter(Role.is_system == True).all()]
    if not filename.endswith(".json"): filename += ".json"
    return JSONResponse(content=export_payload, headers={"Content-Disposition": f"attachment; filename={filename}"})

@router.get("/settings/import", response_class=HTMLResponse)
async def system_import_page(request: Request, accept_language: str = Header(None), user: User = Depends(check_page_permission), db: Session = Depends(get_db)):
    t = get_text(accept_language)
    return templates.TemplateResponse(request, "import_data.html", {
        "t": t, "user": user, "heading": t.get("heading_system_import"),
        "action_url": "/admin/settings/import", "categories": get_activity_categories(db, "system_data", t),
        "success": request.query_params.get("success") == "true", "error": request.query_params.get("error") == "true"
    })

@router.post("/settings/import")
async def system_import(file: UploadFile = File(...), include_logging: bool = Form(False), include_endpoints: bool = Form(False), include_system_roles: bool = Form(False), user: User = Depends(check_page_permission), db: Session = Depends(get_db)):
    try:
        data = json.loads(await file.read())
        if data.get("metadata", {}).get("type") != "system_config": raise Exception("Invalid file type")
        if "system_settings" in data:
            s_data = data["system_settings"]
            if include_logging:
                for k in ["app_log_lines", "app_log_retention", "startup_log_lines", "startup_log_retention", "test_log_lines", "test_log_retention"]:
                    if k in s_data:
                        s = db.query(SystemSetting).filter(SystemSetting.name == k).first()
                        if s: s.value = s_data[k]
                        else: db.add(SystemSetting(name=k, value=s_data[k], is_system=True))
            if include_endpoints:
                for k in ["security_data_endpoint", "security_data_api_key"]:
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
        db.commit(); return RedirectResponse(url="/admin/settings/import?success=true", status_code=303)
    except Exception as e:
        logger.error(f"System import failed: {e}"); db.rollback(); return RedirectResponse(url="/admin/settings/import?error=true", status_code=303)

# --- PERMISSIONS MAINTENANCE ---
@router.get("/permissions", response_class=HTMLResponse)
async def list_permissions(request: Request, accept_language: str = Header(None), user: User = Depends(check_page_permission), db: Session = Depends(get_db)):
    t = get_text(accept_language); perms = db.query(Permission).all(); pages = get_pages()
    grouped = {pt: {path: {"label": t.get(lk, path), "subjects": {}} for path, p_type, lk in pages if p_type == pt} for pt in PageType}
    for p in perms:
        sk = f"role:{p.role_id}" if p.role_id else f"user:{p.user_id}"
        if p.page_path in grouped.get(p.page_type, {}):
            s = grouped[p.page_type][p.page_path]["subjects"]
            if sk not in s: s[sk] = {"role": p.role, "user": p.user, "permissions": []}
            s[sk]["permissions"].append(p)
    return templates.TemplateResponse(request, "admin_permissions.html", {"t": t, "user": user, "grouped": grouped, "roles": db.query(Role).all(), "users": db.query(User).all(), "page_types": list(PageType), "permission_levels": list(PermissionLevel)})

@router.post("/permissions/create")
async def create_permission(page_path: str = Form(...), subject: str = Form(...), level: PermissionLevel = Form(...), db: Session = Depends(get_db)):
    st, sid = subject.split(":"); rid = int(sid) if st == "role" else None; uid = int(sid) if st == "user" else None
    pt = next((p[1] for p in get_pages() if p[0] == page_path), PageType.INFO)
    
    if level in [PermissionLevel.FULL, PermissionLevel.NONE]:
        db.query(Permission).filter(Permission.page_path == page_path, Permission.role_id == rid, Permission.user_id == uid).delete()
    else:
        db.query(Permission).filter(Permission.page_path == page_path, Permission.role_id == rid, Permission.user_id == uid, Permission.level.in_([PermissionLevel.FULL, PermissionLevel.NONE])).delete()
        db.query(Permission).filter(Permission.page_path == page_path, Permission.role_id == rid, Permission.user_id == uid, Permission.level == level).delete()

    db.add(Permission(page_path=page_path, page_type=pt, role_id=rid, user_id=uid, level=level))
    db.commit(); return RedirectResponse(url="/admin/permissions", status_code=303)

@router.post("/permissions/delete-subject")
async def delete_permission_subject(page_path: str = Form(...), subject: str = Form(...), db: Session = Depends(get_db)):
    st, sid = subject.split(":"); rid = int(sid) if st == "role" else None; uid = int(sid) if st == "user" else None
    db.query(Permission).filter(Permission.page_path == page_path, Permission.role_id == rid, Permission.user_id == uid).delete()
    pt = next((p[1] for p in get_pages() if p[0] == page_path), PageType.INFO)
    db.add(Permission(page_path=page_path, page_type=pt, role_id=rid, user_id=uid, level=PermissionLevel.NONE))
    db.commit(); return RedirectResponse(url="/admin/permissions", status_code=303)

@router.post("/permissions/delete/{perm_id}")
async def delete_permission(perm_id: int, db: Session = Depends(get_db)):
    p = db.query(Permission).filter(Permission.id == perm_id).first()
    if p:
        path, rid, uid = p.page_path, p.role_id, p.user_id; db.delete(p); db.commit()
        if db.query(Permission).filter(Permission.page_path == path, Permission.role_id == rid, Permission.user_id == uid).count() == 0:
            pt = next((pg[1] for pg in get_pages() if pg[0] == path), PageType.INFO)
            db.add(Permission(page_path=path, page_type=pt, role_id=rid, user_id=uid, level=PermissionLevel.NONE)); db.commit()
    return RedirectResponse(url="/admin/permissions", status_code=303)
