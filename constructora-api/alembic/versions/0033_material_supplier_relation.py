"""material supplier relation

Revision ID: 0033_material_supplier_relation
Revises: 0032_permission_catalog_refactor
Create Date: 2026-07-06 18:45:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0033_material_supplier_relation"
down_revision = "0032_permission_catalog_refactor"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("materials", sa.Column("supplier_id", sa.Integer(), nullable=True))
    op.create_index("ix_materials_supplier_id", "materials", ["supplier_id"], unique=False)
    op.create_foreign_key(
        "fk_materials_supplier_id_suppliers",
        "materials",
        "suppliers",
        ["supplier_id"],
        ["id"],
    )
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT r.id, p.id
            FROM roles r
            JOIN permissions p
              ON (p.module, p.action) IN (
                ('materials', 'create'),
                ('suppliers', 'view')
              )
            WHERE r.name = 'Obra'
              AND r.is_system_role IS FALSE
            ON CONFLICT DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.drop_constraint("fk_materials_supplier_id_suppliers", "materials", type_="foreignkey")
    op.drop_index("ix_materials_supplier_id", table_name="materials")
    op.drop_column("materials", "supplier_id")
