"""normalize notifications

Revision ID: 0025_normalize_notifications
Revises: 0024_material_requisitions
Create Date: 2026-06-16 14:30:00.000000
"""

from alembic import op


revision = "0025_normalize_notifications"
down_revision = "0024_material_requisitions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE notifications "
        "SET category = 'info' "
        "WHERE category NOT IN ('task', 'deadline', 'warning', 'info', 'exception')"
    )
    op.execute(
        "UPDATE notifications "
        "SET priority = 'normal' "
        "WHERE priority NOT IN ('low', 'normal', 'high', 'critical')"
    )
    op.execute(
        "UPDATE notifications "
        "SET action_url = '/purchasing' "
        "WHERE action_url = '/purchasing/material-requisitions'"
    )


def downgrade() -> None:
    pass
