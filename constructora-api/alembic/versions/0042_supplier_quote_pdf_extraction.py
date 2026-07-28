"""supplier quote PDF extraction evidence

Revision ID: 0042_quote_pdf_extraction
Revises: 0041_supplier_quote_drafts
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0042_quote_pdf_extraction"
down_revision: str | None = "0041_supplier_quote_drafts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    columns = (
        sa.Column("detected_supplier_name", sa.String(length=255), nullable=True),
        sa.Column("detected_supplier_tax_id", sa.String(length=80), nullable=True),
        sa.Column("detected_supplier_email", sa.String(length=255), nullable=True),
        sa.Column(
            "supplier_match_status",
            sa.String(length=40),
            nullable=False,
            server_default="not_detected",
        ),
        sa.Column(
            "supplier_match_confidence",
            sa.Numeric(precision=5, scale=4),
            nullable=False,
            server_default="0",
        ),
        sa.Column("detected_rfq_number", sa.String(length=80), nullable=True),
        sa.Column("document_subtotal", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("document_tax_amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("document_total", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column(
            "extraction_metadata",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
    )
    for column in columns:
        op.add_column("supplier_quote_drafts", column)


def downgrade() -> None:
    for column in (
        "extraction_metadata",
        "document_total",
        "document_tax_amount",
        "document_subtotal",
        "detected_rfq_number",
        "supplier_match_confidence",
        "supplier_match_status",
        "detected_supplier_email",
        "detected_supplier_tax_id",
        "detected_supplier_name",
    ):
        op.drop_column("supplier_quote_drafts", column)
