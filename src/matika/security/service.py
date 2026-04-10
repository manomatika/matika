import logging
from fastapi import Request, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db, User, Permission, PermissionLevel, PageType
from ..auth.dependencies import login_required

logger = logging.getLogger(__name__)

async def check_page_permission(request: Request, db: Session = Depends(get_db), user: User = Depends(login_required)):
    """Validates that the current user has access to the requested path."""
    request.state.user = user
    path = request.url.path
    role_ids = [role.id for role in user.roles]
    
    # Check inheritance: /admin/users -> /admin
    potential_paths = [path]
    parts = path.strip("/").split("/")
    while len(parts) > 1:
        parts.pop()
        potential_paths.append("/" + "/".join(parts))

    permission = db.query(Permission).filter(
        Permission.page_path.in_(potential_paths),
        (Permission.user_id == user.id) | (Permission.role_id.in_(role_ids)),
        Permission.level != PermissionLevel.NONE
    ).first()    

    if not permission:
        logger.warning(f"Access Denied for user {user.email} to {path}")
        raise HTTPException(status_code=403, detail="Access Denied")
    return user
