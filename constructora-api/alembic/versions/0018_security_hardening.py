"""security settings and rfq fingerprint

Revision ID: 0018_security_hardening
Revises: 0017_supplier_rfq_exceptions
Create Date: 2026-06-03 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision: str = "0018_security_hardening"
down_revision: str | None = "0017_supplier_rfq_exceptions"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "supplier_rfq_exception_requests",
        sa.Column("payload_fingerprint", sa.String(length=64), nullable=True),
    )
    op.create_index(
        op.f("ix_supplier_rfq_exception_requests_payload_fingerprint"),
        "supplier_rfq_exception_requests",
        ["payload_fingerprint"],
        unique=False,
    )

    permissions = [
        ("settings", "edit", "Editar configuracion"),
        ("settings", "test_email", "Probar configuracion de correo"),
    ]
    for module, action, description in permissions:
        op.execute(
            sa.text(
                """
                INSERT INTO permissions (module, action, description)
                VALUES (:module, :action, :description)
                ON CONFLICT (module, action) DO NOTHING
                """
            ).bindparams(module=module, action=action, description=description)
        )

    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        JOIN permissions p ON p.module = 'settings' AND p.action IN ('edit', 'test_email')
        WHERE r.name IN ('admin', 'Administrador de constructora', 'master_admin')
        ON CONFLICT (role_id, permission_id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM role_permissions
        WHERE permission_id IN (
            SELECT id FROM permissions
            WHERE module = 'settings' AND action IN ('edit', 'test_email')
        )
        """
    )
    op.execute("DELETE FROM permissions WHERE module = 'settings' AND action IN ('edit', 'test_email')")
    op.drop_index(
        op.f("ix_supplier_rfq_exception_requests_payload_fingerprint"),
        table_name="supplier_rfq_exception_requests",
    )
    op.drop_column("supplier_rfq_exception_requests", "payload_fingerprint")
