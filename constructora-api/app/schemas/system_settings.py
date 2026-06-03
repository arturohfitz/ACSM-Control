from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import TimestampRead


class EmailSettingsUpsert(BaseModel):
    company_id: int | None = None
    sender_name: str = Field(default="ACSM Control", min_length=1, max_length=160)
    sender_email: EmailStr
    reply_to_email: EmailStr | None = None
    smtp_host: str = Field(min_length=1, max_length=255)
    smtp_port: int = Field(default=465, ge=1, le=65535)
    smtp_username: str = Field(min_length=1, max_length=255)
    smtp_password: str | None = None
    smtp_use_ssl: bool = True
    smtp_use_tls: bool = False
    imap_host: str | None = Field(default=None, max_length=255)
    imap_port: int | None = Field(default=None, ge=1, le=65535)
    imap_username: str | None = Field(default=None, max_length=255)
    imap_password: str | None = None
    is_active: bool = True


class EmailSettingsRead(TimestampRead):
    id: int
    company_id: int
    sender_name: str
    sender_email: str
    reply_to_email: str | None = None
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password_set: bool
    smtp_use_ssl: bool
    smtp_use_tls: bool
    imap_host: str | None = None
    imap_port: int | None = None
    imap_username: str | None = None
    imap_password_set: bool
    is_active: bool
    last_tested_at: datetime | None = None
    last_test_status: str | None = None
    last_test_message: str | None = None


class EmailTestRequest(BaseModel):
    recipient_email: EmailStr | None = None


class EmailTestResult(BaseModel):
    ok: bool
    message: str


class EmailOutboxMessageRead(TimestampRead):
    id: int
    company_id: int
    requested_by: int | None = None
    message_type: str
    related_entity_type: str | None = None
    related_entity_id: str | None = None
    recipient_email: str
    recipient_name: str | None = None
    subject: str
    status: str
    attempts: int
    max_attempts: int
    last_error: str | None = None
    next_attempt_at: datetime | None = None
    sent_at: datetime | None = None


class EmailOutboxProcessResult(BaseModel):
    procesados: int
    enviados: int
    errores: int
