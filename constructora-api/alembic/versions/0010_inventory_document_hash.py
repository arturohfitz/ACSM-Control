"""add inventory document hash

Revision ID: 0010_inventory_document_hash
Revises: 0009_inv_quick
Create Date: 2026-05-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0010_inventory_document_hash"
down_revision: Union[str, None] = "0009_inv_quick"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "expected_material_lists",
        sa.Column("source_document_hash", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_expected_material_lists_source_document_hash",
        "expected_material_lists",
        ["source_document_hash"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_expected_material_lists_source_document_hash",
        table_name="expected_material_lists",
    )
    op.drop_column("expected_material_lists", "source_document_hash")
