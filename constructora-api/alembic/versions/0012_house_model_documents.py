"""add house model documents

Revision ID: 0012_house_model_documents
Revises: 0011_purchasing_flow
Create Date: 2026-05-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0012_house_model_documents"
down_revision: Union[str, None] = "0011_purchasing_flow"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "house_model_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column(
            "house_model_id",
            sa.Integer(),
            sa.ForeignKey("house_models.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("document_type", sa.String(length=40), nullable=False),
        sa.Column("version", sa.String(length=80), nullable=True),
        sa.Column("source_code", sa.String(length=120), nullable=True),
        sa.Column("source_date", sa.Date(), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=True),
        sa.Column("file_hash", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="interpreted"),
        sa.Column("total_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "company_id",
            "house_model_id",
            "document_type",
            "file_hash",
            name="uq_house_model_document_hash",
        ),
    )
    op.create_index("ix_house_model_documents_company_id", "house_model_documents", ["company_id"])
    op.create_index("ix_house_model_documents_client_id", "house_model_documents", ["client_id"])
    op.create_index(
        "ix_house_model_documents_house_model_id", "house_model_documents", ["house_model_id"]
    )

    op.create_table(
        "house_model_material_requirements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column(
            "house_model_id",
            sa.Integer(),
            sa.ForeignKey("house_models.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey("house_model_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id"), nullable=True),
        sa.Column("source_code", sa.String(length=80), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("unit", sa.String(length=40), nullable=False),
        sa.Column("quantity_per_house", sa.Numeric(14, 6), nullable=False),
        sa.Column("unit_cost_reference", sa.Numeric(14, 4), nullable=True),
        sa.Column("total_cost_reference", sa.Numeric(14, 2), nullable=True),
        sa.Column("family", sa.String(length=120), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_house_model_material_requirements_company_id",
        "house_model_material_requirements",
        ["company_id"],
    )
    op.create_index(
        "ix_house_model_material_requirements_client_id",
        "house_model_material_requirements",
        ["client_id"],
    )
    op.create_index(
        "ix_house_model_material_requirements_house_model_id",
        "house_model_material_requirements",
        ["house_model_id"],
    )
    op.create_index(
        "ix_house_model_material_requirements_document_id",
        "house_model_material_requirements",
        ["document_id"],
    )
    op.create_index(
        "ix_house_model_material_requirements_material_id",
        "house_model_material_requirements",
        ["material_id"],
    )

    op.create_table(
        "house_model_budget_activities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column(
            "house_model_id",
            sa.Integer(),
            sa.ForeignKey("house_models.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey("house_model_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "construction_concept_id",
            sa.Integer(),
            sa.ForeignKey("construction_concepts.id"),
            nullable=True,
        ),
        sa.Column("chapter_code", sa.String(length=40), nullable=True),
        sa.Column("chapter_name", sa.String(length=200), nullable=True),
        sa.Column("source_code", sa.String(length=80), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("unit", sa.String(length=40), nullable=False),
        sa.Column("quantity_per_house", sa.Numeric(14, 6), nullable=False),
        sa.Column("unit_price_reference", sa.Numeric(14, 4), nullable=True),
        sa.Column("total_price_reference", sa.Numeric(14, 2), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_house_model_budget_activities_company_id",
        "house_model_budget_activities",
        ["company_id"],
    )
    op.create_index(
        "ix_house_model_budget_activities_client_id",
        "house_model_budget_activities",
        ["client_id"],
    )
    op.create_index(
        "ix_house_model_budget_activities_house_model_id",
        "house_model_budget_activities",
        ["house_model_id"],
    )
    op.create_index(
        "ix_house_model_budget_activities_document_id",
        "house_model_budget_activities",
        ["document_id"],
    )
    op.create_index(
        "ix_house_model_budget_activities_construction_concept_id",
        "house_model_budget_activities",
        ["construction_concept_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_house_model_budget_activities_construction_concept_id",
        table_name="house_model_budget_activities",
    )
    op.drop_index("ix_house_model_budget_activities_document_id", table_name="house_model_budget_activities")
    op.drop_index(
        "ix_house_model_budget_activities_house_model_id",
        table_name="house_model_budget_activities",
    )
    op.drop_index("ix_house_model_budget_activities_client_id", table_name="house_model_budget_activities")
    op.drop_index("ix_house_model_budget_activities_company_id", table_name="house_model_budget_activities")
    op.drop_table("house_model_budget_activities")

    op.drop_index(
        "ix_house_model_material_requirements_material_id",
        table_name="house_model_material_requirements",
    )
    op.drop_index(
        "ix_house_model_material_requirements_document_id",
        table_name="house_model_material_requirements",
    )
    op.drop_index(
        "ix_house_model_material_requirements_house_model_id",
        table_name="house_model_material_requirements",
    )
    op.drop_index(
        "ix_house_model_material_requirements_client_id",
        table_name="house_model_material_requirements",
    )
    op.drop_index(
        "ix_house_model_material_requirements_company_id",
        table_name="house_model_material_requirements",
    )
    op.drop_table("house_model_material_requirements")

    op.drop_index("ix_house_model_documents_house_model_id", table_name="house_model_documents")
    op.drop_index("ix_house_model_documents_client_id", table_name="house_model_documents")
    op.drop_index("ix_house_model_documents_company_id", table_name="house_model_documents")
    op.drop_table("house_model_documents")
