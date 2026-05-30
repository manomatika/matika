import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

# Must set these before importing app or database
test_db_path = os.path.abspath(os.path.join("data", "test_matika.db"))
if os.name == 'nt':
    os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:////{test_db_path.lstrip('/')}"

os.environ.setdefault("SECRET_KEY", "test-only-secret-key-never-use-in-production")
os.environ.pop("MATIKA_ENV", None)  # prevent ambient dev-mode from silently relaxing version checks

from matika.database import get_db
from matika.models import Base, User, UserSetting, SystemSetting, Role, user_roles
from matika.auth.service import get_password_hash
from matika.main import create_app, init_plugins

# Test database setup
TEST_DATABASE_URL = os.environ["DATABASE_URL"]
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session", autouse=True)
def setup_plugins(tmp_path_factory):
    import shutil
    import json
    from matika.core.paths import get_matika_version
    # Use a pytest-managed temp directory so tests never touch the project's
    # plugins/ folder (which may contain dev symlinks like eyerate).
    test_plugins_dir = str(tmp_path_factory.mktemp("matika_plugins"))
    os.environ["MATIKA_PLUGINS_DIR"] = test_plugins_dir

    mock_src = os.path.join(os.path.dirname(__file__), "plugins", "mock_plugin")
    mock_dest = os.path.join(test_plugins_dir, "mock_plugin")
    if os.path.exists(mock_src):
        shutil.copytree(mock_src, mock_dest)
        # Patch matika_version to match the running Matika version so the
        # mock plugin passes the compatibility check regardless of which
        # VERSION the repo is currently at.
        manifest_path = os.path.join(mock_dest, "applug.json")
        with open(manifest_path) as f:
            manifest = json.load(f)
        manifest["matika_version"] = get_matika_version()
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=4)

    yield

    # Remove the env var; pytest auto-cleans tmp_path_factory directories.
    os.environ.pop("MATIKA_PLUGINS_DIR", None)

@pytest.fixture(scope="session", autouse=True)
def setup_database(setup_plugins):
    # Ensure we are using the test database
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    # Stamp the Alembic version table so test_alembic_current_is_head can assert
    # without skipping. The schema was created via create_all() (equivalent to head),
    # so stamping head is always correct here.
    from alembic.config import Config
    from alembic import command as alembic_command
    alembic_ini = os.path.join(os.path.dirname(__file__), "..", "alembic.ini")
    alembic_cfg = Config(alembic_ini)
    alembic_command.stamp(alembic_cfg, "head")

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
    hashed_pwd = get_password_hash("testpassword")
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
    hashed_pwd = get_password_hash("adminpassword")
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
