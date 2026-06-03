from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class SystemEmailSettings(TimestampMixin, Base):
    __tablename__ = "system_email_settings"
    __table_args__ = (
        UniqueConstraint("company_id", name="uq_system_email_settings_company"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    sender_name: Mapped[str] = mapped_column(String(160), default="ACSM Control", nullable=False)
    sender_email: Mapped[str] = mapped_column(String(255), nullable=False)
    reply_to_email: Mapped[str | None] = mapped_column(String(255))
    smtp_host: Mapped[str] = mapped_column(String(255), nullable=False)
    smtp_port: Mapped[int] = mapped_column(Integer, default=465, nullable=False)
    smtp_username: Mapped[str] = mapped_column(String(255), nullable=False)
    smtp_password: Mapped[str | None] = mapped_column(Text)
    smtp_use_ssl: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    smtp_use_tls: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    imap_host: Mapped[str | None] = mapped_column(String(255))
    imap_port: Mapped[int | None] = mapped_column(Integer)
    imap_username: Mapped[str | None] = mapped_column(String(255))
    imap_password: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_test_status: Mapped[str | None] = mapped_column(String(40))
    last_test_message: Mapped[str | None] = mapped_column(Text)


class EmailOutboxMessage(TimestampMixin, Base):
    __tablename__ = "email_outbox_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    requested_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    message_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    related_entity_type: Mapped[str | None] = mapped_column(String(120), index=True)
    related_entity_id: Mapped[str | None] = mapped_column(String(80), index=True)
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    recipient_name: Mapped[str | None] = mapped_column(String(200))
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    text_body: Mapped[str] = mapped_column(Text, nullable=False)
    html_body: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
