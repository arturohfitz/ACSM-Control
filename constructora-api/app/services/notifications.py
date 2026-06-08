from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Iterable

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Notification,
    Permission,
    PurchaseOrder,
    Role,
    RolePermission,
    SupplierInvoice,
    User,
    UserRole,
)


OPEN_STATUSES = {"unread", "read"}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _day_to_datetime(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def users_with_permission(
    db: Session,
    *,
    company_id: int,
    module: str,
    action: str,
) -> list[User]:
    permission = db.scalar(
        select(Permission).where(Permission.module == module, Permission.action == action)
    )
    role_ids: list[int] = []
    if permission is not None:
        role_ids = list(
            db.scalars(
                select(RolePermission.role_id).where(RolePermission.permission_id == permission.id)
            ).all()
        )

    statement = (
        select(User)
        .where(User.is_active.is_(True), User.company_id == company_id)
        .options(selectinload(User.roles))
    )
    if role_ids:
        statement = statement.where(
            or_(
                User.is_master_admin.is_(True),
                User.id.in_(
                    select(UserRole.user_id).where(UserRole.role_id.in_(role_ids))
                ),
            )
        )
    else:
        statement = statement.where(User.is_master_admin.is_(True))

    users = list(db.scalars(statement).unique().all())
    return users


def create_notification(
    db: Session,
    *,
    company_id: int,
    user_id: int,
    notification_type: str,
    title: str,
    body: str,
    source_module: str,
    category: str = "task",
    priority: str = "normal",
    entity_type: str | None = None,
    entity_id: int | str | None = None,
    entity_label: str | None = None,
    action_url: str | None = None,
    metadata: dict | None = None,
    due_at: datetime | None = None,
) -> Notification | None:
    entity_id_text = str(entity_id) if entity_id is not None else None
    existing = db.scalar(
        select(Notification).where(
            Notification.company_id == company_id,
            Notification.user_id == user_id,
            Notification.notification_type == notification_type,
            Notification.entity_type == entity_type,
            Notification.entity_id == entity_id_text,
            Notification.status.in_(OPEN_STATUSES),
        )
    )
    if existing is not None:
        existing.title = title
        existing.body = body
        existing.category = category
        existing.priority = priority
        existing.source_module = source_module
        existing.entity_label = entity_label
        existing.action_url = action_url
        existing.event_metadata = metadata
        existing.due_at = due_at
        return existing

    notification = Notification(
        company_id=company_id,
        user_id=user_id,
        notification_type=notification_type,
        title=title,
        body=body,
        category=category,
        priority=priority,
        status="unread",
        source_module=source_module,
        entity_type=entity_type,
        entity_id=entity_id_text,
        entity_label=entity_label,
        action_url=action_url,
        event_metadata=metadata,
        due_at=due_at,
    )
    db.add(notification)
    return notification


def notify_users(
    db: Session,
    users: Iterable[User],
    **kwargs,
) -> int:
    count = 0
    for user in users:
        if create_notification(db, user_id=user.id, **kwargs) is not None:
            count += 1
    return count


def notify_permission(
    db: Session,
    *,
    company_id: int,
    module: str,
    action: str,
    **kwargs,
) -> int:
    return notify_users(
        db,
        users_with_permission(db, company_id=company_id, module=module, action=action),
        company_id=company_id,
        **kwargs,
    )


def notify_user_id(db: Session, *, user_id: int | None, company_id: int, **kwargs) -> int:
    if user_id is None:
        return 0
    user = db.scalar(select(User).where(User.id == user_id, User.is_active.is_(True)))
    if user is None or user.company_id != company_id:
        return 0
    return 1 if create_notification(db, user_id=user.id, company_id=company_id, **kwargs) else 0


def resolve_notifications(
    db: Session,
    *,
    company_id: int,
    notification_type: str | None = None,
    entity_type: str | None = None,
    entity_id: int | str | None = None,
) -> int:
    statement = select(Notification).where(
        Notification.company_id == company_id,
        Notification.status.in_(OPEN_STATUSES),
    )
    if notification_type is not None:
        statement = statement.where(Notification.notification_type == notification_type)
    if entity_type is not None:
        statement = statement.where(Notification.entity_type == entity_type)
    if entity_id is not None:
        statement = statement.where(Notification.entity_id == str(entity_id))

    resolved_at = now_utc()
    count = 0
    for notification in db.scalars(statement).all():
        notification.status = "resolved"
        notification.resolved_at = resolved_at
        count += 1
    return count


def sync_operational_notifications(db: Session, *, company_id: int) -> None:
    _sync_invoice_due_notifications(db, company_id=company_id)
    _sync_incomplete_purchase_order_notifications(db, company_id=company_id)


def _sync_invoice_due_notifications(db: Session, *, company_id: int) -> None:
    today = date.today()
    warning_day = today + timedelta(days=7)
    invoices = db.scalars(
        select(SupplierInvoice)
        .where(
            SupplierInvoice.company_id == company_id,
            SupplierInvoice.status.notin_(("paid", "rejected")),
            SupplierInvoice.due_date <= warning_day,
        )
        .options(selectinload(SupplierInvoice.supplier))
    ).all()
    for invoice in invoices:
        days = (invoice.due_date - today).days
        if days < 0:
            title = "Factura vencida"
            priority = "critical"
            body = f"{invoice.invoice_number} vencio hace {abs(days)} dia(s)."
        elif days == 0:
            title = "Factura vence hoy"
            priority = "high"
            body = f"{invoice.invoice_number} vence hoy."
        else:
            title = "Factura por vencer"
            priority = "normal" if days > 3 else "high"
            body = f"{invoice.invoice_number} vence en {days} dia(s)."
        if invoice.supplier:
            body = f"{body} Proveedor: {invoice.supplier.name}."
        notify_permission(
            db,
            company_id=company_id,
            module="supplier_payments",
            action="view",
            notification_type="supplier_invoice_due",
            title=title,
            body=body,
            category="deadline",
            priority=priority,
            source_module="pagos_proveedores",
            entity_type="SupplierInvoice",
            entity_id=invoice.id,
            entity_label=invoice.invoice_number,
            action_url="/supplier-payments",
            due_at=_day_to_datetime(invoice.due_date),
            metadata={"due_date": invoice.due_date.isoformat(), "total": str(invoice.total)},
        )


def _sync_incomplete_purchase_order_notifications(db: Session, *, company_id: int) -> None:
    today = date.today()
    purchase_orders = db.scalars(
        select(PurchaseOrder)
        .where(
            PurchaseOrder.company_id == company_id,
            PurchaseOrder.status.in_(("issued", "sent", "partially_received")),
            PurchaseOrder.issued_at <= today - timedelta(days=3),
        )
        .options(selectinload(PurchaseOrder.supplier), selectinload(PurchaseOrder.items))
    ).all()
    for purchase_order in purchase_orders:
        pending_items = [
            item
            for item in purchase_order.items
            if item.received_quantity < item.quantity_ordered
        ]
        if not pending_items:
            resolve_notifications(
                db,
                company_id=company_id,
                notification_type="purchase_order_incomplete",
                entity_type="PurchaseOrder",
                entity_id=purchase_order.id,
            )
            continue
        pending_qty = sum(
            (item.quantity_ordered - item.received_quantity for item in pending_items),
            Decimal("0"),
        )
        supplier_name = purchase_order.supplier.name if purchase_order.supplier else "Proveedor"
        notify_permission(
            db,
            company_id=company_id,
            module="inventory",
            action="receive",
            notification_type="purchase_order_incomplete",
            title="Orden con material pendiente",
            body=(
                f"{purchase_order.po_number} de {supplier_name} tiene "
                f"{len(pending_items)} partida(s) sin completar."
            ),
            category="warning",
            priority="high" if purchase_order.status == "partially_received" else "normal",
            source_module="inventario",
            entity_type="PurchaseOrder",
            entity_id=purchase_order.id,
            entity_label=purchase_order.po_number,
            action_url="/inventory/purchase-order-receiving",
            due_at=_day_to_datetime(purchase_order.issued_at),
            metadata={"pending_items": len(pending_items), "pending_quantity": str(pending_qty)},
        )
