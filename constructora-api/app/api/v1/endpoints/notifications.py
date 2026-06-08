from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Notification, Project, User, UserClientAccess
from app.schemas.notification import NotificationBulkRead, NotificationCountRead, NotificationRead
from app.services.notifications import sync_operational_notifications


router = APIRouter()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _scope_notification_statement(statement, current_user: User):
    if current_user.is_master_admin or current_user.client_access_mode != "restricted":
        return statement
    allowed_clients = select(UserClientAccess.client_id).where(
        UserClientAccess.user_id == current_user.id,
        UserClientAccess.company_id == current_user.company_id,
    )
    allowed_projects = select(Project.id).where(Project.client_id.in_(allowed_clients))
    return statement.where(
        or_(
            Notification.client_id.in_(allowed_clients),
            Notification.project_id.in_(allowed_projects),
            and_(Notification.client_id.is_(None), Notification.project_id.is_(None)),
        )
    )


def _notification_for_user(db: Session, notification_id: int, current_user: User) -> Notification:
    statement = _scope_notification_statement(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        ),
        current_user,
    )
    notification = db.scalar(statement)
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notificacion no encontrada")
    return notification


@router.get("", response_model=list[NotificationRead])
def list_notifications(
    status_filter: str = "open",
    limit: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Notification]:
    if current_user.company_id is not None:
        sync_operational_notifications(db, company_id=current_user.company_id)
        db.commit()

    statement = _scope_notification_statement(
        select(Notification).where(Notification.user_id == current_user.id),
        current_user,
    )
    if status_filter == "open":
        statement = statement.where(Notification.status.in_(("unread", "read")))
    elif status_filter != "all":
        statement = statement.where(Notification.status == status_filter)
    return list(
        db.scalars(
            statement.order_by(
                case(
                    (Notification.priority == "critical", 4),
                    (Notification.priority == "high", 3),
                    (Notification.priority == "normal", 2),
                    else_=1,
                ).desc(),
                Notification.created_at.desc(),
            ).limit(min(max(limit, 1), 100))
        ).all()
    )


@router.get("/counts", response_model=NotificationCountRead)
def notification_counts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NotificationCountRead:
    if current_user.company_id is not None:
        sync_operational_notifications(db, company_id=current_user.company_id)
        db.commit()

    unread_statement = _scope_notification_statement(
        select(func.count(Notification.id)).where(
            Notification.user_id == current_user.id,
            Notification.status == "unread",
        ),
        current_user,
    )
    open_statement = _scope_notification_statement(
        select(func.count(Notification.id)).where(
            Notification.user_id == current_user.id,
            Notification.status.in_(("unread", "read")),
        ),
        current_user,
    )
    unread = db.scalar(unread_statement) or 0
    open_count = db.scalar(open_statement) or 0
    return NotificationCountRead(unread=unread, open=open_count)


@router.post("/{notification_id}/read", response_model=NotificationRead)
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Notification:
    notification = _notification_for_user(db, notification_id, current_user)
    if notification.status == "unread":
        notification.status = "read"
        notification.read_at = _now()
    db.commit()
    db.refresh(notification)
    return notification


@router.post("/{notification_id}/resolve", response_model=NotificationRead)
def resolve_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Notification:
    notification = _notification_for_user(db, notification_id, current_user)
    notification.status = "resolved"
    notification.resolved_at = _now()
    if notification.read_at is None:
        notification.read_at = notification.resolved_at
    db.commit()
    db.refresh(notification)
    return notification


@router.post("/mark-all-read", response_model=NotificationBulkRead)
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NotificationBulkRead:
    now = _now()
    updated = 0
    notifications = db.scalars(
        _scope_notification_statement(
            select(Notification).where(
                Notification.user_id == current_user.id,
                Notification.status == "unread",
            ),
            current_user,
        )
    ).all()
    for notification in notifications:
        notification.status = "read"
        notification.read_at = now
        updated += 1
    db.commit()
    return NotificationBulkRead(updated=updated)
