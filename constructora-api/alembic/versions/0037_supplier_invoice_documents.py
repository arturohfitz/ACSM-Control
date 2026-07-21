"""supplier invoice documents and fiscal controls

Revision ID: 0037_invoice_documents
Revises: 0036_inventory_operations
Create Date: 2026-07-20 18:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0037_invoice_documents"
down_revision: str | None = "0036_inventory_operations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("supplier_invoices", sa.Column("discount", sa.Numeric(14, 2), nullable=True))
    op.add_column("supplier_invoices", sa.Column("transferred_taxes", sa.Numeric(14, 2), nullable=True))
    op.add_column("supplier_invoices", sa.Column("withheld_taxes", sa.Numeric(14, 2), nullable=True))
    op.add_column(
        "supplier_invoices",
        sa.Column("currency", sa.String(10), server_default="MXN", nullable=False),
    )
    op.add_column("supplier_invoices", sa.Column("exchange_rate", sa.Numeric(14, 6), nullable=True))
    op.add_column("supplier_invoices", sa.Column("fiscal_uuid", sa.String(40), nullable=True))
    op.add_column("supplier_invoices", sa.Column("series", sa.String(40), nullable=True))
    op.add_column("supplier_invoices", sa.Column("issuer_tax_id", sa.String(20), nullable=True))
    op.add_column("supplier_invoices", sa.Column("receiver_tax_id", sa.String(20), nullable=True))
    op.add_column("supplier_invoices", sa.Column("payment_method", sa.String(10), nullable=True))
    op.add_column("supplier_invoices", sa.Column("payment_form", sa.String(10), nullable=True))
    op.add_column(
        "supplier_invoices",
        sa.Column("fiscal_status", sa.String(40), server_default="legacy_validated", nullable=False),
    )
    op.add_column("supplier_invoices", sa.Column("fiscal_validation_message", sa.Text(), nullable=True))
    op.create_index("ix_supplier_invoices_fiscal_uuid", "supplier_invoices", ["fiscal_uuid"])
    op.create_index("ix_supplier_invoices_issuer_tax_id", "supplier_invoices", ["issuer_tax_id"])
    op.create_index("ix_supplier_invoices_receiver_tax_id", "supplier_invoices", ["receiver_tax_id"])
    op.create_unique_constraint(
        "uq_supplier_invoices_company_fiscal_uuid",
        "supplier_invoices",
        ["company_id", "fiscal_uuid"],
    )

    op.create_table(
        "supplier_invoice_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column(
            "supplier_invoice_id",
            sa.Integer(),
            sa.ForeignKey("supplier_invoices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("document_type", sa.String(40), nullable=False),
        sa.Column("original_file_name", sa.String(255), nullable=False),
        sa.Column("stored_file_name", sa.String(255), nullable=False),
        sa.Column("storage_path", sa.String(700), nullable=False),
        sa.Column("content_type", sa.String(120), nullable=False),
        sa.Column("extension", sa.String(20), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("validation_status", sa.String(40), server_default="uploaded", nullable=False),
        sa.Column("validation_message", sa.Text(), nullable=True),
        sa.Column("parsed_data", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    for column in ("company_id", "supplier_invoice_id", "document_type", "sha256", "uploaded_by"):
        op.create_index(
            f"ix_supplier_invoice_documents_{column}",
            "supplier_invoice_documents",
            [column],
        )

    op.execute(
        """
        INSERT INTO roles (company_id, name, description, is_system_role, created_at, updated_at)
        SELECT id, 'Cuentas por pagar',
               'Revision fiscal de facturas, programacion y registro de pagos a proveedores',
               FALSE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        FROM companies
        ON CONFLICT (company_id, name) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        JOIN permissions p ON (p.module || ':' || p.action) IN (
            'projects:view', 'suppliers:view', 'purchase_orders:view',
            'supplier_invoices:view', 'supplier_invoices:upload', 'supplier_invoices:validate',
            'supplier_payments:view', 'supplier_payments:schedule', 'supplier_payments:pay',
            'notifications:view'
        )
        WHERE r.name = 'Cuentas por pagar'
        ON CONFLICT (role_id, permission_id) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        JOIN permissions p ON (p.module || ':' || p.action) IN (
            'supplier_invoices:view', 'supplier_invoices:upload'
        )
        WHERE r.name = 'Compras'
        ON CONFLICT (role_id, permission_id) DO NOTHING
        """
    )
    op.execute(
        """
        DELETE FROM role_permissions rp
        USING roles r, permissions p
        WHERE rp.role_id = r.id AND rp.permission_id = p.id
          AND r.name = 'Inventarios'
          AND (p.module || ':' || p.action) IN (
              'supplier_invoices:view', 'supplier_invoices:upload', 'supplier_invoices:validate'
          )
        """
    )


def downgrade() -> None:
    op.drop_table("supplier_invoice_documents")
    op.drop_constraint(
        "uq_supplier_invoices_company_fiscal_uuid",
        "supplier_invoices",
        type_="unique",
    )
    op.drop_index("ix_supplier_invoices_receiver_tax_id", table_name="supplier_invoices")
    op.drop_index("ix_supplier_invoices_issuer_tax_id", table_name="supplier_invoices")
    op.drop_index("ix_supplier_invoices_fiscal_uuid", table_name="supplier_invoices")
    for column in (
        "fiscal_validation_message",
        "fiscal_status",
        "payment_form",
        "payment_method",
        "receiver_tax_id",
        "issuer_tax_id",
        "series",
        "fiscal_uuid",
        "exchange_rate",
        "currency",
        "withheld_taxes",
        "transferred_taxes",
        "discount",
    ):
        op.drop_column("supplier_invoices", column)
