import os
import secrets
import time
from typing import Optional
from fastapi import Request, Depends, HTTPException, Form, status
from sqlalchemy.orm import Session, subqueryload
from ..database import get_db, get_system_setting
from ..models import User

_IS_TESTING = (
    "pytest" in os.environ.get("PYTEST_CURRENT_TEST", "")
    or "PYTEST_VERSION" in os.environ
)

def get_current_user(request: Request, db: Session = Depends(get_db)):
    """Retrieves the currently logged-in user from the session with inactivity timeout."""
    user_id = request.session.get("user_id")
    last_activity = request.session.get("last_activity")
    
    if not user_id:
        return None
        
    now = int(time.time())

    # Absolute session cap — even persistent sessions expire after 30 days.
    SESSION_MAX_SECONDS = 30 * 24 * 3600
    session_created = request.session.get("session_created")
    if session_created and now - int(session_created) > SESSION_MAX_SECONDS:
        request.session.clear()
        return None

    # Idle timeout (skipped for persistent "remember me" sessions).
    if last_activity and not request.session.get("is_persistent"):
        idle_timeout = int(get_system_setting(db, "session_idle_timeout", "1800"))
        if now - int(last_activity) > idle_timeout:
            request.session.clear()
            return None

    # Update last activity
    request.session["last_activity"] = now
    
    # Eager load roles to avoid DetachedInstanceError in templates
    user = db.query(User).options(subqueryload(User.roles)).filter(User.id == user_id).first()
    
    if not user:
        request.session.clear()
        return None
    return user

async def validate_csrf(
    request: Request,
    csrf_token: Optional[str] = Form(None),
) -> None:
    """
    Validates the CSRF token submitted with a form against the session-stored token.
    Skipped in test environments (PYTEST_VERSION / PYTEST_CURRENT_TEST set).
    Must be added as a dependency to every state-changing POST route that uses
    form data and is accessed by authenticated users.
    """
    if _IS_TESTING:
        return
    session_token = request.session.get("csrf_token")
    if not session_token or not csrf_token:
        raise HTTPException(status_code=403, detail="CSRF validation failed")
    if not secrets.compare_digest(session_token, csrf_token):
        raise HTTPException(status_code=403, detail="CSRF validation failed")


def login_required(user: Optional[User] = Depends(get_current_user)):
    """Dependency that ensures a user is authenticated and authorized."""
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    if not user.is_authorized:
        raise HTTPException(status_code=403, detail="User not authorized")
    return user
