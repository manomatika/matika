import os
import json
from passlib.context import CryptContext
from authlib.integrations.starlette_client import OAuth

# --- PASSWORD HASHING ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    if not hashed_password:
        return False
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

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
