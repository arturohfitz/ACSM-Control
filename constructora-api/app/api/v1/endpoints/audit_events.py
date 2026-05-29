from fastapi import APIRouter, Depends
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models import AuditEvent, User
from app.schemas.audit import AuditEventList, AuditEventRead
from app.services.tenancy import scoped_select


router = APIRouter()


@router.get("", response_model=AuditEventList)
def list_audit_events(
    skip: int = 0,
    limit: int = 100,
    module: str | None = None,
    action: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("events", "view")),
) -> AuditEventList:
    statement = scoped_select(select(AuditEvent), AuditEvent, current_user)
    count_statement = scoped_select(select(func.count(AuditEvent.id)), AuditEvent, current_user)

    filters = []
    if module:
        filters.append(AuditEvent.module == module)
    if action:
        filters.append(AuditEvent.action == action)
    if search:
        like = f"%{search.strip()}%"
        filters.append(
            or_(
                AuditEvent.description.ilike(like),
                AuditEvent.entity_label.ilike(like),
                AuditEvent.user_email.ilike(like),
                AuditEvent.user_name.ilike(like),
            )
        )
    if filters:
        statement = statement.where(*filters)
        count_statement = count_statement.where(*filters)

    total = db.scalar(count_statement) or 0
    items = list(
        db.scalars(
            statement.order_by(AuditEvent.created_at.desc()).offset(skip).limit(limit)
        ).all()
    )
    return AuditEventList(total=total, items=[AuditEventRead.model_validate(item) for item in items])
