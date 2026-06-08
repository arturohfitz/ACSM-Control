from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import TimestampRead


NotificationCategory = Literal["task", "deadline", "warning", "info", "exception"]
NotificationPriority = Literal["low", "normal", "high", "critical"]
NotificationStatus = Literal["unread", "read", "resolved", "dismissed"]


class NotificationRead(TimestampRead):
    id: int
    company_id: int
    user_id: int
    client_id: int | None = None
    project_id: int | None = None
    notification_type: str
    title: str
    body: str
    category: NotificationCategory
    priority: NotificationPriority
    status: NotificationStatus
    source_module: str
    entity_type: str | None = None
    entity_id: str | None = None
    entity_label: str | None = None
    action_url: str | None = None
    event_metadata: dict | None = None
    due_at: datetime | None = None
    read_at: datetime | None = None
    resolved_at: datetime | None = None


class NotificationCountRead(BaseModel):
    unread: int = Field(ge=0)
    open: int = Field(ge=0)


class NotificationBulkRead(BaseModel):
    updated: int = Field(ge=0)
