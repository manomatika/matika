"""Regression for the logging settings clean-break migration (matika#118).

Exercises the real Alembic migration ``b1f2c3d4e5a6`` against a pre-clean-break
database and asserts it renames ``app_* -> aggregate_*`` (value preserved) and
drops the dead ``test_*`` rows, leaving unrelated settings untouched.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

_PREV_HEAD = "a7593cab3e1b"


def _alembic_cfg(url: str) -> Config:
    repo_root = Path(__file__).resolve().parent.parent
    cfg = Config(str(repo_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(repo_root / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def test_migration_renames_app_to_aggregate_and_drops_test(tmp_path, monkeypatch):
    from matika.models import Base

    db_file = tmp_path / "mig.db"
    url = f"sqlite:///{db_file}"
    # migrations/env.py::get_url() reads DATABASE_URL — point it at the temp DB.
    monkeypatch.setenv("DATABASE_URL", url)

    # Build the pre-clean-break schema + the OLD settings rows.
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        for name, value in [
            ("app_log_lines", "250"), ("app_log_retention", "20"),
            ("startup_log_lines", "100"), ("startup_log_retention", "10"),
            ("test_log_lines", "77"), ("test_log_retention", "5"),
        ]:
            conn.execute(
                text(
                    "INSERT INTO system_settings (name, value, is_system) "
                    "VALUES (:n, :v, 1)"
                ),
                {"n": name, "v": value},
            )
    engine.dispose()

    # Stamp to the pre-clean-break head, then upgrade — runs ONLY our migration.
    cfg = _alembic_cfg(url)
    command.stamp(cfg, _PREV_HEAD)
    command.upgrade(cfg, "head")

    engine = create_engine(url)
    with engine.connect() as conn:
        rows = dict(conn.execute(text("SELECT name, value FROM system_settings")).all())
    engine.dispose()

    # Renamed, values preserved.
    assert rows.get("aggregate_log_lines") == "250"
    assert rows.get("aggregate_log_retention") == "20"
    # Old app_* names gone.
    assert "app_log_lines" not in rows
    assert "app_log_retention" not in rows
    # Dead test_* rows dropped.
    assert "test_log_lines" not in rows
    assert "test_log_retention" not in rows
    # Unrelated settings untouched.
    assert rows.get("startup_log_lines") == "100"
    assert rows.get("startup_log_retention") == "10"


def test_migration_downgrade_restores_app_names(tmp_path, monkeypatch):
    from matika.models import Base

    db_file = tmp_path / "mig_down.db"
    url = f"sqlite:///{db_file}"
    monkeypatch.setenv("DATABASE_URL", url)

    engine = create_engine(url)
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO system_settings (name, value, is_system) "
                "VALUES ('aggregate_log_lines', '150', 1)"
            )
        )
    engine.dispose()

    cfg = _alembic_cfg(url)
    command.stamp(cfg, "head")
    command.downgrade(cfg, _PREV_HEAD)

    engine = create_engine(url)
    with engine.connect() as conn:
        rows = dict(conn.execute(text("SELECT name, value FROM system_settings")).all())
    engine.dispose()

    assert rows.get("app_log_lines") == "150"          # rename reversed, value kept
    assert "aggregate_log_lines" not in rows
    assert rows.get("test_log_lines") == "100"         # re-seeded default
    assert rows.get("test_log_retention") == "10"
