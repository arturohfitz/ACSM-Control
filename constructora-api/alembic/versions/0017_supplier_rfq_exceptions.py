"""supplier rfq exceptions

Revision ID: 0017_supplier_rfq_exceptions
Revises: 0016_supplier_quote_approvals
Create Date: 2026-06-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0017_supplier_rfq_exceptions"
down_revision: str | None = "0016_supplier_quote_approvals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "supplier_rfq_exception_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("rfq_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="requested"),
        sa.Column("required_by", sa.Date(), nullable=True),
        sa.Column("response_deadline", sa.Date(), nullable=True),
        sa.Column("supplier_count", sa.Integer(), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("payload_snapshot", sa.JSON(), nullable=False),
        sa.Column("request_notes", sa.Text(), nullable=False),
        sa.Column("decision_notes", sa.Text(), nullable=True),
        sa.Column("requested_by", sa.Integer(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_by", sa.Integer(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["decided_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["rfq_id"], ["supplier_rfqs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_supplier_rfq_exception_requests_company_id"), "supplier_rfq_exception_requests", ["company_id"])
    op.create_index(op.f("ix_supplier_rfq_exception_requests_decided_by"), "supplier_rfq_exception_requests", ["decided_by"])
    op.create_index(op.f("ix_supplier_rfq_exception_requests_project_id"), "supplier_rfq_exception_requests", ["project_id"])
    op.create_index(op.f("ix_supplier_rfq_exception_requests_requested_by"), "supplier_rfq_exception_requests", ["requested_by"])
    op.create_index(op.f("ix_supplier_rfq_exception_requests_rfq_id"), "supplier_rfq_exception_requests", ["rfq_id"])
    op.create_index(op.f("ix_supplier_rfq_exception_requests_status"), "supplier_rfq_exception_requests", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_supplier_rfq_exception_requests_status"), table_name="supplier_rfq_exception_requests")
    op.drop_index(op.f("ix_supplier_rfq_exception_requests_rfq_id"), table_name="supplier_rfq_exception_requests")
    op.drop_index(op.f("ix_supplier_rfq_exception_requests_requested_by"), table_name="supplier_rfq_exception_requests")
    op.drop_index(op.f("ix_supplier_rfq_exception_requests_project_id"), table_name="supplier_rfq_exception_requests")
    op.drop_index(op.f("ix_supplier_rfq_exception_requests_decided_by"), table_name="supplier_rfq_exception_requests")
    op.drop_index(op.f("ix_supplier_rfq_exception_requests_company_id"), table_name="supplier_rfq_exception_requests")
    op.drop_table("supplier_rfq_exception_requests")
