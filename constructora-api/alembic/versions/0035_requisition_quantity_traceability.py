"""requisition quantity traceability

Revision ID: 0035_requisition_traceability
Revises: 0034_material_unit_conversions
Create Date: 2026-07-20 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0035_requisition_traceability"
down_revision: str | None = "0034_material_unit_conversions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "material_requisition_items",
        sa.Column("requested_base_quantity", sa.Numeric(14, 4), nullable=True),
    )
    op.add_column(
        "material_requisition_items",
        sa.Column("unit_conversion_factor", sa.Numeric(18, 8), nullable=True),
    )
    op.add_column(
        "material_requisition_items",
        sa.Column("coverage_houses", sa.Numeric(12, 2), nullable=True),
    )
    op.execute(
        """
        UPDATE material_requisition_items
        SET requested_base_quantity = requested_quantity,
            unit_conversion_factor = 1
        WHERE requested_unit IS NULL OR upper(trim(requested_unit)) = upper(trim(unit))
        """
    )
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        JOIN permissions p
          ON p.module = 'construction_concepts' AND p.action = 'create'
        WHERE r.name = 'Obra'
          AND r.is_system_role IS FALSE
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_column("material_requisition_items", "coverage_houses")
    op.drop_column("material_requisition_items", "unit_conversion_factor")
    op.drop_column("material_requisition_items", "requested_base_quantity")
