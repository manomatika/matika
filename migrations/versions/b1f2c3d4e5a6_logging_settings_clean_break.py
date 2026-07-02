"""logging_settings_clean_break — rename app_* -> aggregate_*, drop test_* log settings

Revision ID: b1f2c3d4e5a6
Revises: a7593cab3e1b
Create Date: 2026-07-02

Context
-------
The logging-unification clean break (matika#118) renames the "app" log sink to the
"aggregate" (runtime) sink and removes the dead unit-test log section entirely. The
per-sink retention/line settings live as rows in ``system_settings`` (name is the
primary key), so this is a DATA migration, not a schema change:

  * ``app_log_lines``      -> ``aggregate_log_lines``      (value preserved)
  * ``app_log_retention``  -> ``aggregate_log_retention``  (value preserved)
  * ``test_log_lines`` / ``test_log_retention``  -> removed

Fresh installs never carry the old rows (``init_db`` seeds the new names directly);
this migration only transforms an existing pre-clean-break database on upgrade.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b1f2c3d4e5a6"
down_revision: Union[str, Sequence[str], None] = "a7593cab3e1b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_RENAMES = [
    ("app_log_lines", "aggregate_log_lines"),
    ("app_log_retention", "aggregate_log_retention"),
]
_DROPPED = ["test_log_lines", "test_log_retention"]


def upgrade() -> None:
    bind = op.get_bind()
    # Rename the app_* rows to aggregate_*, preserving each value. Only touch the
    # old name so a re-run (or a DB already seeded with the new name) is a no-op.
    for old, new in _RENAMES:
        bind.execute(
            sa.text(
                "UPDATE system_settings SET name = :new "
                "WHERE name = :old AND NOT EXISTS "
                "(SELECT 1 FROM system_settings WHERE name = :new)"
            ),
            {"old": old, "new": new},
        )
    # Remove the dead test-log rows.
    for name in _DROPPED:
        bind.execute(
            sa.text("DELETE FROM system_settings WHERE name = :name"),
            {"name": name},
        )


def downgrade() -> None:
    bind = op.get_bind()
    # Reverse the rename (value preserved).
    for old, new in _RENAMES:
        bind.execute(
            sa.text(
                "UPDATE system_settings SET name = :old "
                "WHERE name = :new AND NOT EXISTS "
                "(SELECT 1 FROM system_settings WHERE name = :old)"
            ),
            {"old": old, "new": new},
        )
    # Re-seed the removed test-log rows with their historical defaults (the
    # original values cannot be recovered once dropped).
    for name in _DROPPED:
        bind.execute(
            sa.text(
                "INSERT INTO system_settings (name, value, is_system) "
                "SELECT :name, :value, 1 WHERE NOT EXISTS "
                "(SELECT 1 FROM system_settings WHERE name = :name)"
            ),
            {"name": name, "value": "100" if name.endswith("_lines") else "10"},
        )
