"""system email settings

Revision ID: 0014_system_email_settings
Revises: 0013_house_model_review_status
Create Date: 2026-05-26 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0014_system_email_settings"
down_revision: str | None = "0013_house_model_review_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "system_email_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("sender_name", sa.String(length=160), nullable=False),
        sa.Column("sender_email", sa.String(length=255), nullable=False),
        sa.Column("reply_to_email", sa.String(length=255), nullable=True),
        sa.Column("smtp_host", sa.String(length=255), nullable=False),
        sa.Column("smtp_port", sa.Integer(), nullable=False),
        sa.Column("smtp_username", sa.String(length=255), nullable=False),
        sa.Column("smtp_password", sa.Text(), nullable=True),
        sa.Column("smtp_use_ssl", sa.Boolean(), nullable=False),
        sa.Column("smtp_use_tls", sa.Boolean(), nullable=False),
        sa.Column("imap_host", sa.String(length=255), nullable=True),
        sa.Column("imap_port", sa.Integer(), nullable=True),
        sa.Column("imap_username", sa.String(length=255), nullable=True),
        sa.Column("imap_password", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_test_status", sa.String(length=40), nullable=True),
        sa.Column("last_test_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", name="uq_system_email_settings_company"),
    )
    op.create_index(
        op.f("ix_system_email_settings_company_id"),
        "system_email_settings",
        ["company_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_system_email_settings_company_id"), table_name="system_email_settings")
    op.drop_table("system_email_settings")
