from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Notification(TimestampMixin, Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    notification_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(40), default="task", nullable=False, index=True)
    priority: Mapped[str] = mapped_column(String(20), default="normal", nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="unread", nullable=False, index=True)
    source_module: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(120), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(80), index=True)
    entity_label: Mapped[str | None] = mapped_column(String(255))
    action_url: Mapped[str | None] = mapped_column(String(255))
    event_metadata: Mapped[dict | None] = mapped_column(JSON)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship()
