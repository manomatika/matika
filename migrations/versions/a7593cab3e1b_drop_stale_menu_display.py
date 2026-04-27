"""drop_stale_menu_display — remove permissions.menu_display stale column

Revision ID: a7593cab3e1b
Revises: dcdb5f511773
Create Date: 2026-04-26

permissions.menu_display was removed from the ORM model but never dropped
from the live database. Separated from the index migration so operators can
apply indexes first (zero-downtime), verify health, then clean up the column.
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "a7593cab3e1b"
down_revision: Union[str, Sequence[str], None] = "dcdb5f511773"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("permissions") as batch_op:
        batch_op.drop_column("menu_display")


def downgrade() -> None:
    with op.batch_alter_table("permissions") as batch_op:
        batch_op.add_column(sa.Column("menu_display", sa.Boolean(), nullable=True))
