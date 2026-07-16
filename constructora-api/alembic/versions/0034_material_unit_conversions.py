"""material unit conversions

Revision ID: 0034_material_unit_conversions
Revises: 0033_material_supplier_relation
Create Date: 2026-07-15 18:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "0034_material_unit_conversions"
down_revision: str | None = "0033_material_supplier_relation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "material_unit_conversions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("material_id", sa.Integer(), nullable=False),
        sa.Column("from_unit", sa.String(length=40), nullable=False),
        sa.Column("to_unit", sa.String(length=40), nullable=False),
        sa.Column("factor_to_base", sa.Numeric(18, 8), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "material_id",
            "from_unit",
            "to_unit",
            name="uq_material_unit_conversion_pair",
        ),
    )
    op.create_index(
        op.f("ix_material_unit_conversions_company_id"),
        "material_unit_conversions",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_material_unit_conversions_material_id"),
        "material_unit_conversions",
        ["material_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_material_unit_conversions_material_id"), table_name="material_unit_conversions")
    op.drop_index(op.f("ix_material_unit_conversions_company_id"), table_name="material_unit_conversions")
    op.drop_table("material_unit_conversions")
