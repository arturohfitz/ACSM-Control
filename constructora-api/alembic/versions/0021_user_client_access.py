"""user client access

Revision ID: 0021_user_client_access
Revises: 0020_notifications
Create Date: 2026-06-08 14:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0021_user_client_access"
down_revision = "0020_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("client_access_mode", sa.String(length=20), nullable=False, server_default="all"),
    )
    op.create_table(
        "user_client_access",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "client_id", name="uq_user_client_access_pair"),
    )
    op.create_index(op.f("ix_user_client_access_company_id"), "user_client_access", ["company_id"])
    op.add_column("notifications", sa.Column("client_id", sa.Integer(), nullable=True))
    op.add_column("notifications", sa.Column("project_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_notifications_client_id", "notifications", "clients", ["client_id"], ["id"])
    op.create_foreign_key("fk_notifications_project_id", "notifications", "projects", ["project_id"], ["id"])
    op.create_index(op.f("ix_notifications_client_id"), "notifications", ["client_id"])
    op.create_index(op.f("ix_notifications_project_id"), "notifications", ["project_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_notifications_project_id"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_client_id"), table_name="notifications")
    op.drop_constraint("fk_notifications_project_id", "notifications", type_="foreignkey")
    op.drop_constraint("fk_notifications_client_id", "notifications", type_="foreignkey")
    op.drop_column("notifications", "project_id")
    op.drop_column("notifications", "client_id")
    op.drop_index(op.f("ix_user_client_access_company_id"), table_name="user_client_access")
    op.drop_table("user_client_access")
    op.drop_column("users", "client_access_mode")
