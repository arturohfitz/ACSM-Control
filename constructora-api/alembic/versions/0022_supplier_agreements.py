"""supplier agreements

Revision ID: 0022_supplier_agreements
Revises: 0021_user_client_access
Create Date: 2026-06-12 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0022_supplier_agreements"
down_revision = "0021_user_client_access"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "supplier_agreements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("supplier_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("house_model_id", sa.Integer(), nullable=False),
        sa.Column("agreement_number", sa.String(length=120), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("payment_terms_days", sa.Integer(), nullable=False),
        sa.Column("average_delivery_days", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["house_model_id"], ["house_models.id"]),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "supplier_id",
            "client_id",
            "house_model_id",
            "agreement_number",
            name="uq_supplier_agreements_scope_number",
        ),
    )
    op.create_index("ix_supplier_agreements_client_id", "supplier_agreements", ["client_id"])
    op.create_index("ix_supplier_agreements_company_id", "supplier_agreements", ["company_id"])
    op.create_index("ix_supplier_agreements_house_model_id", "supplier_agreements", ["house_model_id"])
    op.create_index("ix_supplier_agreements_status", "supplier_agreements", ["status"])
    op.create_index("ix_supplier_agreements_supplier_id", "supplier_agreements", ["supplier_id"])

    op.create_table(
        "supplier_agreement_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agreement_id", sa.Integer(), nullable=False),
        sa.Column("material_id", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("unit", sa.String(length=40), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 4), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("delivery_days", sa.Integer(), nullable=True),
        sa.Column("min_quantity", sa.Numeric(14, 4), nullable=True),
        sa.Column("max_quantity", sa.Numeric(14, 4), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["agreement_id"], ["supplier_agreements.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agreement_id", "material_id", name="uq_supplier_agreement_item_material"),
    )
    op.create_index("ix_supplier_agreement_items_agreement_id", "supplier_agreement_items", ["agreement_id"])
    op.create_index("ix_supplier_agreement_items_material_id", "supplier_agreement_items", ["material_id"])
    op.create_index("ix_supplier_agreement_items_status", "supplier_agreement_items", ["status"])

    op.add_column(
        "supplier_rfqs",
        sa.Column("request_type", sa.String(length=40), server_default="standard", nullable=False),
    )
    op.add_column(
        "supplier_rfqs",
        sa.Column("supplier_agreement_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_supplier_rfqs_supplier_agreement_id",
        "supplier_rfqs",
        "supplier_agreements",
        ["supplier_agreement_id"],
        ["id"],
    )
    op.create_index("ix_supplier_rfqs_request_type", "supplier_rfqs", ["request_type"])
    op.create_index("ix_supplier_rfqs_supplier_agreement_id", "supplier_rfqs", ["supplier_agreement_id"])

    permissions = [
        ("supplier_agreements", "view", "Ver convenios de proveedores"),
        ("supplier_agreements", "create", "Crear convenios de proveedores"),
        ("supplier_agreements", "edit", "Editar convenios de proveedores"),
        ("supplier_agreements", "delete", "Eliminar convenios de proveedores"),
        ("supplier_agreements", "use", "Crear solicitudes directas por convenio"),
    ]
    for module, action, description in permissions:
        op.execute(
            sa.text(
                """
                INSERT INTO permissions (module, action, description)
                SELECT :module, :action, :description
                WHERE NOT EXISTS (
                    SELECT 1 FROM permissions WHERE module = :module AND action = :action
                )
                """
            ).bindparams(module=module, action=action, description=description)
        )


def downgrade() -> None:
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN "
        "(SELECT id FROM permissions WHERE module = 'supplier_agreements')"
    )
    op.execute("DELETE FROM permissions WHERE module = 'supplier_agreements'")
    op.drop_index("ix_supplier_rfqs_supplier_agreement_id", table_name="supplier_rfqs")
    op.drop_index("ix_supplier_rfqs_request_type", table_name="supplier_rfqs")
    op.drop_constraint("fk_supplier_rfqs_supplier_agreement_id", "supplier_rfqs", type_="foreignkey")
    op.drop_column("supplier_rfqs", "supplier_agreement_id")
    op.drop_column("supplier_rfqs", "request_type")
    op.drop_index("ix_supplier_agreement_items_status", table_name="supplier_agreement_items")
    op.drop_index("ix_supplier_agreement_items_material_id", table_name="supplier_agreement_items")
    op.drop_index("ix_supplier_agreement_items_agreement_id", table_name="supplier_agreement_items")
    op.drop_table("supplier_agreement_items")
    op.drop_index("ix_supplier_agreements_supplier_id", table_name="supplier_agreements")
    op.drop_index("ix_supplier_agreements_status", table_name="supplier_agreements")
    op.drop_index("ix_supplier_agreements_house_model_id", table_name="supplier_agreements")
    op.drop_index("ix_supplier_agreements_company_id", table_name="supplier_agreements")
    op.drop_index("ix_supplier_agreements_client_id", table_name="supplier_agreements")
    op.drop_table("supplier_agreements")
