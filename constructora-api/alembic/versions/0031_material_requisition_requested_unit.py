"""material requisition requested unit

Revision ID: 0031_material_requisition_requested_unit
Revises: 0030_model_inventory_control
Create Date: 2026-06-27 14:05:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0031_material_requisition_requested_unit"
down_revision = "0030_model_inventory_control"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "material_requisition_items",
        sa.Column("requested_unit", sa.String(length=40), nullable=True),
    )
    op.execute("UPDATE material_requisition_items SET requested_unit = unit WHERE requested_unit IS NULL")


def downgrade() -> None:
    op.drop_column("material_requisition_items", "requested_unit")
