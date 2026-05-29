"""project inventory reception

Revision ID: 0004_project_inventory
Revises: 0003_role_company_scope
Create Date: 2026-05-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004_project_inventory"
down_revision: Union[str, None] = "0003_role_company_scope"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "project_warehouses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], name=op.f("fk_project_warehouses_company_id_companies")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_project_warehouses_project_id_projects")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project_warehouses")),
        sa.UniqueConstraint("project_id", "name", name="uq_project_warehouses_project_name"),
    )
    op.create_index(op.f("ix_project_warehouses_company_id"), "project_warehouses", ["company_id"], unique=False)
    op.create_index(op.f("ix_project_warehouses_project_id"), "project_warehouses", ["project_id"], unique=False)

    op.create_table(
        "expected_material_lists",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("warehouse_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("source_document_name", sa.String(length=255), nullable=True),
        sa.Column("source_notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], name=op.f("fk_expected_material_lists_company_id_companies")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_expected_material_lists_project_id_projects")),
        sa.ForeignKeyConstraint(["warehouse_id"], ["project_warehouses.id"], name=op.f("fk_expected_material_lists_warehouse_id_project_warehouses")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_expected_material_lists")),
    )
    op.create_index(op.f("ix_expected_material_lists_company_id"), "expected_material_lists", ["company_id"], unique=False)
    op.create_index(op.f("ix_expected_material_lists_project_id"), "expected_material_lists", ["project_id"], unique=False)
    op.create_index(op.f("ix_expected_material_lists_warehouse_id"), "expected_material_lists", ["warehouse_id"], unique=False)

    op.create_table(
        "expected_material_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("expected_list_id", sa.Integer(), nullable=False),
        sa.Column("material_id", sa.Integer(), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("unit", sa.String(length=40), nullable=False),
        sa.Column("expected_quantity", sa.Numeric(14, 4), nullable=False),
        sa.Column("received_quantity", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], name=op.f("fk_expected_material_items_company_id_companies")),
        sa.ForeignKeyConstraint(["expected_list_id"], ["expected_material_lists.id"], ondelete="CASCADE", name=op.f("fk_expected_material_items_expected_list_id_expected_material_lists")),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"], name=op.f("fk_expected_material_items_material_id_materials")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_expected_material_items")),
    )
    op.create_index(op.f("ix_expected_material_items_company_id"), "expected_material_items", ["company_id"], unique=False)
    op.create_index(op.f("ix_expected_material_items_expected_list_id"), "expected_material_items", ["expected_list_id"], unique=False)
    op.create_index(op.f("ix_expected_material_items_material_id"), "expected_material_items", ["material_id"], unique=False)

    op.create_table(
        "material_receptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("warehouse_id", sa.Integer(), nullable=False),
        sa.Column("expected_list_id", sa.Integer(), nullable=False),
        sa.Column("received_at", sa.Date(), nullable=False),
        sa.Column("delivery_reference", sa.String(length=160), nullable=True),
        sa.Column("delivered_by", sa.String(length=160), nullable=True),
        sa.Column("received_by", sa.String(length=160), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], name=op.f("fk_material_receptions_company_id_companies")),
        sa.ForeignKeyConstraint(["expected_list_id"], ["expected_material_lists.id"], name=op.f("fk_material_receptions_expected_list_id_expected_material_lists")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_material_receptions_project_id_projects")),
        sa.ForeignKeyConstraint(["warehouse_id"], ["project_warehouses.id"], name=op.f("fk_material_receptions_warehouse_id_project_warehouses")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_material_receptions")),
    )
    op.create_index(op.f("ix_material_receptions_company_id"), "material_receptions", ["company_id"], unique=False)
    op.create_index(op.f("ix_material_receptions_expected_list_id"), "material_receptions", ["expected_list_id"], unique=False)
    op.create_index(op.f("ix_material_receptions_project_id"), "material_receptions", ["project_id"], unique=False)
    op.create_index(op.f("ix_material_receptions_warehouse_id"), "material_receptions", ["warehouse_id"], unique=False)

    op.create_table(
        "material_reception_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("reception_id", sa.Integer(), nullable=False),
        sa.Column("expected_item_id", sa.Integer(), nullable=False),
        sa.Column("material_id", sa.Integer(), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("unit", sa.String(length=40), nullable=False),
        sa.Column("received_quantity", sa.Numeric(14, 4), nullable=False),
        sa.Column("condition_status", sa.String(length=40), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["expected_item_id"], ["expected_material_items.id"], name=op.f("fk_material_reception_items_expected_item_id_expected_material_items")),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"], name=op.f("fk_material_reception_items_material_id_materials")),
        sa.ForeignKeyConstraint(["reception_id"], ["material_receptions.id"], ondelete="CASCADE", name=op.f("fk_material_reception_items_reception_id_material_receptions")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_material_reception_items")),
    )
    op.create_index(op.f("ix_material_reception_items_expected_item_id"), "material_reception_items", ["expected_item_id"], unique=False)
    op.create_index(op.f("ix_material_reception_items_material_id"), "material_reception_items", ["material_id"], unique=False)
    op.create_index(op.f("ix_material_reception_items_reception_id"), "material_reception_items", ["reception_id"], unique=False)

    op.create_table(
        "warehouse_stock",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("warehouse_id", sa.Integer(), nullable=False),
        sa.Column("expected_item_id", sa.Integer(), nullable=False),
        sa.Column("material_id", sa.Integer(), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("unit", sa.String(length=40), nullable=False),
        sa.Column("quantity_on_hand", sa.Numeric(14, 4), nullable=False, server_default="0"),
        *timestamps(),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], name=op.f("fk_warehouse_stock_company_id_companies")),
        sa.ForeignKeyConstraint(["expected_item_id"], ["expected_material_items.id"], name=op.f("fk_warehouse_stock_expected_item_id_expected_material_items")),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"], name=op.f("fk_warehouse_stock_material_id_materials")),
        sa.ForeignKeyConstraint(["warehouse_id"], ["project_warehouses.id"], name=op.f("fk_warehouse_stock_warehouse_id_project_warehouses")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_warehouse_stock")),
        sa.UniqueConstraint("warehouse_id", "expected_item_id", name="uq_stock_warehouse_expected_item"),
    )
    op.create_index(op.f("ix_warehouse_stock_company_id"), "warehouse_stock", ["company_id"], unique=False)
    op.create_index(op.f("ix_warehouse_stock_expected_item_id"), "warehouse_stock", ["expected_item_id"], unique=False)
    op.create_index(op.f("ix_warehouse_stock_material_id"), "warehouse_stock", ["material_id"], unique=False)
    op.create_index(op.f("ix_warehouse_stock_warehouse_id"), "warehouse_stock", ["warehouse_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_warehouse_stock_warehouse_id"), table_name="warehouse_stock")
    op.drop_index(op.f("ix_warehouse_stock_material_id"), table_name="warehouse_stock")
    op.drop_index(op.f("ix_warehouse_stock_expected_item_id"), table_name="warehouse_stock")
    op.drop_index(op.f("ix_warehouse_stock_company_id"), table_name="warehouse_stock")
    op.drop_table("warehouse_stock")

    op.drop_index(op.f("ix_material_reception_items_reception_id"), table_name="material_reception_items")
    op.drop_index(op.f("ix_material_reception_items_material_id"), table_name="material_reception_items")
    op.drop_index(op.f("ix_material_reception_items_expected_item_id"), table_name="material_reception_items")
    op.drop_table("material_reception_items")

    op.drop_index(op.f("ix_material_receptions_warehouse_id"), table_name="material_receptions")
    op.drop_index(op.f("ix_material_receptions_project_id"), table_name="material_receptions")
    op.drop_index(op.f("ix_material_receptions_expected_list_id"), table_name="material_receptions")
    op.drop_index(op.f("ix_material_receptions_company_id"), table_name="material_receptions")
    op.drop_table("material_receptions")

    op.drop_index(op.f("ix_expected_material_items_material_id"), table_name="expected_material_items")
    op.drop_index(op.f("ix_expected_material_items_expected_list_id"), table_name="expected_material_items")
    op.drop_index(op.f("ix_expected_material_items_company_id"), table_name="expected_material_items")
    op.drop_table("expected_material_items")

    op.drop_index(op.f("ix_expected_material_lists_warehouse_id"), table_name="expected_material_lists")
    op.drop_index(op.f("ix_expected_material_lists_project_id"), table_name="expected_material_lists")
    op.drop_index(op.f("ix_expected_material_lists_company_id"), table_name="expected_material_lists")
    op.drop_table("expected_material_lists")

    op.drop_index(op.f("ix_project_warehouses_project_id"), table_name="project_warehouses")
    op.drop_index(op.f("ix_project_warehouses_company_id"), table_name="project_warehouses")
    op.drop_table("project_warehouses")
