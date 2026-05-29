"""add quick inventory document fields

Revision ID: 0009_inv_quick
Revises: 0008_price_timestamps
Create Date: 2026-05-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0009_inv_quick"
down_revision: Union[str, None] = "0008_price_timestamps"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("expected_material_lists", sa.Column("document_number", sa.String(length=80), nullable=True))
    op.add_column("expected_material_lists", sa.Column("supplier_name", sa.String(length=200), nullable=True))
    op.add_column("expected_material_lists", sa.Column("document_date", sa.Date(), nullable=True))
    op.add_column("expected_material_lists", sa.Column("delivery_date", sa.Date(), nullable=True))
    op.add_column("expected_material_items", sa.Column("source_code", sa.String(length=80), nullable=True))
    op.add_column("expected_material_items", sa.Column("unit_price", sa.Numeric(14, 4), nullable=True))
    op.add_column("expected_material_items", sa.Column("line_total", sa.Numeric(14, 2), nullable=True))
    op.add_column("expected_material_items", sa.Column("delivery_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("expected_material_items", "delivery_date")
    op.drop_column("expected_material_items", "line_total")
    op.drop_column("expected_material_items", "unit_price")
    op.drop_column("expected_material_items", "source_code")
    op.drop_column("expected_material_lists", "delivery_date")
    op.drop_column("expected_material_lists", "document_date")
    op.drop_column("expected_material_lists", "supplier_name")
    op.drop_column("expected_material_lists", "document_number")
