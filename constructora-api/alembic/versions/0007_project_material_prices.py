"""add project material price tabulators

Revision ID: 0007_project_material_prices
Revises: 0006_require_house_model_client
Create Date: 2026-05-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0007_project_material_prices"
down_revision: Union[str, None] = "0006_require_house_model_client"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "project_material_prices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("house_model_id", sa.Integer(), nullable=True),
        sa.Column("material_id", sa.Integer(), nullable=False),
        sa.Column("unit", sa.String(length=40), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("supply_source", sa.String(length=40), nullable=False, server_default="constructor"),
        sa.Column("supplier_name", sa.String(length=200), nullable=True),
        sa.Column("include_in_quote", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("source_document_name", sa.String(length=255), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["house_model_id"], ["house_models.id"]),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_project_material_prices_company_id"),
        "project_material_prices",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_project_material_prices_house_model_id"),
        "project_material_prices",
        ["house_model_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_project_material_prices_material_id"),
        "project_material_prices",
        ["material_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_project_material_prices_project_id"),
        "project_material_prices",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "uq_project_material_prices_project_material_global",
        "project_material_prices",
        ["project_id", "material_id"],
        unique=True,
        postgresql_where=sa.text("house_model_id IS NULL"),
    )
    op.create_index(
        "uq_project_material_prices_project_model_material",
        "project_material_prices",
        ["project_id", "house_model_id", "material_id"],
        unique=True,
        postgresql_where=sa.text("house_model_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_project_material_prices_project_model_material",
        table_name="project_material_prices",
    )
    op.drop_index(
        "uq_project_material_prices_project_material_global",
        table_name="project_material_prices",
    )
    op.drop_index(op.f("ix_project_material_prices_project_id"), table_name="project_material_prices")
    op.drop_index(op.f("ix_project_material_prices_material_id"), table_name="project_material_prices")
    op.drop_index(op.f("ix_project_material_prices_house_model_id"), table_name="project_material_prices")
    op.drop_index(op.f("ix_project_material_prices_company_id"), table_name="project_material_prices")
    op.drop_table("project_material_prices")
