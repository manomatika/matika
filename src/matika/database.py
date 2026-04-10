import os
import sys
from enum import Enum
from sqlalchemy import create_engine, Column, String, Integer, Boolean, Text, ForeignKey, Table, Enum as SQLEnum, LargeBinary
from sqlalchemy.orm import sessionmaker, declarative_base, Session, relationship

from .core.paths import BASE_DIR, ROOT_DIR

db_path = os.path.join(ROOT_DIR, "data", "matika.db")
# Standard SQLAlchemy format for absolute path on Unix is sqlite:////path/to/db
# On Windows it is sqlite:///C:\path\to\db
if DATABASE_URL_ENV := os.environ.get("DATABASE_URL"):
    DATABASE_URL = DATABASE_URL_ENV
else:
    if os.name == 'nt':
        DATABASE_URL = f"sqlite:///{db_path}"
    else:
        # Four slashes for absolute path on Unix
        DATABASE_URL = f"sqlite:////{db_path.lstrip('/')}"

# Only use check_same_thread for SQLite
engine_kwargs = {}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class PageType(str, Enum):
    MAINTENANCE = "Maintenance"
    SETTINGS = "Settings"
    INFO = "Info"

class PermissionLevel(str, Enum):
    CREATE = "Create"
    UPDATE = "Update"
    DELETE = "Delete"
    READ = "Read"
    FULL = "Full"
    NONE = "None"

class SecurityType(str, Enum):
    STOCK = "Stock"
    BOND = "Bond"
    MUTUAL_FUND = "Mutual Fund"
    ETF = "ETF"
    MONEY_MARKET = "Money Market"

class AssetClass(str, Enum):
    LARGE_CAP_STOCK = "Large Cap Stock"
    SMALL_CAP_STOCK = "Small Cap Stock"
    INTERNATIONAL_STOCK = "International Stock"
    DOMESTIC_BOND = "Domestic Bond"
    INTERNATIONAL_BOND = "International Bond"
    MONEY_MARKET = "Money Market"
    CASH = "Cash"

# Many-to-Many Association Table
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id"), primary_key=True),
)

class SystemSetting(Base):
    __tablename__ = "system_settings"
    name = Column(String, primary_key=True, index=True)
    value = Column(String)
    is_system = Column(Boolean, default=False)

class UserSetting(Base):
    __tablename__ = "user_settings"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    name = Column(String, index=True)
    value = Column(String)
    
    user = relationship("User", back_populates="settings")

class Permission(Base):
    __tablename__ = "permissions"
    id = Column(Integer, primary_key=True, index=True)
    page_path = Column(String, nullable=False) # e.g. "/admin/users"
    page_type = Column(SQLEnum(PageType), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    level = Column(SQLEnum(PermissionLevel), nullable=False, default=PermissionLevel.NONE)
    is_system = Column(Boolean, default=False)

    role = relationship("Role", back_populates="permissions")
    user = relationship("User", back_populates="permissions")

class Security(Base):
    __tablename__ = "securities"
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    security_type = Column(SQLEnum(SecurityType), nullable=False)
    asset_class = Column(SQLEnum(AssetClass), nullable=True) # Optional as requested
    
    previous_close = Column(String, nullable=True)
    open_price = Column(String, nullable=True)
    current_price = Column(String, nullable=True)
    nav = Column(String, nullable=True)
    range_52_week = Column(String, nullable=True)
    avg_volume = Column(String, nullable=True)
    yield_30_day = Column(String, nullable=True)
    yield_7_day = Column(String, nullable=True)

class Role(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(String)
    is_system = Column(Boolean, default=False)
    
    users = relationship("User", secondary=user_roles, back_populates="roles")
    permissions = relationship("Permission", back_populates="role", cascade="all, delete-orphan")

from passlib.context import CryptContext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String, nullable=True)
    is_authorized = Column(Boolean, default=True)
    force_password_change = Column(Boolean, default=False)
    provider = Column(String, default="local")
    profile_json = Column(Text, nullable=True)
    photo_url = Column(String, nullable=True)
    photo_blob = Column(LargeBinary, nullable=True)
    photo_mime_type = Column(String, nullable=True)
    
    settings = relationship("UserSetting", back_populates="user", cascade="all, delete-orphan")
    roles = relationship("Role", secondary=user_roles, back_populates="users")
    permissions = relationship("Permission", back_populates="user", cascade="all, delete-orphan")

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
        "version": "unknown"
    }
    
    # Update version from file system if available
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
    
    db.commit() # Commit roles so they have IDs

    # 3. Seed default permissions for roles
    # Identify unique pages from database.py get_pages()
    pages_list = get_pages()

    admin_menu_pages = ["/admin/roles", "/admin/permissions", "/admin/users", "/settings/system", "/admin/securities", "/admin/settings/export", "/admin/settings/import"]

    # Clear old type-based permissions to avoid confusion during this migration
    db.query(Permission).filter(Permission.page_path == None).delete()

    for path, pt, label_key in pages_list:
        # Admin Role: Gets FULL for all pages
        existing_admin = db.query(Permission).filter(
            Permission.role_id == admin_role.id,
            Permission.page_path == path
        ).first()
        if not existing_admin:
            db.add(Permission(role_id=admin_role.id, page_path=path, page_type=pt, level=PermissionLevel.FULL, is_system=True))

        # User Role: 
        # NONE for Admin menu pages, FULL for others
        existing_user = db.query(Permission).filter(
            Permission.role_id == user_role.id,
            Permission.page_path == path
        ).first()
        if not existing_user:
            level = PermissionLevel.NONE if path in admin_menu_pages else PermissionLevel.FULL
            db.add(Permission(role_id=user_role.id, page_path=path, page_type=pt, level=level, is_system=True))
    
    db.commit()
    
    # 4. Seed default admin user
    admin_user = db.query(User).filter(User.username == "admin").first()
    if not admin_user:
        hashed_pwd = pwd_context.hash("adminpassword")
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
        print("Default admin user created: admin / adminpassword")

    # Ensure admin user has Admin role
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
        ("/admin/securities", PageType.MAINTENANCE, "item_securities"),
        ("/admin/permissions", PageType.MAINTENANCE, "item_permissions"),
    ]
