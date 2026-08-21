"""purchasing audit permission

Revision ID: 0043_purchasing_audit
Revises: 0042_quote_pdf_extraction
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0043_purchasing_audit"
down_revision: str | None = "0042_quote_pdf_extraction"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            INSERT INTO permissions (module, action, description)
            VALUES ('purchasing_audit', 'view', 'Ver bitacora administrativa de Compras')
            ON CONFLICT (module, action)
            DO UPDATE SET description = EXCLUDED.description
            """
        )
    )
    conn.execute(
        sa.text(
            """
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT r.id, p.id
            FROM roles r
            CROSS JOIN permissions p
            WHERE r.name IN ('Administrador', 'master_admin')
              AND p.module = 'purchasing_audit'
              AND p.action = 'view'
            ON CONFLICT (role_id, permission_id) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            DELETE FROM role_permissions rp
            USING permissions p
            WHERE rp.permission_id = p.id
              AND p.module = 'purchasing_audit'
              AND p.action = 'view'
            """
        )
    )
    conn.execute(
        sa.text(
            """
            DELETE FROM permissions
            WHERE module = 'purchasing_audit' AND action = 'view'
            """
        )
    )
