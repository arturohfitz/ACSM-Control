"""add purchasing flow

Revision ID: 0011_purchasing_flow
Revises: 0010_inventory_document_hash
Create Date: 2026-05-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0011_purchasing_flow"
down_revision: Union[str, None] = "0010_inventory_document_hash"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "suppliers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("legal_name", sa.String(length=255), nullable=True),
        sa.Column("tax_id", sa.String(length=80), nullable=True),
        sa.Column("contact_name", sa.String(length=200), nullable=True),
        sa.Column("contact_email", sa.String(length=255), nullable=True),
        sa.Column("contact_phone", sa.String(length=80), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("payment_terms_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("average_delivery_days", sa.Integer(), nullable=True),
        sa.Column("material_categories", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="active"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "name", name="uq_suppliers_company_name"),
    )
    op.create_index("ix_suppliers_company_id", "suppliers", ["company_id"])

    op.create_table(
        "supplier_rfqs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("warehouse_id", sa.Integer(), sa.ForeignKey("project_warehouses.id"), nullable=True),
        sa.Column("rfq_number", sa.String(length=80), nullable=False, unique=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="draft"),
        sa.Column("required_by", sa.Date(), nullable=True),
        sa.Column("response_deadline", sa.Date(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_supplier_rfqs_company_id", "supplier_rfqs", ["company_id"])
    op.create_index("ix_supplier_rfqs_project_id", "supplier_rfqs", ["project_id"])
    op.create_index("ix_supplier_rfqs_warehouse_id", "supplier_rfqs", ["warehouse_id"])

    op.create_table(
        "supplier_rfq_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("rfq_id", sa.Integer(), sa.ForeignKey("supplier_rfqs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id"), nullable=True),
        sa.Column("source_code", sa.String(length=80), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("unit", sa.String(length=40), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 4), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_supplier_rfq_items_rfq_id", "supplier_rfq_items", ["rfq_id"])
    op.create_index("ix_supplier_rfq_items_material_id", "supplier_rfq_items", ["material_id"])

    op.create_table(
        "supplier_rfq_suppliers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("rfq_id", sa.Integer(), sa.ForeignKey("supplier_rfqs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="invited"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("rfq_id", "supplier_id", name="uq_supplier_rfq_supplier_pair"),
    )
    op.create_index("ix_supplier_rfq_suppliers_rfq_id", "supplier_rfq_suppliers", ["rfq_id"])
    op.create_index("ix_supplier_rfq_suppliers_supplier_id", "supplier_rfq_suppliers", ["supplier_id"])

    op.create_table(
        "supplier_quotes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("rfq_id", sa.Integer(), sa.ForeignKey("supplier_rfqs.id"), nullable=False),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("quote_number", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="received"),
        sa.Column("received_at", sa.Date(), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("delivery_days", sa.Integer(), nullable=True),
        sa.Column("payment_terms_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("attachment_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("rfq_id", "supplier_id", name="uq_supplier_quotes_rfq_supplier"),
    )
    op.create_index("ix_supplier_quotes_company_id", "supplier_quotes", ["company_id"])
    op.create_index("ix_supplier_quotes_rfq_id", "supplier_quotes", ["rfq_id"])
    op.create_index("ix_supplier_quotes_supplier_id", "supplier_quotes", ["supplier_id"])

    op.create_table(
        "supplier_quote_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("supplier_quote_id", sa.Integer(), sa.ForeignKey("supplier_quotes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rfq_item_id", sa.Integer(), sa.ForeignKey("supplier_rfq_items.id"), nullable=False),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id"), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("unit", sa.String(length=40), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 4), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 4), nullable=False),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("delivery_days", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_supplier_quote_items_supplier_quote_id", "supplier_quote_items", ["supplier_quote_id"])
    op.create_index("ix_supplier_quote_items_material_id", "supplier_quote_items", ["material_id"])

    op.create_table(
        "purchase_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("warehouse_id", sa.Integer(), sa.ForeignKey("project_warehouses.id"), nullable=True),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("supplier_quote_id", sa.Integer(), sa.ForeignKey("supplier_quotes.id"), nullable=True, unique=True),
        sa.Column("po_number", sa.String(length=80), nullable=False, unique=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="issued"),
        sa.Column("issued_at", sa.Date(), nullable=False),
        sa.Column("expected_delivery_date", sa.Date(), nullable=True),
        sa.Column("payment_terms_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("approved_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_purchase_orders_company_id", "purchase_orders", ["company_id"])
    op.create_index("ix_purchase_orders_project_id", "purchase_orders", ["project_id"])
    op.create_index("ix_purchase_orders_warehouse_id", "purchase_orders", ["warehouse_id"])
    op.create_index("ix_purchase_orders_supplier_id", "purchase_orders", ["supplier_id"])
    op.create_index("ix_purchase_orders_supplier_quote_id", "purchase_orders", ["supplier_quote_id"])

    op.create_table(
        "purchase_order_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("purchase_order_id", sa.Integer(), sa.ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rfq_item_id", sa.Integer(), sa.ForeignKey("supplier_rfq_items.id"), nullable=True),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id"), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("unit", sa.String(length=40), nullable=False),
        sa.Column("quantity_ordered", sa.Numeric(14, 4), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 4), nullable=False),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("received_quantity", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="pending"),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_purchase_order_items_purchase_order_id", "purchase_order_items", ["purchase_order_id"])
    op.create_index("ix_purchase_order_items_rfq_item_id", "purchase_order_items", ["rfq_item_id"])
    op.create_index("ix_purchase_order_items_material_id", "purchase_order_items", ["material_id"])

    op.add_column("expected_material_lists", sa.Column("purchase_order_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_expected_material_lists_purchase_order_id",
        "expected_material_lists",
        "purchase_orders",
        ["purchase_order_id"],
        ["id"],
    )
    op.create_index("ix_expected_material_lists_purchase_order_id", "expected_material_lists", ["purchase_order_id"])
    op.add_column("expected_material_items", sa.Column("purchase_order_item_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_expected_material_items_purchase_order_item_id",
        "expected_material_items",
        "purchase_order_items",
        ["purchase_order_item_id"],
        ["id"],
    )
    op.create_index("ix_expected_material_items_purchase_order_item_id", "expected_material_items", ["purchase_order_item_id"])

    op.create_table(
        "supplier_invoices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("purchase_order_id", sa.Integer(), sa.ForeignKey("purchase_orders.id"), nullable=False),
        sa.Column("invoice_number", sa.String(length=100), nullable=False),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=True),
        sa.Column("total", sa.Numeric(14, 2), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="received"),
        sa.Column("document_name", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("validated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_supplier_invoices_company_id", "supplier_invoices", ["company_id"])
    op.create_index("ix_supplier_invoices_supplier_id", "supplier_invoices", ["supplier_id"])
    op.create_index("ix_supplier_invoices_purchase_order_id", "supplier_invoices", ["purchase_order_id"])

    op.create_table(
        "supplier_payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("supplier_invoice_id", sa.Integer(), sa.ForeignKey("supplier_invoices.id"), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("scheduled_date", sa.Date(), nullable=True),
        sa.Column("paid_at", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="scheduled"),
        sa.Column("reference", sa.String(length=160), nullable=True),
        sa.Column("proof_document_name", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("approved_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_supplier_payments_company_id", "supplier_payments", ["company_id"])
    op.create_index("ix_supplier_payments_supplier_invoice_id", "supplier_payments", ["supplier_invoice_id"])


def downgrade() -> None:
    op.drop_index("ix_supplier_payments_supplier_invoice_id", table_name="supplier_payments")
    op.drop_index("ix_supplier_payments_company_id", table_name="supplier_payments")
    op.drop_table("supplier_payments")
    op.drop_index("ix_supplier_invoices_purchase_order_id", table_name="supplier_invoices")
    op.drop_index("ix_supplier_invoices_supplier_id", table_name="supplier_invoices")
    op.drop_index("ix_supplier_invoices_company_id", table_name="supplier_invoices")
    op.drop_table("supplier_invoices")
    op.drop_index("ix_expected_material_items_purchase_order_item_id", table_name="expected_material_items")
    op.drop_constraint("fk_expected_material_items_purchase_order_item_id", "expected_material_items", type_="foreignkey")
    op.drop_column("expected_material_items", "purchase_order_item_id")
    op.drop_index("ix_expected_material_lists_purchase_order_id", table_name="expected_material_lists")
    op.drop_constraint("fk_expected_material_lists_purchase_order_id", "expected_material_lists", type_="foreignkey")
    op.drop_column("expected_material_lists", "purchase_order_id")
    op.drop_index("ix_purchase_order_items_material_id", table_name="purchase_order_items")
    op.drop_index("ix_purchase_order_items_rfq_item_id", table_name="purchase_order_items")
    op.drop_index("ix_purchase_order_items_purchase_order_id", table_name="purchase_order_items")
    op.drop_table("purchase_order_items")
    op.drop_index("ix_purchase_orders_supplier_quote_id", table_name="purchase_orders")
    op.drop_index("ix_purchase_orders_supplier_id", table_name="purchase_orders")
    op.drop_index("ix_purchase_orders_warehouse_id", table_name="purchase_orders")
    op.drop_index("ix_purchase_orders_project_id", table_name="purchase_orders")
    op.drop_index("ix_purchase_orders_company_id", table_name="purchase_orders")
    op.drop_table("purchase_orders")
    op.drop_index("ix_supplier_quote_items_material_id", table_name="supplier_quote_items")
    op.drop_index("ix_supplier_quote_items_supplier_quote_id", table_name="supplier_quote_items")
    op.drop_table("supplier_quote_items")
    op.drop_index("ix_supplier_quotes_supplier_id", table_name="supplier_quotes")
    op.drop_index("ix_supplier_quotes_rfq_id", table_name="supplier_quotes")
    op.drop_index("ix_supplier_quotes_company_id", table_name="supplier_quotes")
    op.drop_table("supplier_quotes")
    op.drop_index("ix_supplier_rfq_suppliers_supplier_id", table_name="supplier_rfq_suppliers")
    op.drop_index("ix_supplier_rfq_suppliers_rfq_id", table_name="supplier_rfq_suppliers")
    op.drop_table("supplier_rfq_suppliers")
    op.drop_index("ix_supplier_rfq_items_material_id", table_name="supplier_rfq_items")
    op.drop_index("ix_supplier_rfq_items_rfq_id", table_name="supplier_rfq_items")
    op.drop_table("supplier_rfq_items")
    op.drop_index("ix_supplier_rfqs_warehouse_id", table_name="supplier_rfqs")
    op.drop_index("ix_supplier_rfqs_project_id", table_name="supplier_rfqs")
    op.drop_index("ix_supplier_rfqs_company_id", table_name="supplier_rfqs")
    op.drop_table("supplier_rfqs")
    op.drop_index("ix_suppliers_company_id", table_name="suppliers")
    op.drop_table("suppliers")
