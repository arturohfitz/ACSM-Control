"""financial reconciliation workflow

Revision ID: 0039_financial_reconciliations
Revises: 0038_project_material_financials
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0039_financial_reconciliations"
down_revision: str | None = "0038_project_material_financials"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _indexes(table: str, columns: tuple[str, ...]) -> None:
    for column in columns:
        op.create_index(f"ix_{table}_{column}", table, [column])


def upgrade() -> None:
    op.create_table(
        "financial_reconciliation_cases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("purchase_order_id", sa.Integer(), sa.ForeignKey("purchase_orders.id"), nullable=False),
        sa.Column("supplier_invoice_id", sa.Integer(), sa.ForeignKey("supplier_invoices.id"), nullable=False),
        sa.Column("supplier_payment_id", sa.Integer(), sa.ForeignKey("supplier_payments.id"), nullable=True),
        sa.Column("case_number", sa.String(80), nullable=False, unique=True),
        sa.Column("issue_type", sa.String(60), nullable=False),
        sa.Column("resolution_type", sa.String(60), nullable=False),
        sa.Column("status", sa.String(40), server_default="requested", nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("proposed_data", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("original_snapshot", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("decision_notes", sa.Text(), nullable=True),
        sa.Column("requested_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    _indexes(
        "financial_reconciliation_cases",
        (
            "company_id", "project_id", "purchase_order_id", "supplier_invoice_id",
            "supplier_payment_id", "case_number", "issue_type", "resolution_type", "status",
            "requested_by", "decided_by", "applied_by",
        ),
    )

    op.create_table(
        "supplier_invoice_corrections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("supplier_invoice_id", sa.Integer(), sa.ForeignKey("supplier_invoices.id"), nullable=False),
        sa.Column(
            "reconciliation_case_id", sa.Integer(),
            sa.ForeignKey("financial_reconciliation_cases.id"), nullable=False, unique=True,
        ),
        sa.Column("before_snapshot", sa.JSON(), nullable=False),
        sa.Column("after_snapshot", sa.JSON(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("applied_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    _indexes(
        "supplier_invoice_corrections",
        ("company_id", "supplier_invoice_id", "reconciliation_case_id", "applied_by"),
    )

    op.create_table(
        "purchase_order_amendments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("purchase_order_id", sa.Integer(), sa.ForeignKey("purchase_orders.id"), nullable=False),
        sa.Column(
            "reconciliation_case_id", sa.Integer(),
            sa.ForeignKey("financial_reconciliation_cases.id"), nullable=False, unique=True,
        ),
        sa.Column("previous_subtotal", sa.Numeric(14, 2), nullable=False),
        sa.Column("new_subtotal", sa.Numeric(14, 2), nullable=False),
        sa.Column("difference", sa.Numeric(14, 2), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("applied_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    _indexes(
        "purchase_order_amendments",
        ("company_id", "purchase_order_id", "reconciliation_case_id", "applied_by"),
    )

    op.create_table(
        "supplier_payment_reversals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column(
            "supplier_payment_id", sa.Integer(),
            sa.ForeignKey("supplier_payments.id"), nullable=False, unique=True,
        ),
        sa.Column(
            "reconciliation_case_id", sa.Integer(),
            sa.ForeignKey("financial_reconciliation_cases.id"), nullable=False, unique=True,
        ),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("applied_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    _indexes(
        "supplier_payment_reversals",
        ("company_id", "supplier_payment_id", "reconciliation_case_id", "applied_by"),
    )

    op.execute(
        """
        INSERT INTO permissions (module, action, description)
        VALUES
            ('financial_reconciliations', 'view', 'Ver conciliaciones financieras'),
            ('financial_reconciliations', 'request', 'Solicitar correcciones financieras'),
            ('financial_reconciliations', 'approve', 'Aprobar y aplicar correcciones financieras')
        ON CONFLICT (module, action) DO UPDATE SET description = EXCLUDED.description
        """
    )
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        JOIN permissions p ON p.module = 'financial_reconciliations'
        WHERE r.name = 'Administrador'
        ON CONFLICT (role_id, permission_id) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        JOIN permissions p ON (p.module || ':' || p.action) IN (
            'financial_reconciliations:view', 'financial_reconciliations:request'
        )
        WHERE r.name = 'Cuentas por pagar'
        ON CONFLICT (role_id, permission_id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_table("supplier_payment_reversals")
    op.drop_table("purchase_order_amendments")
    op.drop_table("supplier_invoice_corrections")
    op.drop_table("financial_reconciliation_cases")
    op.execute(
        """
        DELETE FROM role_permissions
        WHERE permission_id IN (
            SELECT id FROM permissions WHERE module = 'financial_reconciliations'
        )
        """
    )
    op.execute("DELETE FROM permissions WHERE module = 'financial_reconciliations'")
