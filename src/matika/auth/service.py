import os
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional
from authlib.integrations.starlette_client import OAuth
from jose import jwt

# Settings — SECRET_KEY must be provided; the app refuses to start without it.
SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "CRITICAL: SECRET_KEY environment variable is not set. "
        "The application cannot start. Set it in your environment or .env file."
    )
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 # 24 hours

# --- PASSWORD HASHING ---
def verify_password(plain_password: str, hashed_password: str):
    if not hashed_password:
        return False
    try:
        # bcrypt.checkpw expects bytes
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

def get_password_hash(password: str):
    # bcrypt.hashpw expects bytes and returns bytes
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

# --- JWT TOKENS ---
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# --- OAUTH SETUP ---
def setup_oauth():
    oauth = OAuth()
    oauth.register(
        name="google",
        client_id=os.environ.get("GOOGLE_CLIENT_ID", "id"),
        client_secret=os.environ.get("GOOGLE_CLIENT_SECRET", "sec"),
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"}
    )
    oauth.register(
        name="github",
        client_id=os.environ.get("GITHUB_CLIENT_ID", "id"),
        client_secret=os.environ.get("GITHUB_CLIENT_SECRET", "sec"),
        access_token_url="https://github.com/login/oauth/access_token",
        authorize_url="https://github.com/login/oauth/authorize",
        api_base_url="https://api.github.com/",
        client_kwargs={"scope": "user:email"}
    )
    return oauth
