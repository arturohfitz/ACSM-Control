"""supplier invoice portal

Revision ID: 0044_supplier_invoice_portal
Revises: 0043_purchasing_audit
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0044_supplier_invoice_portal"
down_revision: str | None = "0043_purchasing_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("purchase_orders", sa.Column("invoice_portal_token_hash", sa.String(64)))
    op.add_column(
        "purchase_orders",
        sa.Column("invoice_portal_token_expires_at", sa.DateTime(timezone=True)),
    )
    op.add_column(
        "purchase_orders",
        sa.Column("invoice_portal_last_accessed_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_purchase_orders_invoice_portal_token_hash",
        "purchase_orders",
        ["invoice_portal_token_hash"],
        unique=True,
    )

    op.create_table(
        "supplier_invoice_submissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column(
            "purchase_order_id",
            sa.Integer(),
            sa.ForeignKey("purchase_orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("invoice_number", sa.String(100)),
        sa.Column("invoice_date", sa.Date()),
        sa.Column("currency", sa.String(10), nullable=False, server_default="MXN"),
        sa.Column("subtotal", sa.Numeric(14, 2)),
        sa.Column("total", sa.Numeric(14, 2)),
        sa.Column("fiscal_uuid", sa.String(40)),
        sa.Column("notes", sa.Text()),
        sa.Column("status", sa.String(40), nullable=False, server_default="review_required"),
        sa.Column("validation_message", sa.Text()),
        sa.Column("parsed_data", sa.JSON()),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column(
            "supplier_invoice_id",
            sa.Integer(),
            sa.ForeignKey("supplier_invoices.id"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    for name in (
        "company_id",
        "purchase_order_id",
        "supplier_id",
        "fiscal_uuid",
        "status",
        "reviewed_by",
        "supplier_invoice_id",
    ):
        op.create_index(
            f"ix_supplier_invoice_submissions_{name}",
            "supplier_invoice_submissions",
            [name],
            unique=name == "supplier_invoice_id",
        )

    op.create_table(
        "supplier_invoice_submission_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "submission_id",
            sa.Integer(),
            sa.ForeignKey("supplier_invoice_submissions.id", ondelete="CASCADE"),
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
        sa.Column("validation_status", sa.String(40), nullable=False, server_default="uploaded"),
        sa.Column("validation_message", sa.Text()),
        sa.Column("parsed_data", sa.JSON()),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    for name in ("submission_id", "document_type", "sha256"):
        op.create_index(
            f"ix_supplier_invoice_submission_documents_{name}",
            "supplier_invoice_submission_documents",
            [name],
        )


def downgrade() -> None:
    for name in ("submission_id", "document_type", "sha256"):
        op.drop_index(
            f"ix_supplier_invoice_submission_documents_{name}",
            table_name="supplier_invoice_submission_documents",
        )
    op.drop_table("supplier_invoice_submission_documents")
    for name in (
        "company_id",
        "purchase_order_id",
        "supplier_id",
        "fiscal_uuid",
        "status",
        "reviewed_by",
        "supplier_invoice_id",
    ):
        op.drop_index(
            f"ix_supplier_invoice_submissions_{name}",
            table_name="supplier_invoice_submissions",
        )
    op.drop_table("supplier_invoice_submissions")
    op.drop_index("ix_purchase_orders_invoice_portal_token_hash", table_name="purchase_orders")
    op.drop_column("purchase_orders", "invoice_portal_last_accessed_at")
    op.drop_column("purchase_orders", "invoice_portal_token_expires_at")
    op.drop_column("purchase_orders", "invoice_portal_token_hash")
