from datetime import datetime

from pydantic import BaseModel, Field


class AuditEventRead(BaseModel):
    id: int
    company_id: int | None = None
    user_id: int | None = None
    user_name: str | None = None
    user_email: str | None = None
    module: str
    action: str
    entity_type: str
    entity_id: str | None = None
    entity_label: str | None = None
    description: str
    event_metadata: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditEventList(BaseModel):
    total: int
    items: list[AuditEventRead] = Field(default_factory=list)
