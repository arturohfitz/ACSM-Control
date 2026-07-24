"""supplier quote structured drafts

Revision ID: 0041_supplier_quote_drafts
Revises: 0040_executive_dashboard
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0041_supplier_quote_drafts"
down_revision: str | None = "0040_executive_dashboard"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "supplier_quotes",
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="MXN"),
    )
    op.add_column(
        "supplier_quotes",
        sa.Column("discount", sa.Numeric(precision=14, scale=2), nullable=False, server_default="0"),
    )
    op.add_column(
        "supplier_quotes",
        sa.Column("shipping_cost", sa.Numeric(precision=14, scale=2), nullable=False, server_default="0"),
    )
    op.add_column(
        "supplier_quotes",
        sa.Column("tax_amount", sa.Numeric(precision=14, scale=2), nullable=False, server_default="0"),
    )
    op.add_column(
        "supplier_quotes",
        sa.Column("total", sa.Numeric(precision=14, scale=2), nullable=False, server_default="0"),
    )
    op.execute("UPDATE supplier_quotes SET total = subtotal")

    op.create_table(
        "supplier_quote_drafts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("rfq_id", sa.Integer(), nullable=False),
        sa.Column("rfq_supplier_id", sa.Integer(), nullable=False),
        sa.Column("supplier_id", sa.Integer(), nullable=False),
        sa.Column("upload_id", sa.Integer(), nullable=True),
        sa.Column("supplier_quote_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="review_required"),
        sa.Column("source_type", sa.String(length=40), nullable=False, server_default="portal"),
        sa.Column("parser_version", sa.String(length=40), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=False, server_default="1"),
        sa.Column("quote_number", sa.String(length=80), nullable=True),
        sa.Column("received_at", sa.Date(), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="MXN"),
        sa.Column("delivery_days", sa.Integer(), nullable=True),
        sa.Column("payment_terms_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("subtotal", sa.Numeric(precision=14, scale=2), nullable=False, server_default="0"),
        sa.Column("discount", sa.Numeric(precision=14, scale=2), nullable=False, server_default="0"),
        sa.Column("shipping_cost", sa.Numeric(precision=14, scale=2), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(precision=14, scale=2), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(precision=14, scale=2), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("validation_errors", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("confirmed_by", sa.Integer(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["rfq_id"], ["supplier_rfqs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rfq_supplier_id"], ["supplier_rfq_suppliers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"]),
        sa.ForeignKeyConstraint(["upload_id"], ["supplier_quote_uploads.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["supplier_quote_id"], ["supplier_quotes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["confirmed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("upload_id", name="uq_supplier_quote_drafts_upload"),
        sa.UniqueConstraint("supplier_quote_id", name="uq_supplier_quote_drafts_quote"),
    )
    for column in (
        "company_id",
        "rfq_id",
        "rfq_supplier_id",
        "supplier_id",
        "upload_id",
        "supplier_quote_id",
        "status",
        "confirmed_by",
    ):
        op.create_index(f"ix_supplier_quote_drafts_{column}", "supplier_quote_drafts", [column])

    op.create_table(
        "supplier_quote_draft_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("draft_id", sa.Integer(), nullable=False),
        sa.Column("rfq_item_id", sa.Integer(), nullable=False),
        sa.Column("material_id", sa.Integer(), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("unit", sa.String(length=40), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column("line_total", sa.Numeric(precision=14, scale=2), nullable=False, server_default="0"),
        sa.Column("delivery_days", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=False, server_default="1"),
        sa.Column("match_method", sa.String(length=40), nullable=False, server_default="rfq_item_id"),
        sa.ForeignKeyConstraint(["draft_id"], ["supplier_quote_drafts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rfq_item_id"], ["supplier_rfq_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "draft_id",
            "rfq_item_id",
            name="uq_supplier_quote_draft_items_rfq_item",
        ),
    )
    for column in ("draft_id", "rfq_item_id", "material_id"):
        op.create_index(
            f"ix_supplier_quote_draft_items_{column}",
            "supplier_quote_draft_items",
            [column],
        )


def downgrade() -> None:
    op.drop_table("supplier_quote_draft_items")
    op.drop_table("supplier_quote_drafts")
    op.drop_column("supplier_quotes", "total")
    op.drop_column("supplier_quotes", "tax_amount")
    op.drop_column("supplier_quotes", "shipping_cost")
    op.drop_column("supplier_quotes", "discount")
    op.drop_column("supplier_quotes", "currency")
