"""notifications

Revision ID: 0020_notifications
Revises: 0019_email_outbox
Create Date: 2026-06-08 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision: str = "0020_notifications"
down_revision: str | None = "0019_email_outbox"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("notification_type", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False, server_default="task"),
        sa.Column("priority", sa.String(length=20), nullable=False, server_default="normal"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="unread"),
        sa.Column("source_module", sa.String(length=80), nullable=False),
        sa.Column("entity_type", sa.String(length=120), nullable=True),
        sa.Column("entity_id", sa.String(length=80), nullable=True),
        sa.Column("entity_label", sa.String(length=255), nullable=True),
        sa.Column("action_url", sa.String(length=255), nullable=True),
        sa.Column("event_metadata", sa.JSON(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "company_id",
        "user_id",
        "notification_type",
        "category",
        "priority",
        "status",
        "source_module",
        "entity_type",
        "entity_id",
        "due_at",
    ):
        op.create_index(op.f(f"ix_notifications_{column}"), "notifications", [column], unique=False)


def downgrade() -> None:
    for column in (
        "due_at",
        "entity_id",
        "entity_type",
        "source_module",
        "status",
        "priority",
        "category",
        "notification_type",
        "user_id",
        "company_id",
    ):
        op.drop_index(op.f(f"ix_notifications_{column}"), table_name="notifications")
    op.drop_table("notifications")
