"""model inventory control

Revision ID: 0030_model_inventory_control
Revises: 0029_agreement_approvals
Create Date: 2026-06-26 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0030_model_inventory_control"
down_revision = "0029_agreement_approvals"
branch_labels = None
depends_on = None


TRACKED_TABLES = (
    "supplier_rfq_items",
    "purchase_order_items",
    "expected_material_items",
    "material_reception_items",
    "warehouse_stock",
)


def _add_tracking_columns(table_name: str) -> None:
    op.add_column(table_name, sa.Column("house_model_id", sa.Integer(), nullable=True))
    op.add_column(
        table_name,
        sa.Column("house_model_material_requirement_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        f"fk_{table_name}_house_model_id",
        table_name,
        "house_models",
        ["house_model_id"],
        ["id"],
    )
    op.create_foreign_key(
        f"fk_{table_name}_hm_requirement_id",
        table_name,
        "house_model_material_requirements",
        ["house_model_material_requirement_id"],
        ["id"],
    )
    op.create_index(f"ix_{table_name}_house_model_id", table_name, ["house_model_id"])
    op.create_index(
        f"ix_{table_name}_hm_requirement_id",
        table_name,
        ["house_model_material_requirement_id"],
    )


def _drop_tracking_columns(table_name: str) -> None:
    op.drop_index(f"ix_{table_name}_hm_requirement_id", table_name=table_name)
    op.drop_index(f"ix_{table_name}_house_model_id", table_name=table_name)
    op.drop_constraint(f"fk_{table_name}_hm_requirement_id", table_name, type_="foreignkey")
    op.drop_constraint(f"fk_{table_name}_house_model_id", table_name, type_="foreignkey")
    op.drop_column(table_name, "house_model_material_requirement_id")
    op.drop_column(table_name, "house_model_id")


def upgrade() -> None:
    for table_name in TRACKED_TABLES:
        _add_tracking_columns(table_name)


def downgrade() -> None:
    for table_name in reversed(TRACKED_TABLES):
        _drop_tracking_columns(table_name)
