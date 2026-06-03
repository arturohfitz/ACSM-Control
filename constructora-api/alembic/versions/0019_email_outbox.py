"""email outbox

Revision ID: 0019_email_outbox
Revises: 0018_security_hardening
Create Date: 2026-06-03 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision: str = "0019_email_outbox"
down_revision: str | None = "0018_security_hardening"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "email_outbox_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("requested_by", sa.Integer(), nullable=True),
        sa.Column("message_type", sa.String(length=80), nullable=False),
        sa.Column("related_entity_type", sa.String(length=120), nullable=True),
        sa.Column("related_entity_id", sa.String(length=80), nullable=True),
        sa.Column("recipient_email", sa.String(length=255), nullable=False),
        sa.Column("recipient_name", sa.String(length=200), nullable=True),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("text_body", sa.Text(), nullable=False),
        sa.Column("html_body", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_email_outbox_messages_company_id"),
        "email_outbox_messages",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_email_outbox_messages_message_type"),
        "email_outbox_messages",
        ["message_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_email_outbox_messages_next_attempt_at"),
        "email_outbox_messages",
        ["next_attempt_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_email_outbox_messages_recipient_email"),
        "email_outbox_messages",
        ["recipient_email"],
        unique=False,
    )
    op.create_index(
        op.f("ix_email_outbox_messages_related_entity_id"),
        "email_outbox_messages",
        ["related_entity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_email_outbox_messages_related_entity_type"),
        "email_outbox_messages",
        ["related_entity_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_email_outbox_messages_requested_by"),
        "email_outbox_messages",
        ["requested_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_email_outbox_messages_status"),
        "email_outbox_messages",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_email_outbox_messages_status"), table_name="email_outbox_messages")
    op.drop_index(op.f("ix_email_outbox_messages_requested_by"), table_name="email_outbox_messages")
    op.drop_index(op.f("ix_email_outbox_messages_related_entity_type"), table_name="email_outbox_messages")
    op.drop_index(op.f("ix_email_outbox_messages_related_entity_id"), table_name="email_outbox_messages")
    op.drop_index(op.f("ix_email_outbox_messages_recipient_email"), table_name="email_outbox_messages")
    op.drop_index(op.f("ix_email_outbox_messages_next_attempt_at"), table_name="email_outbox_messages")
    op.drop_index(op.f("ix_email_outbox_messages_message_type"), table_name="email_outbox_messages")
    op.drop_index(op.f("ix_email_outbox_messages_company_id"), table_name="email_outbox_messages")
    op.drop_table("email_outbox_messages")
