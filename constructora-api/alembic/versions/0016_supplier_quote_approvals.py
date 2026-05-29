"""supplier quote approvals

Revision ID: 0016_supplier_quote_approvals
Revises: 0015_audit_events
Create Date: 2026-05-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0016_supplier_quote_approvals"
down_revision: str | None = "0015_audit_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "supplier_quote_approvals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("rfq_id", sa.Integer(), nullable=False),
        sa.Column("supplier_quote_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="requested"),
        sa.Column("request_notes", sa.Text(), nullable=True),
        sa.Column("decision_notes", sa.Text(), nullable=True),
        sa.Column("requested_by", sa.Integer(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_by", sa.Integer(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["decided_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["rfq_id"], ["supplier_rfqs.id"]),
        sa.ForeignKeyConstraint(["supplier_quote_id"], ["supplier_quotes.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("supplier_quote_id", name="uq_supplier_quote_approvals_quote"),
    )
    op.create_index(
        op.f("ix_supplier_quote_approvals_company_id"),
        "supplier_quote_approvals",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_supplier_quote_approvals_decided_by"),
        "supplier_quote_approvals",
        ["decided_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_supplier_quote_approvals_requested_by"),
        "supplier_quote_approvals",
        ["requested_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_supplier_quote_approvals_rfq_id"),
        "supplier_quote_approvals",
        ["rfq_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_supplier_quote_approvals_status"),
        "supplier_quote_approvals",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_supplier_quote_approvals_supplier_quote_id"),
        "supplier_quote_approvals",
        ["supplier_quote_id"],
        unique=False,
    )

    permissions = [
        ("supplier_quotes", "request_approval", "Solicitar aprobacion de cotizaciones de proveedores"),
        ("supplier_quotes", "approve", "Aprobar o rechazar cotizaciones de proveedores"),
    ]
    for module, action, description in permissions:
        op.execute(
            f"""
            INSERT INTO permissions (module, action, description)
            VALUES ('{module}', '{action}', '{description}')
            ON CONFLICT (module, action) DO NOTHING
            """
        )
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        JOIN permissions p ON p.module = 'supplier_quotes' AND p.action = 'request_approval'
        WHERE r.name IN ('master_admin', 'admin', 'Administrador de constructora', 'Cotizaciones y costos', 'Compras')
        ON CONFLICT (role_id, permission_id) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        JOIN permissions p ON p.module = 'supplier_quotes' AND p.action = 'approve'
        WHERE r.name IN ('master_admin', 'admin', 'Administrador de constructora', 'Cotizaciones y costos')
        ON CONFLICT (role_id, permission_id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_supplier_quote_approvals_supplier_quote_id"), table_name="supplier_quote_approvals")
    op.drop_index(op.f("ix_supplier_quote_approvals_status"), table_name="supplier_quote_approvals")
    op.drop_index(op.f("ix_supplier_quote_approvals_rfq_id"), table_name="supplier_quote_approvals")
    op.drop_index(op.f("ix_supplier_quote_approvals_requested_by"), table_name="supplier_quote_approvals")
    op.drop_index(op.f("ix_supplier_quote_approvals_decided_by"), table_name="supplier_quote_approvals")
    op.drop_index(op.f("ix_supplier_quote_approvals_company_id"), table_name="supplier_quote_approvals")
    op.drop_table("supplier_quote_approvals")
    op.execute(
        """
        DELETE FROM permissions
        WHERE module = 'supplier_quotes' AND action IN ('request_approval', 'approve')
        """
    )
