"""initial_schema — add performance indexes to the permissions table

Revision ID: dcdb5f511773
Revises:
Create Date: 2026-04-26

Context
-------
The `permissions` table is queried on *every authenticated request* via
`security/service.py::check_page_permission`. Without indexes, this is a
full-table scan each time. This migration adds the five indexes identified
as critical during the Milestone 2 performance review.

Notes
-----
* Plugin-owned tables (e.g. EyeRate's `securities`) are intentionally
  excluded; plugins manage their own schema via `on_load() / create_all()`.
* The `permissions.menu_display` column present in pre-migration databases
  is a stale field that was removed from the ORM model. It is cleaned up in
  a subsequent migration (0002_drop_stale_menu_display.py) to give operators
  a clear rollback path.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "dcdb5f511773"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("permissions") as batch_op:
        batch_op.create_index("ix_permissions_page_path", ["page_path"], unique=False)
        batch_op.create_index("ix_permissions_role_id",   ["role_id"],   unique=False)
        batch_op.create_index("ix_permissions_user_id",   ["user_id"],   unique=False)
        batch_op.create_index("ix_permissions_path_role", ["page_path", "role_id"], unique=False)
        batch_op.create_index("ix_permissions_path_user", ["page_path", "user_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("permissions") as batch_op:
        batch_op.drop_index("ix_permissions_path_user")
        batch_op.drop_index("ix_permissions_path_role")
        batch_op.drop_index("ix_permissions_user_id")
        batch_op.drop_index("ix_permissions_role_id")
        batch_op.drop_index("ix_permissions_page_path")
