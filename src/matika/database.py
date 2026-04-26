import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from .core.paths import BASE_DIR, ROOT_DIR
from .core.constants import PageType, PermissionLevel
from .models import Base, User, Role, Permission, SystemSetting, user_roles
from .auth.service import get_password_hash

db_path = os.path.join(ROOT_DIR, "data", "matika.db")

if DATABASE_URL_ENV := os.environ.get("DATABASE_URL"):
    DATABASE_URL = DATABASE_URL_ENV
else:
    if os.name == 'nt':
        DATABASE_URL = f"sqlite:///{db_path}"
    else:
        DATABASE_URL = f"sqlite:////{db_path.lstrip('/')}"

engine_kwargs: dict = {}
if DATABASE_URL.startswith("sqlite"):
    # SQLite: disable the single-thread check for use with FastAPI's dependency injection.
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # PostgreSQL / MySQL: connection pool tuned for multi-user production use.
    # pool_size      — persistent connections kept alive between requests
    # max_overflow   — additional connections allowed under burst load
    # pool_recycle   — close connections older than 30 min (avoids "server gone away")
    # pool_pre_ping  — validate connections before use (catches network drops)
    engine_kwargs.update(
        pool_size=10,
        max_overflow=20,
        pool_recycle=1800,
        pool_pre_ping=True,
    )

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db(db: Session = None):
    Base.metadata.create_all(bind=engine)
    standalone = False
    if db is None:
        db = SessionLocal()
        standalone = True
    
    # 1. Seed initial system settings
    log_defaults = {
        "app_log_lines": "100", "app_log_retention": "10",
        "test_log_lines": "100", "test_log_retention": "10",
        "startup_log_lines": "100", "startup_log_retention": "10",
        "session_idle_timeout": "1800",
        "version": "unknown"
    }
    
    version_file = os.path.join(BASE_DIR, "VERSION")
    if os.path.exists(version_file):
        with open(version_file, "r") as f:
            v_val = f.read().strip()
            if v_val: log_defaults["version"] = v_val

    for name, value in log_defaults.items():
        existing = db.query(SystemSetting).filter(SystemSetting.name == name).first()
        if not existing:
            db.add(SystemSetting(name=name, value=value, is_system=True))
        elif name == "version":
            existing.value = value
    
    # 2. Seed default roles
    admin_role = db.query(Role).filter(Role.name == "Admin").first()
    if not admin_role:
        admin_role = Role(name="Admin", description="System Administrator with full access", is_system=True)
        db.add(admin_role)
        
    user_role = db.query(Role).filter(Role.name == "User").first()
    if not user_role:
        user_role = Role(name="User", description="Standard user with limited access", is_system=True)
        db.add(user_role)
    
    db.commit()

    # 3. Seed default permissions
    pages_list = get_pages()
    admin_menu_pages = ["/admin/roles", "/admin/permissions", "/admin/users", "/settings/system", "/admin/settings/export", "/admin/settings/import"]

    for path, pt, label_key in pages_list:
        existing_admin = db.query(Permission).filter(Permission.role_id == admin_role.id, Permission.page_path == path).first()
        if not existing_admin:
            db.add(Permission(role_id=admin_role.id, page_path=path, page_type=pt, level=PermissionLevel.FULL, is_system=True))

        existing_user = db.query(Permission).filter(Permission.role_id == user_role.id, Permission.page_path == path).first()
        if not existing_user:
            level = PermissionLevel.NONE if path in admin_menu_pages else PermissionLevel.FULL
            db.add(Permission(role_id=user_role.id, page_path=path, page_type=pt, level=level, is_system=True))
    
    db.commit()
    
    # 4. Seed default admin user
    admin_user = db.query(User).filter(User.username == "admin").first()
    if not admin_user:
        hashed_pwd = get_password_hash("adminpassword")
        admin_user = User(
            username="admin",
            email="admin@matika.local",
            hashed_password=hashed_pwd,
            is_authorized=True,
            force_password_change=True
        )
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)

    if admin_role not in admin_user.roles:
        admin_user.roles.append(admin_role)
    if user_role not in admin_user.roles:
        admin_user.roles.append(user_role)
    
    db.commit()
    if standalone:
        db.close()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_system_setting(db: Session, name: str, default: str):
    res = db.query(SystemSetting).filter(SystemSetting.name == name).first()
    return res.value if res else default

def get_user_setting(db: Session, user_id: int, name: str, default: str = "") -> str:
    from .models import UserSetting
    res = db.query(UserSetting).filter(
        UserSetting.user_id == user_id,
        UserSetting.name == name,
    ).first()
    return res.value if res else default

def set_user_setting(db: Session, user_id: int, name: str, value: str) -> None:
    from .models import UserSetting
    existing = db.query(UserSetting).filter(
        UserSetting.user_id == user_id,
        UserSetting.name == name,
    ).first()
    if existing:
        existing.value = value
    else:
        db.add(UserSetting(user_id=user_id, name=name, value=value))
    db.commit()

def get_pages():
    """Returns the master list of pages, their types, and their translation keys."""
    return [
        ("/", PageType.INFO, "item_home"),
        ("/register", PageType.INFO, "nav_register"),
        ("/forgot-password", PageType.INFO, "link_forgot_password"),
        ("/login", PageType.INFO, "nav_login"),
        ("/logout", PageType.INFO, "nav_logout"),
        ("/show-log", PageType.INFO, "item_show_log"),
        ("/about", PageType.INFO, "item_about"),
        ("/change-password", PageType.INFO, "heading_change_password"),
        ("/settings/user", PageType.SETTINGS, "item_user_settings"),
        ("/settings/user/change-username", PageType.SETTINGS, "link_change_username"),
        ("/settings/user/change-password", PageType.SETTINGS, "link_change_password"),
        ("/settings/user/upload-photo", PageType.SETTINGS, "label_profile_photo"),
        ("/settings/system", PageType.SETTINGS, "item_system_settings"),
        ("/settings/export", PageType.SETTINGS, "link_export_data"),
        ("/settings/import", PageType.SETTINGS, "link_import_data"),
        ("/admin/settings/export", PageType.SETTINGS, "link_system_export"),
        ("/admin/settings/import", PageType.SETTINGS, "link_system_import"),
        ("/admin/users", PageType.MAINTENANCE, "item_users"),
        ("/admin/roles", PageType.MAINTENANCE, "item_roles"),
        ("/admin/permissions", PageType.MAINTENANCE, "item_permissions"),
    ]
