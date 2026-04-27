from sqlalchemy import Column, String, Integer, Boolean, Text, ForeignKey, Table, Enum as SQLEnum, LargeBinary, Index
from sqlalchemy.orm import relationship, declarative_base
from .core.constants import PageType, PermissionLevel

Base = declarative_base()

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
    page_path = Column(String, nullable=False, index=True)   # indexed: queried on every auth check
    page_type = Column(SQLEnum(PageType), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    level = Column(SQLEnum(PermissionLevel), nullable=False, default=PermissionLevel.NONE)
    is_system = Column(Boolean, default=False)

    __table_args__ = (
        # Composite index covering the most common auth query pattern:
        # WHERE page_path IN (...) AND (role_id IN (...) OR user_id = ?)
        Index("ix_permissions_path_role", "page_path", "role_id"),
        Index("ix_permissions_path_user", "page_path", "user_id"),
    )

    role = relationship("Role", back_populates="permissions")
    user = relationship("User", back_populates="permissions")

class Role(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(String)
    is_system = Column(Boolean, default=False)
    
    users = relationship("User", secondary=user_roles, back_populates="roles")
    permissions = relationship("Permission", back_populates="role", cascade="all, delete-orphan")

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
