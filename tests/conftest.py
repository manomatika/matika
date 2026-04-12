import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

# Must set this before importing app or database
test_db_path = os.path.abspath(os.path.join("data", "test_matika.db"))
if os.name == 'nt':
    os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:////{test_db_path.lstrip('/')}"

from matika.database import Base, get_db, User, UserSetting, SystemSetting, Role, pwd_context, user_roles
from matika.main import create_app, init_plugins

# Test database setup
TEST_DATABASE_URL = os.environ["DATABASE_URL"]
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session", autouse=True)
def setup_plugins():
    # 1. Create plugins directory in PROJECT ROOT
    from matika.core.paths import ROOT_DIR
    plugins_dir = os.path.join(ROOT_DIR, "plugins")
    os.makedirs(plugins_dir, exist_ok=True)
    
    # Path to eyerate relative to matika root
    eyerate_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "eyerate"))
    eyerate_dest = os.path.join(plugins_dir, "eyerate")
    
    if not os.path.exists(eyerate_dest):
        try:
            os.symlink(eyerate_src, eyerate_dest)
        except OSError:
            import shutil
            if os.path.exists(eyerate_dest): shutil.rmtree(eyerate_dest)
            shutil.copytree(eyerate_src, eyerate_dest)
    
    yield

@pytest.fixture(scope="session", autouse=True)
def setup_database(setup_plugins):
    # Ensure we are using the test database
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    # Initialize session for seeding
    db = TestingSessionLocal()
    
    # Seed default roles, permissions, and settings for tests
    from matika.database import init_db
    init_db(db)
        
    db.close()
    
    yield
    
    # Cleanup after all tests
    Base.metadata.drop_all(bind=engine)
    if os.path.exists("./data/test_matika.db"):
        os.remove("./data/test_matika.db")

@pytest.fixture
def db():
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    
    # We want to start each test with a clean database state.
    from matika.database import init_db, Permission
    session.execute(user_roles.delete())
    session.query(User).delete()
    session.query(Permission).delete()
    session.commit()

    # Re-seed for every test to ensure consistent state
    init_db(session)

    yield session
    
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture
def test_app(db):
    # Fresh app for each test
    app_instance = create_app()
    # Initialize plugins for THIS fresh app instance
    init_plugins(app_instance, db)
    return app_instance

@pytest.fixture
def client(test_app, db):
    def override_get_db():
        try:
            yield db
        finally:
            pass # Session is managed by the fixture

    test_app.dependency_overrides[get_db] = override_get_db
    with TestClient(test_app) as c:
        yield c
    test_app.dependency_overrides.clear()

@pytest.fixture
def test_user(db):
    hashed_pwd = pwd_context.hash("testpassword")
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=hashed_pwd,
        is_authorized=True,
        force_password_change=False
    )
    # Give it User role
    user_role = db.query(Role).filter(Role.name == "User").first()
    if user_role:
        user.roles.append(user_role)
    
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@pytest.fixture
def test_admin(db):
    hashed_pwd = pwd_context.hash("adminpassword")
    user = User(
        username="adminuser",
        email="admin@example.com",
        hashed_password=hashed_pwd,
        is_authorized=True,
        force_password_change=False
    )
    # Give it admin role
    admin_role = db.query(Role).filter(Role.name == "Admin").first()
    user.roles.append(admin_role)
    
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
