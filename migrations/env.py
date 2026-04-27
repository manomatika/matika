"""
Alembic migration environment for Matika core schema.

Plugin schemas (e.g. EyeRate's `securities` table) are managed by each
plugin's own `on_load()` / `create_all()` call and are intentionally
outside this migration scope. See the AppLug development guide for
plugin-specific schema migration patterns.
"""
import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Make the matika package importable from the repo root.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Import Matika's declarative Base so Alembic can introspect all core models.
from matika.models import Base  # noqa: E402

# ---------------------------------------------------------------------------
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    """Resolve DATABASE_URL from environment, falling back to dev SQLite."""
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    from matika.core.paths import ROOT_DIR
    db_path = os.path.join(ROOT_DIR, "data", "matika.db")
    if os.name == "nt":
        return f"sqlite:///{db_path}"
    return f"sqlite:////{db_path.lstrip('/')}"


def run_migrations_offline() -> None:
    """Generate SQL without a live DB connection."""
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,   # required for SQLite ALTER TABLE support
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Connect to the live DB and apply pending migrations."""
    cfg = config.get_section(config.config_ini_section, {})
    cfg["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,   # required for SQLite ALTER TABLE support
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
