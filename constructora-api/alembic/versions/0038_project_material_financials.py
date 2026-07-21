"""project material budget baselines and financial permissions

Revision ID: 0038_project_material_financials
Revises: 0037_invoice_documents
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0038_project_material_financials"
down_revision: str | None = "0037_invoice_documents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_material_budget_baselines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(40), server_default="approved", nullable=False),
        sa.Column("currency", sa.String(10), server_default="MXN", nullable=False),
        sa.Column("total_amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("project_id", "revision", name="uq_project_material_budget_revision"),
    )
    for column in ("company_id", "project_id", "status", "approved_by"):
        op.create_index(
            f"ix_project_material_budget_baselines_{column}",
            "project_material_budget_baselines",
            [column],
        )

    op.create_table(
        "project_material_budget_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "baseline_id",
            sa.Integer(),
            sa.ForeignKey("project_material_budget_baselines.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "house_model_id",
            sa.Integer(),
            sa.ForeignKey("house_models.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "source_document_id",
            sa.Integer(),
            sa.ForeignKey("house_model_documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "material_requirement_id",
            sa.Integer(),
            sa.ForeignKey("house_model_material_requirements.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "material_id",
            sa.Integer(),
            sa.ForeignKey("materials.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source_code", sa.String(80), nullable=True),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("unit", sa.String(40), nullable=False),
        sa.Column("houses_quantity", sa.Numeric(12, 2), nullable=False),
        sa.Column("quantity_per_house", sa.Numeric(14, 6), nullable=False),
        sa.Column("budget_quantity", sa.Numeric(16, 4), nullable=False),
        sa.Column("unit_cost", sa.Numeric(14, 4), nullable=False),
        sa.Column("line_total", sa.Numeric(16, 2), nullable=False),
    )
    for column in (
        "baseline_id",
        "house_model_id",
        "source_document_id",
        "material_requirement_id",
        "material_id",
    ):
        op.create_index(
            f"ix_project_material_budget_items_{column}",
            "project_material_budget_items",
            [column],
        )

    op.execute(
        """
        INSERT INTO permissions (module, action, description)
        VALUES
            ('project_financials', 'view', 'Ver avance financiero de materiales por desarrollo'),
            ('project_material_budgets', 'approve', 'Aprobar linea base del presupuesto de materiales')
        ON CONFLICT (module, action) DO UPDATE SET description = EXCLUDED.description
        """
    )
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        JOIN permissions p ON (p.module || ':' || p.action) IN (
            'project_financials:view', 'project_material_budgets:approve'
        )
        WHERE r.name = 'Administrador'
        ON CONFLICT (role_id, permission_id) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        JOIN permissions p ON (p.module || ':' || p.action) = 'project_financials:view'
        WHERE r.name = 'Cuentas por pagar'
        ON CONFLICT (role_id, permission_id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_table("project_material_budget_items")
    op.drop_table("project_material_budget_baselines")
    op.execute(
        """
        DELETE FROM role_permissions
        WHERE permission_id IN (
            SELECT id FROM permissions
            WHERE (module || ':' || action) IN (
                'project_financials:view', 'project_material_budgets:approve'
            )
        )
        """
    )
    op.execute(
        """
        DELETE FROM permissions
        WHERE (module || ':' || action) IN (
            'project_financials:view', 'project_material_budgets:approve'
        )
        """
    )
