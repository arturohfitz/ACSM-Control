"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "clients",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("legal_name", sa.String(length=255), nullable=True),
        sa.Column("tax_id", sa.String(length=80), nullable=True),
        sa.Column("contact_name", sa.String(length=200), nullable=True),
        sa.Column("contact_phone", sa.String(length=80), nullable=True),
        sa.Column("contact_email", sa.String(length=255), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_clients")),
    )
    op.create_table(
        "house_models",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("construction_m2", sa.Numeric(12, 2), nullable=False),
        sa.Column("levels", sa.Integer(), nullable=True),
        sa.Column("bedrooms", sa.Integer(), nullable=True),
        sa.Column("bathrooms", sa.Numeric(5, 2), nullable=True),
        sa.Column("base_notes", sa.Text(), nullable=True),
        *timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_house_models")),
    )
    op.create_table(
        "labor_rates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("unit", sa.String(length=40), nullable=False),
        sa.Column("unit_cost", sa.Numeric(14, 4), nullable=False),
        sa.Column("performance_per_day", sa.Numeric(14, 4), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_labor_rates")),
    )
    op.create_table(
        "materials",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("unit", sa.String(length=40), nullable=False),
        sa.Column("current_unit_price", sa.Numeric(14, 4), nullable=False),
        sa.Column("supplier_name", sa.String(length=200), nullable=True),
        sa.Column("last_price_update", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_materials")),
    )
    op.create_table(
        "permissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("module", sa.String(length=80), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_permissions")),
        sa.UniqueConstraint("module", "action", name="uq_permissions_module_action"),
    )
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_system_role", sa.Boolean(), nullable=False),
        *timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_roles")),
        sa.UniqueConstraint("name", name=op.f("uq_roles_name")),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_master_admin", sa.Boolean(), nullable=False),
        *timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_table(
        "construction_concepts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("unit", sa.String(length=40), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("default_waste_percent", sa.Numeric(8, 4), nullable=False),
        sa.Column("default_indirect_percent", sa.Numeric(8, 4), nullable=False),
        *timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_construction_concepts")),
        sa.UniqueConstraint("code", name=op.f("uq_construction_concepts_code")),
    )
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("estimated_end_date", sa.Date(), nullable=True),
        sa.Column("approved_at", sa.Date(), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], name=op.f("fk_projects_client_id_clients")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_projects")),
    )
    op.create_index(op.f("ix_projects_client_id"), "projects", ["client_id"], unique=False)
    op.create_table(
        "role_permissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("permission_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"], ondelete="CASCADE", name=op.f("fk_role_permissions_permission_id_permissions")),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE", name=op.f("fk_role_permissions_role_id_roles")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_role_permissions")),
        sa.UniqueConstraint("role_id", "permission_id", name="uq_role_permissions_pair"),
    )
    op.create_table(
        "user_roles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE", name=op.f("fk_user_roles_role_id_roles")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE", name=op.f("fk_user_roles_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_roles")),
        sa.UniqueConstraint("user_id", "role_id", name="uq_user_roles_pair"),
    )
    op.create_table(
        "concept_labor",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("construction_concept_id", sa.Integer(), nullable=False),
        sa.Column("labor_rate_id", sa.Integer(), nullable=False),
        sa.Column("quantity_per_unit", sa.Numeric(14, 4), nullable=False),
        sa.ForeignKeyConstraint(["construction_concept_id"], ["construction_concepts.id"], name=op.f("fk_concept_labor_construction_concept_id_construction_concepts")),
        sa.ForeignKeyConstraint(["labor_rate_id"], ["labor_rates.id"], name=op.f("fk_concept_labor_labor_rate_id_labor_rates")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_concept_labor")),
        sa.UniqueConstraint("construction_concept_id", "labor_rate_id", name="uq_concept_labor_pair"),
    )
    op.create_index(op.f("ix_concept_labor_construction_concept_id"), "concept_labor", ["construction_concept_id"], unique=False)
    op.create_index(op.f("ix_concept_labor_labor_rate_id"), "concept_labor", ["labor_rate_id"], unique=False)
    op.create_table(
        "concept_materials",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("construction_concept_id", sa.Integer(), nullable=False),
        sa.Column("material_id", sa.Integer(), nullable=False),
        sa.Column("quantity_per_unit", sa.Numeric(14, 4), nullable=False),
        sa.ForeignKeyConstraint(["construction_concept_id"], ["construction_concepts.id"], name=op.f("fk_concept_materials_construction_concept_id_construction_concepts")),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"], name=op.f("fk_concept_materials_material_id_materials")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_concept_materials")),
        sa.UniqueConstraint("construction_concept_id", "material_id", name="uq_concept_material_pair"),
    )
    op.create_index(op.f("ix_concept_materials_construction_concept_id"), "concept_materials", ["construction_concept_id"], unique=False)
    op.create_index(op.f("ix_concept_materials_material_id"), "concept_materials", ["material_id"], unique=False)
    op.create_table(
        "house_model_concepts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("house_model_id", sa.Integer(), nullable=False),
        sa.Column("construction_concept_id", sa.Integer(), nullable=False),
        sa.Column("quantity_formula_type", sa.String(length=40), nullable=False),
        sa.Column("quantity_value", sa.Numeric(14, 4), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["construction_concept_id"], ["construction_concepts.id"], name=op.f("fk_house_model_concepts_construction_concept_id_construction_concepts")),
        sa.ForeignKeyConstraint(["house_model_id"], ["house_models.id"], name=op.f("fk_house_model_concepts_house_model_id_house_models")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_house_model_concepts")),
        sa.UniqueConstraint("house_model_id", "construction_concept_id", name="uq_house_model_concept_pair"),
    )
    op.create_index(op.f("ix_house_model_concepts_construction_concept_id"), "house_model_concepts", ["construction_concept_id"], unique=False)
    op.create_index(op.f("ix_house_model_concepts_house_model_id"), "house_model_concepts", ["house_model_id"], unique=False)
    op.create_table(
        "project_house_models",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("house_model_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=False),
        sa.Column("estimated_cost_per_unit", sa.Numeric(14, 2), nullable=True),
        sa.Column("estimated_price_per_unit", sa.Numeric(14, 2), nullable=True),
        sa.Column("total_estimated_cost", sa.Numeric(14, 2), nullable=True),
        sa.Column("total_estimated_price", sa.Numeric(14, 2), nullable=True),
        sa.ForeignKeyConstraint(["house_model_id"], ["house_models.id"], name=op.f("fk_project_house_models_house_model_id_house_models")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_project_house_models_project_id_projects")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project_house_models")),
        sa.UniqueConstraint("project_id", "house_model_id", name="uq_project_house_model_pair"),
    )
    op.create_index(op.f("ix_project_house_models_house_model_id"), "project_house_models", ["house_model_id"], unique=False)
    op.create_index(op.f("ix_project_house_models_project_id"), "project_house_models", ["project_id"], unique=False)
    op.create_table(
        "quotes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("quote_number", sa.String(length=80), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("subtotal_direct_cost", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_waste", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_indirects", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_profit", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("approved_by", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], name=op.f("fk_quotes_approved_by_users")),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_quotes_created_by_users")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_quotes_project_id_projects")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quotes")),
        sa.UniqueConstraint("quote_number", name=op.f("uq_quotes_quote_number")),
    )
    op.create_index(op.f("ix_quotes_project_id"), "quotes", ["project_id"], unique=False)
    op.create_table(
        "quote_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("quote_id", sa.Integer(), nullable=False),
        sa.Column("project_house_model_id", sa.Integer(), nullable=False),
        sa.Column("house_model_id", sa.Integer(), nullable=False),
        sa.Column("construction_concept_id", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("unit", sa.String(length=40), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 4), nullable=False),
        sa.Column("material_cost", sa.Numeric(14, 2), nullable=False),
        sa.Column("labor_cost", sa.Numeric(14, 2), nullable=False),
        sa.Column("equipment_cost", sa.Numeric(14, 2), nullable=False),
        sa.Column("waste_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("indirect_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("profit_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_cost", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_price", sa.Numeric(14, 2), nullable=False),
        sa.ForeignKeyConstraint(["construction_concept_id"], ["construction_concepts.id"], name=op.f("fk_quote_items_construction_concept_id_construction_concepts")),
        sa.ForeignKeyConstraint(["house_model_id"], ["house_models.id"], name=op.f("fk_quote_items_house_model_id_house_models")),
        sa.ForeignKeyConstraint(["project_house_model_id"], ["project_house_models.id"], name=op.f("fk_quote_items_project_house_model_id_project_house_models")),
        sa.ForeignKeyConstraint(["quote_id"], ["quotes.id"], ondelete="CASCADE", name=op.f("fk_quote_items_quote_id_quotes")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quote_items")),
    )
    op.create_index(op.f("ix_quote_items_project_house_model_id"), "quote_items", ["project_house_model_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_quote_items_project_house_model_id"), table_name="quote_items")
    op.drop_table("quote_items")
    op.drop_index(op.f("ix_quotes_project_id"), table_name="quotes")
    op.drop_table("quotes")
    op.drop_index(op.f("ix_project_house_models_project_id"), table_name="project_house_models")
    op.drop_index(op.f("ix_project_house_models_house_model_id"), table_name="project_house_models")
    op.drop_table("project_house_models")
    op.drop_index(op.f("ix_house_model_concepts_house_model_id"), table_name="house_model_concepts")
    op.drop_index(op.f("ix_house_model_concepts_construction_concept_id"), table_name="house_model_concepts")
    op.drop_table("house_model_concepts")
    op.drop_index(op.f("ix_concept_materials_material_id"), table_name="concept_materials")
    op.drop_index(op.f("ix_concept_materials_construction_concept_id"), table_name="concept_materials")
    op.drop_table("concept_materials")
    op.drop_index(op.f("ix_concept_labor_labor_rate_id"), table_name="concept_labor")
    op.drop_index(op.f("ix_concept_labor_construction_concept_id"), table_name="concept_labor")
    op.drop_table("concept_labor")
    op.drop_table("user_roles")
    op.drop_table("role_permissions")
    op.drop_index(op.f("ix_projects_client_id"), table_name="projects")
    op.drop_table("projects")
    op.drop_table("construction_concepts")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
    op.drop_table("roles")
    op.drop_table("permissions")
    op.drop_table("materials")
    op.drop_table("labor_rates")
    op.drop_table("house_models")
    op.drop_table("clients")

