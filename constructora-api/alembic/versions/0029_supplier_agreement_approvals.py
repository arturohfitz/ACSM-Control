"""supplier agreement approvals

Revision ID: 0029_agreement_approvals
Revises: 0028_po_partial_billing
Create Date: 2026-06-25 18:45:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0029_agreement_approvals"
down_revision = "0028_po_partial_billing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "supplier_agreements",
        sa.Column("approval_status", sa.String(length=40), nullable=False, server_default="approved"),
    )
    op.add_column("supplier_agreements", sa.Column("request_notes", sa.Text(), nullable=True))
    op.add_column("supplier_agreements", sa.Column("decision_notes", sa.Text(), nullable=True))
    op.add_column("supplier_agreements", sa.Column("requested_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("supplier_agreements", sa.Column("decided_by", sa.Integer(), nullable=True))
    op.add_column("supplier_agreements", sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        "fk_supplier_agreements_decided_by",
        "supplier_agreements",
        "users",
        ["decided_by"],
        ["id"],
    )
    op.create_index("ix_supplier_agreements_approval_status", "supplier_agreements", ["approval_status"])
    op.create_index("ix_supplier_agreements_decided_by", "supplier_agreements", ["decided_by"])
    op.alter_column("supplier_agreements", "approval_status", server_default=None)

    op.execute(
        sa.text(
            """
            INSERT INTO permissions (module, action, description)
            SELECT 'supplier_agreements', 'approve', 'Aprobar o rechazar convenios de proveedores'
            WHERE NOT EXISTS (
                SELECT 1 FROM permissions
                WHERE module = 'supplier_agreements' AND action = 'approve'
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT r.id, p.id
            FROM roles r
            JOIN permissions p
                ON p.module = 'supplier_agreements'
               AND p.action = 'approve'
            WHERE r.name = 'Administrador'
              AND r.company_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM role_permissions rp
                  WHERE rp.role_id = r.id AND rp.permission_id = p.id
              )
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_supplier_agreements_decided_by", table_name="supplier_agreements")
    op.drop_index("ix_supplier_agreements_approval_status", table_name="supplier_agreements")
    op.drop_constraint("fk_supplier_agreements_decided_by", "supplier_agreements", type_="foreignkey")
    op.drop_column("supplier_agreements", "decided_at")
    op.drop_column("supplier_agreements", "decided_by")
    op.drop_column("supplier_agreements", "requested_at")
    op.drop_column("supplier_agreements", "decision_notes")
    op.drop_column("supplier_agreements", "request_notes")
    op.drop_column("supplier_agreements", "approval_status")
