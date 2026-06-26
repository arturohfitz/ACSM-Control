"""partial purchase order billing

Revision ID: 0028_po_partial_billing
Revises: 0027_notification_settings
Create Date: 2026-06-25 08:25:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0028_po_partial_billing"
down_revision = "0027_notification_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "purchase_orders",
        sa.Column("billing_mode", sa.String(length=40), nullable=False, server_default="single"),
    )
    op.create_table(
        "supplier_invoice_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("supplier_invoice_id", sa.Integer(), nullable=False),
        sa.Column("purchase_order_item_id", sa.Integer(), nullable=False),
        sa.Column("material_id", sa.Integer(), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("unit", sa.String(length=40), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 4), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 4), nullable=False),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"]),
        sa.ForeignKeyConstraint(["purchase_order_item_id"], ["purchase_order_items.id"]),
        sa.ForeignKeyConstraint(["supplier_invoice_id"], ["supplier_invoices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_supplier_invoice_items_supplier_invoice_id"),
        "supplier_invoice_items",
        ["supplier_invoice_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_supplier_invoice_items_purchase_order_item_id"),
        "supplier_invoice_items",
        ["purchase_order_item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_supplier_invoice_items_material_id"),
        "supplier_invoice_items",
        ["material_id"],
        unique=False,
    )
    op.alter_column("purchase_orders", "billing_mode", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_supplier_invoice_items_material_id"), table_name="supplier_invoice_items")
    op.drop_index(
        op.f("ix_supplier_invoice_items_purchase_order_item_id"),
        table_name="supplier_invoice_items",
    )
    op.drop_index(
        op.f("ix_supplier_invoice_items_supplier_invoice_id"),
        table_name="supplier_invoice_items",
    )
    op.drop_table("supplier_invoice_items")
    op.drop_column("purchase_orders", "billing_mode")
