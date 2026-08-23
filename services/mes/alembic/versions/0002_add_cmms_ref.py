"""Add cmms_ref and cmms_synced_at to work_orders.

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-16

Adds two nullable columns to work_orders:
  cmms_ref       TEXT        — GitHub Gist ID once synced to CMMS (NULL = not yet pushed)
  cmms_synced_at TIMESTAMPTZ — timestamp of last successful CMMS push

These are both nullable so existing rows are unaffected.
No seed data required.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE work_orders
          ADD COLUMN IF NOT EXISTS cmms_ref       TEXT,
          ADD COLUMN IF NOT EXISTS cmms_synced_at TIMESTAMPTZ;
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE work_orders
          DROP COLUMN IF EXISTS cmms_ref,
          DROP COLUMN IF EXISTS cmms_synced_at;
    """)
