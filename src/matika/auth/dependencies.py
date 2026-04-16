from fastapi import Request, Depends, HTTPException, status
import time
from sqlalchemy.orm import Session, subqueryload
from ..database import get_db, get_system_setting
from ..models import User

def get_current_user(request: Request, db: Session = Depends(get_db)):
    """Retrieves the currently logged-in user from the session with inactivity timeout."""
    user_id = request.session.get("user_id")
    last_activity = request.session.get("last_activity")
    
    if not user_id:
        return None
        
    # Check for inactivity timeout (unless persistent)
    now = int(time.time())
    if last_activity and not request.session.get("is_persistent"):
        # Fetch dynamic timeout from settings (default to 1800s if missing)
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

def login_required(user: Optional[User] = Depends(get_current_user)):
    """Dependency that ensures a user is authenticated and authorized."""
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    if not user.is_authorized:
        raise HTTPException(status_code=403, detail="User not authorized")
    return user
