"""supplier quote uploads

Revision ID: 0023_supplier_quote_uploads
Revises: 0022_supplier_agreements
Create Date: 2026-06-12 15:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0023_supplier_quote_uploads"
down_revision = "0022_supplier_agreements"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("supplier_rfq_suppliers", sa.Column("portal_token_hash", sa.String(length=128), nullable=True))
    op.add_column(
        "supplier_rfq_suppliers",
        sa.Column("portal_token_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "supplier_rfq_suppliers",
        sa.Column("portal_last_accessed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_supplier_rfq_suppliers_portal_token_hash", "supplier_rfq_suppliers", ["portal_token_hash"], unique=True)

    op.create_table(
        "supplier_quote_uploads",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("rfq_id", sa.Integer(), nullable=False),
        sa.Column("rfq_supplier_id", sa.Integer(), nullable=False),
        sa.Column("supplier_id", sa.Integer(), nullable=False),
        sa.Column("quote_number", sa.String(length=120), nullable=True),
        sa.Column("original_file_name", sa.String(length=255), nullable=False),
        sa.Column("stored_file_name", sa.String(length=255), nullable=False),
        sa.Column("stored_file_path", sa.String(length=500), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=True),
        sa.Column("file_extension", sa.String(length=16), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("file_sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("security_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["rfq_id"], ["supplier_rfqs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rfq_supplier_id"], ["supplier_rfq_suppliers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_supplier_quote_uploads_company_id", "supplier_quote_uploads", ["company_id"])
    op.create_index("ix_supplier_quote_uploads_file_sha256", "supplier_quote_uploads", ["file_sha256"])
    op.create_index("ix_supplier_quote_uploads_rfq_id", "supplier_quote_uploads", ["rfq_id"])
    op.create_index("ix_supplier_quote_uploads_rfq_supplier_id", "supplier_quote_uploads", ["rfq_supplier_id"])
    op.create_index("ix_supplier_quote_uploads_status", "supplier_quote_uploads", ["status"])
    op.create_index("ix_supplier_quote_uploads_supplier_id", "supplier_quote_uploads", ["supplier_id"])


def downgrade() -> None:
    op.drop_index("ix_supplier_quote_uploads_supplier_id", table_name="supplier_quote_uploads")
    op.drop_index("ix_supplier_quote_uploads_status", table_name="supplier_quote_uploads")
    op.drop_index("ix_supplier_quote_uploads_rfq_supplier_id", table_name="supplier_quote_uploads")
    op.drop_index("ix_supplier_quote_uploads_rfq_id", table_name="supplier_quote_uploads")
    op.drop_index("ix_supplier_quote_uploads_file_sha256", table_name="supplier_quote_uploads")
    op.drop_index("ix_supplier_quote_uploads_company_id", table_name="supplier_quote_uploads")
    op.drop_table("supplier_quote_uploads")
    op.drop_index("ix_supplier_rfq_suppliers_portal_token_hash", table_name="supplier_rfq_suppliers")
    op.drop_column("supplier_rfq_suppliers", "portal_last_accessed_at")
    op.drop_column("supplier_rfq_suppliers", "portal_token_expires_at")
    op.drop_column("supplier_rfq_suppliers", "portal_token_hash")
