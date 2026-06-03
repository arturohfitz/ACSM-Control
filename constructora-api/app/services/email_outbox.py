import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import EmailOutboxMessage, SupplierRFQSupplier, SystemEmailSettings
from app.services.emailer import send_email


logger = logging.getLogger(__name__)


def queue_email(
    db: Session,
    *,
    company_id: int,
    recipient_email: str,
    subject: str,
    text_body: str,
    html_body: str | None = None,
    message_type: str = "general",
    related_entity_type: str | None = None,
    related_entity_id: str | int | None = None,
    recipient_name: str | None = None,
    requested_by: int | None = None,
) -> EmailOutboxMessage:
    message = EmailOutboxMessage(
        company_id=company_id,
        requested_by=requested_by,
        message_type=message_type,
        related_entity_type=related_entity_type,
        related_entity_id=str(related_entity_id) if related_entity_id is not None else None,
        recipient_email=recipient_email.strip(),
        recipient_name=recipient_name,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        status="pending",
        attempts=0,
        max_attempts=3,
        next_attempt_at=datetime.now(timezone.utc),
    )
    db.add(message)
    return message


def has_active_or_sent_message(
    db: Session,
    *,
    related_entity_type: str,
    related_entity_id: str | int,
    recipient_email: str,
) -> bool:
    return (
        db.scalar(
            select(EmailOutboxMessage.id)
            .where(
                EmailOutboxMessage.related_entity_type == related_entity_type,
                EmailOutboxMessage.related_entity_id == str(related_entity_id),
                EmailOutboxMessage.recipient_email == recipient_email.strip(),
                or_(
                    EmailOutboxMessage.status.in_(("pending", "sent")),
                    and_(
                        EmailOutboxMessage.status == "error",
                        EmailOutboxMessage.attempts < EmailOutboxMessage.max_attempts,
                    ),
                ),
            )
            .limit(1)
        )
        is not None
    )


def send_outbox_message(db: Session, message: EmailOutboxMessage) -> None:
    settings = db.scalar(
        select(SystemEmailSettings).where(
            SystemEmailSettings.company_id == message.company_id,
            SystemEmailSettings.is_active.is_(True),
        )
    )
    message.attempts += 1
    if settings is None:
        message.status = "error"
        message.last_error = "Falta configurar SMTP activo para la empresa."
        message.next_attempt_at = _next_attempt(message.attempts, message.max_attempts)
        _sync_related_entity(db, message)
        return

    try:
        send_email(
            settings=settings,
            recipients=[message.recipient_email],
            subject=message.subject,
            text_body=message.text_body,
            html_body=message.html_body,
        )
    except Exception as exc:
        logger.exception("No fue posible enviar correo outbox %s", message.id)
        message.status = "error"
        message.last_error = str(exc)
        message.next_attempt_at = _next_attempt(message.attempts, message.max_attempts)
        _sync_related_entity(db, message)
        return

    message.status = "sent"
    message.last_error = None
    message.next_attempt_at = None
    message.sent_at = datetime.now(timezone.utc)
    _sync_related_entity(db, message)


def process_pending_email_outbox(
    db: Session,
    *,
    company_id: int | None = None,
    limit: int = 50,
) -> dict[str, int]:
    now = datetime.now(timezone.utc)
    statement = (
        select(EmailOutboxMessage)
        .where(
            EmailOutboxMessage.status.in_(("pending", "error")),
            EmailOutboxMessage.attempts < EmailOutboxMessage.max_attempts,
            (EmailOutboxMessage.next_attempt_at.is_(None) | (EmailOutboxMessage.next_attempt_at <= now)),
        )
        .order_by(EmailOutboxMessage.created_at)
        .limit(limit)
    )
    if company_id is not None:
        statement = statement.where(EmailOutboxMessage.company_id == company_id)

    messages = list(db.scalars(statement).all())
    result = {"procesados": 0, "enviados": 0, "errores": 0}
    for message in messages:
        before_status = message.status
        send_outbox_message(db, message)
        result["procesados"] += 1
        if message.status == "sent":
            result["enviados"] += 1
        elif before_status != "sent":
            result["errores"] += 1
    db.commit()
    return result


def process_email_outbox_for_company(company_id: int, limit: int = 50) -> None:
    with SessionLocal() as db:
        process_pending_email_outbox(db, company_id=company_id, limit=limit)


def _next_attempt(attempts: int, max_attempts: int) -> datetime | None:
    if attempts >= max_attempts:
        return None
    return datetime.now(timezone.utc) + timedelta(minutes=2**attempts)


def _sync_related_entity(db: Session, message: EmailOutboxMessage) -> None:
    if message.related_entity_type != "SupplierRFQSupplier" or not message.related_entity_id:
        return
    link = db.get(SupplierRFQSupplier, int(message.related_entity_id))
    if link is None:
        return
    if message.status == "sent":
        link.status = "sent"
        link.sent_at = message.sent_at
        link.notes = None
        return
    if message.status == "error" and message.attempts >= message.max_attempts:
        link.status = "email_error"
        link.notes = message.last_error
    elif message.status == "error":
        link.status = "queued"
        link.notes = f"Reintentando envio: {message.last_error}"
