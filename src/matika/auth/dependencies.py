from typing import Optional
from fastapi import Request, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..database import get_db, User

async def get_current_user(request: Request, db: Session = Depends(get_db)):
    """Retrieves the currently logged-in user from the session."""
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    user = db.query(User).filter(User.id == user_id).first()
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
