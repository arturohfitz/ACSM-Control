"""notification settings

Revision ID: 0027_notification_settings
Revises: 0026_supplier_quote_links
Create Date: 2026-06-23 07:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0027_notification_settings"
down_revision = "0026_supplier_quote_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_notification_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("sound_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sound_volume", sa.Integer(), nullable=False, server_default="45"),
        sa.Column("flash_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("repeat_alert_minutes", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", name="uq_system_notification_settings_company"),
    )
    op.create_index(
        "ix_system_notification_settings_company_id",
        "system_notification_settings",
        ["company_id"],
    )
    op.execute(
        """
        INSERT INTO system_notification_settings (
            company_id,
            sound_enabled,
            sound_volume,
            flash_enabled,
            repeat_alert_minutes
        )
        SELECT id, true, 45, true, 5
        FROM companies
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index(
        "ix_system_notification_settings_company_id",
        table_name="system_notification_settings",
    )
    op.drop_table("system_notification_settings")
