"""material requisitions

Revision ID: 0024_material_requisitions
Revises: 0023_supplier_quote_uploads
Create Date: 2026-06-15 07:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0024_material_requisitions"
down_revision = "0023_supplier_quote_uploads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "material_requisitions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("house_model_id", sa.Integer(), nullable=False),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("converted_rfq_id", sa.Integer(), nullable=True),
        sa.Column("requisition_number", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("priority", sa.String(length=40), nullable=False),
        sa.Column("required_date", sa.Date(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["converted_rfq_id"], ["supplier_rfqs.id"]),
        sa.ForeignKeyConstraint(["house_model_id"], ["house_models.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "requisition_number", name="uq_material_requisition_number"),
    )
    op.create_index("ix_material_requisitions_client_id", "material_requisitions", ["client_id"])
    op.create_index("ix_material_requisitions_company_id", "material_requisitions", ["company_id"])
    op.create_index("ix_material_requisitions_converted_rfq_id", "material_requisitions", ["converted_rfq_id"])
    op.create_index("ix_material_requisitions_house_model_id", "material_requisitions", ["house_model_id"])
    op.create_index("ix_material_requisitions_project_id", "material_requisitions", ["project_id"])
    op.create_index("ix_material_requisitions_requested_by_user_id", "material_requisitions", ["requested_by_user_id"])
    op.create_index("ix_material_requisitions_reviewed_by_user_id", "material_requisitions", ["reviewed_by_user_id"])
    op.create_index("ix_material_requisitions_status", "material_requisitions", ["status"])

    op.create_table(
        "material_requisition_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("requisition_id", sa.Integer(), nullable=False),
        sa.Column("house_model_material_requirement_id", sa.Integer(), nullable=True),
        sa.Column("material_id", sa.Integer(), nullable=True),
        sa.Column("supplier_rfq_item_id", sa.Integer(), nullable=True),
        sa.Column("source_code", sa.String(length=80), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("unit", sa.String(length=40), nullable=False),
        sa.Column("requested_quantity", sa.Numeric(14, 4), nullable=False),
        sa.Column("approved_quantity", sa.Numeric(14, 4), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["house_model_material_requirement_id"],
            ["house_model_material_requirements.id"],
        ),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"]),
        sa.ForeignKeyConstraint(["requisition_id"], ["material_requisitions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["supplier_rfq_item_id"], ["supplier_rfq_items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_mr_items_requirement_id",
        "material_requisition_items",
        ["house_model_material_requirement_id"],
    )
    op.create_index("ix_material_requisition_items_material_id", "material_requisition_items", ["material_id"])
    op.create_index("ix_material_requisition_items_requisition_id", "material_requisition_items", ["requisition_id"])
    op.create_index("ix_material_requisition_items_status", "material_requisition_items", ["status"])
    op.create_index(
        "ix_material_requisition_items_supplier_rfq_item_id",
        "material_requisition_items",
        ["supplier_rfq_item_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_material_requisition_items_supplier_rfq_item_id", table_name="material_requisition_items")
    op.drop_index("ix_material_requisition_items_status", table_name="material_requisition_items")
    op.drop_index("ix_material_requisition_items_requisition_id", table_name="material_requisition_items")
    op.drop_index("ix_material_requisition_items_material_id", table_name="material_requisition_items")
    op.drop_index(
        "ix_mr_items_requirement_id",
        table_name="material_requisition_items",
    )
    op.drop_table("material_requisition_items")
    op.drop_index("ix_material_requisitions_status", table_name="material_requisitions")
    op.drop_index("ix_material_requisitions_reviewed_by_user_id", table_name="material_requisitions")
    op.drop_index("ix_material_requisitions_requested_by_user_id", table_name="material_requisitions")
    op.drop_index("ix_material_requisitions_project_id", table_name="material_requisitions")
    op.drop_index("ix_material_requisitions_house_model_id", table_name="material_requisitions")
    op.drop_index("ix_material_requisitions_converted_rfq_id", table_name="material_requisitions")
    op.drop_index("ix_material_requisitions_company_id", table_name="material_requisitions")
    op.drop_index("ix_material_requisitions_client_id", table_name="material_requisitions")
    op.drop_table("material_requisitions")
