"""executive dashboard permissions

Revision ID: 0040_executive_dashboard
Revises: 0039_financial_reconciliations
"""

from collections.abc import Sequence

from alembic import op


revision: str = "0040_executive_dashboard"
down_revision: str | None = "0039_financial_reconciliations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


DIRECTION_PERMISSIONS = (
    "executive_dashboard:view",
    "executive_dashboard:export",
    "clients:view",
    "projects:view",
    "house_models:view",
    "materials:view",
    "material_requisitions:view",
    "supplier_rfq:view",
    "supplier_quotes:view",
    "purchase_approvals:view",
    "purchase_orders:view",
    "inventory_progress:view",
    "inventory_missing:view",
    "inventory_stock:view",
    "supplier_invoices:view",
    "supplier_payments:view",
    "project_financials:view",
    "financial_reconciliations:view",
    "notifications:view",
)


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO permissions (module, action, description)
        VALUES
            ('executive_dashboard', 'view', 'Ver control ejecutivo de la constructora'),
            ('executive_dashboard', 'export', 'Exportar indicadores ejecutivos')
        ON CONFLICT (module, action) DO UPDATE SET description = EXCLUDED.description
        """
    )
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        JOIN permissions p ON p.module = 'executive_dashboard'
        WHERE r.name = 'Administrador'
        ON CONFLICT (role_id, permission_id) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO roles (company_id, name, description, is_system_role)
        SELECT
            c.id,
            'Direccion',
            'Consulta ejecutiva transversal sin permisos de captura ni configuracion.',
            false
        FROM companies c
        ON CONFLICT (company_id, name) DO UPDATE
        SET description = EXCLUDED.description
        """
    )
    permission_codes = ", ".join(f"'{code}'" for code in DIRECTION_PERMISSIONS)
    op.execute(
        f"""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        JOIN permissions p ON (p.module || ':' || p.action) IN ({permission_codes})
        WHERE r.name = 'Direccion'
        ON CONFLICT (role_id, permission_id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM role_permissions
        WHERE permission_id IN (
            SELECT id FROM permissions WHERE module = 'executive_dashboard'
        )
        """
    )
    op.execute("DELETE FROM permissions WHERE module = 'executive_dashboard'")
