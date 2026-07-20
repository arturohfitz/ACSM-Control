"""inventory operations center

Revision ID: 0036_inventory_operations
Revises: 0035_requisition_traceability
Create Date: 2026-07-20 14:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0036_inventory_operations"
down_revision: str | None = "0035_requisition_traceability"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "material_reception_items",
        sa.Column("accepted_quantity", sa.Numeric(14, 4), server_default="0", nullable=False),
    )
    op.add_column(
        "material_reception_items",
        sa.Column("rejected_quantity", sa.Numeric(14, 4), server_default="0", nullable=False),
    )
    op.execute(
        """
        UPDATE material_reception_items
        SET accepted_quantity = CASE
                WHEN condition_status = 'damaged' THEN 0
                ELSE received_quantity
            END,
            rejected_quantity = CASE
                WHEN condition_status = 'damaged' THEN received_quantity
                ELSE 0
            END
        """
    )
    op.execute(
        """
        UPDATE warehouse_stock AS stock
        SET quantity_on_hand = COALESCE((
            SELECT SUM(item.accepted_quantity)
            FROM material_reception_items AS item
            WHERE item.expected_item_id = stock.expected_item_id
        ), 0)
        """
    )

    op.create_table(
        "inventory_movements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("warehouse_id", sa.Integer(), sa.ForeignKey("project_warehouses.id"), nullable=False),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id"), nullable=True),
        sa.Column("house_model_id", sa.Integer(), sa.ForeignKey("house_models.id"), nullable=True),
        sa.Column(
            "house_model_material_requirement_id",
            sa.Integer(),
            sa.ForeignKey("house_model_material_requirements.id"),
            nullable=True,
        ),
        sa.Column(
            "reception_item_id",
            sa.Integer(),
            sa.ForeignKey("material_reception_items.id"),
            nullable=True,
            unique=True,
        ),
        sa.Column("movement_type", sa.String(length=40), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("unit", sa.String(length=40), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 4), nullable=False),
        sa.Column("reference", sa.String(length=160), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    for column in (
        "company_id",
        "project_id",
        "warehouse_id",
        "material_id",
        "house_model_id",
        "house_model_material_requirement_id",
        "reception_item_id",
    ):
        op.create_index(f"ix_inventory_movements_{column}", "inventory_movements", [column])

    op.execute(
        """
        INSERT INTO inventory_movements (
            company_id, project_id, warehouse_id, material_id, house_model_id,
            house_model_material_requirement_id, reception_item_id, movement_type,
            description, unit, quantity, reference, notes, created_at, updated_at
        )
        SELECT r.company_id, r.project_id, r.warehouse_id, ri.material_id, ri.house_model_id,
               ri.house_model_material_requirement_id, ri.id, 'receipt', ri.description,
               ri.unit, ri.accepted_quantity, r.delivery_reference, ri.notes,
               COALESCE(r.created_at, CURRENT_TIMESTAMP), COALESCE(r.updated_at, CURRENT_TIMESTAMP)
        FROM material_reception_items ri
        JOIN material_receptions r ON r.id = ri.reception_id
        WHERE ri.accepted_quantity > 0
        """
    )


def downgrade() -> None:
    op.drop_table("inventory_movements")
    op.drop_column("material_reception_items", "rejected_quantity")
    op.drop_column("material_reception_items", "accepted_quantity")
