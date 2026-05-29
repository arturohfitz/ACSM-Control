from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models import SystemEmailSettings, User
from app.schemas.system_settings import EmailSettingsRead, EmailSettingsUpsert, EmailTestRequest, EmailTestResult
from app.services.emailer import send_email
from app.services.tenancy import company_id_for_write, get_user_company_id


router = APIRouter()


def _company_id(current_user: User, requested_company_id: int | None = None) -> int:
    if current_user.is_master_admin and requested_company_id is not None:
        return requested_company_id
    return get_user_company_id(current_user)


def _serialize(settings: SystemEmailSettings) -> EmailSettingsRead:
    return EmailSettingsRead(
        id=settings.id,
        company_id=settings.company_id,
        sender_name=settings.sender_name,
        sender_email=settings.sender_email,
        reply_to_email=settings.reply_to_email,
        smtp_host=settings.smtp_host,
        smtp_port=settings.smtp_port,
        smtp_username=settings.smtp_username,
        smtp_password_set=bool(settings.smtp_password),
        smtp_use_ssl=settings.smtp_use_ssl,
        smtp_use_tls=settings.smtp_use_tls,
        imap_host=settings.imap_host,
        imap_port=settings.imap_port,
        imap_username=settings.imap_username,
        imap_password_set=bool(settings.imap_password),
        is_active=settings.is_active,
        last_tested_at=settings.last_tested_at,
        last_test_status=settings.last_test_status,
        last_test_message=settings.last_test_message,
        created_at=settings.created_at,
        updated_at=settings.updated_at,
    )


@router.get("/email", response_model=EmailSettingsRead | None)
def get_email_settings(
    company_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings", "view")),
) -> EmailSettingsRead | None:
    target_company_id = _company_id(current_user, company_id)
    settings = db.scalar(
        select(SystemEmailSettings).where(SystemEmailSettings.company_id == target_company_id)
    )
    return _serialize(settings) if settings else None


@router.put("/email", response_model=EmailSettingsRead)
def upsert_email_settings(
    payload: EmailSettingsUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings", "view")),
) -> EmailSettingsRead:
    target_company_id = company_id_for_write(current_user, payload.company_id)
    settings = db.scalar(
        select(SystemEmailSettings).where(SystemEmailSettings.company_id == target_company_id)
    )
    data = payload.model_dump(exclude={"company_id"})
    if settings is None:
        settings = SystemEmailSettings(company_id=target_company_id, **data)
        db.add(settings)
    else:
        for key, value in data.items():
            if key in {"smtp_password", "imap_password"} and value in {None, ""}:
                continue
            setattr(settings, key, value)
    db.commit()
    db.refresh(settings)
    return _serialize(settings)


@router.post("/email/test", response_model=EmailTestResult)
def test_email_settings(
    payload: EmailTestRequest,
    company_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings", "view")),
) -> EmailTestResult:
    target_company_id = _company_id(current_user, company_id)
    settings = db.scalar(
        select(SystemEmailSettings).where(SystemEmailSettings.company_id == target_company_id)
    )
    if settings is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Configura el correo antes de probar el envio",
        )

    recipient = str(payload.recipient_email or settings.sender_email)
    try:
        send_email(
            settings=settings,
            recipients=[recipient],
            subject="Prueba de correo ACSM Control",
            text_body="Esta es una prueba de configuracion de correo desde ACSM Control.",
            html_body="<p>Esta es una prueba de configuracion de correo desde <strong>ACSM Control</strong>.</p>",
        )
    except Exception as exc:
        settings.last_test_status = "error"
        settings.last_test_message = str(exc)
        settings.last_tested_at = datetime.now(timezone.utc)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No fue posible enviar el correo de prueba: {exc}",
        ) from exc

    settings.last_test_status = "ok"
    settings.last_test_message = f"Correo de prueba enviado a {recipient}"
    settings.last_tested_at = datetime.now(timezone.utc)
    db.commit()
    return EmailTestResult(ok=True, message=settings.last_test_message)
