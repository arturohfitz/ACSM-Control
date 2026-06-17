"""supplier quote notification links

Revision ID: 0026_supplier_quote_links
Revises: 0025_normalize_notifications
Create Date: 2026-06-16 17:35:00.000000
"""

from alembic import op


revision = "0026_supplier_quote_links"
down_revision = "0025_normalize_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE notifications
        SET action_url = '/purchasing?rfq_id=' || (event_metadata ->> 'rfq_id') || '&focus=uploads'
        WHERE notification_type IN (
            'supplier_quote_document_uploaded',
            'supplier_quote_update_requested'
        )
        AND event_metadata IS NOT NULL
        AND event_metadata ->> 'rfq_id' IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE notifications
        SET action_url = '/purchasing'
        WHERE notification_type = 'supplier_quote_update_requested'
        AND (
            event_metadata IS NULL
            OR event_metadata ->> 'rfq_id' IS NULL
        )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE notifications
        SET action_url = '/purchasing/approvals'
        WHERE notification_type = 'supplier_quote_update_requested'
        """
    )
    op.execute(
        """
        UPDATE notifications
        SET action_url = '/purchasing'
        WHERE notification_type = 'supplier_quote_document_uploaded'
        """
    )
