from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import logging
from typing import Iterable

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Notification,
    Permission,
    Project,
    PurchaseOrder,
    Role,
    RolePermission,
    SupplierInvoice,
    SupplierInvoiceItem,
    User,
    UserRole,
)
from app.services.tenancy import user_can_access_client_id


OPEN_STATUSES = {"unread", "read"}
ALLOWED_CATEGORIES = {"task", "deadline", "warning", "info", "exception"}
ALLOWED_PRIORITIES = {"low", "normal", "high", "critical"}
logger = logging.getLogger(__name__)


def _safe_category(value: str) -> str:
    return value if value in ALLOWED_CATEGORIES else "info"


def _safe_priority(value: str) -> str:
    return value if value in ALLOWED_PRIORITIES else "normal"


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
    include_master_admin: bool = False,
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

    company_scope = User.company_id == company_id
    if include_master_admin:
        company_scope = or_(
            company_scope,
            and_(User.is_master_admin.is_(True), User.company_id.is_(None)),
        )
    statement = (
        select(User)
        .where(User.is_active.is_(True), company_scope)
        .options(selectinload(User.roles), selectinload(User.user_client_accesses))
    )
    if role_ids:
        role_user_filter = User.id.in_(
            select(UserRole.user_id).where(UserRole.role_id.in_(role_ids))
        )
        if include_master_admin:
            statement = statement.where(or_(User.is_master_admin.is_(True), role_user_filter))
        else:
            statement = statement.where(User.is_master_admin.is_(False), role_user_filter)
    else:
        statement = statement.where(User.is_master_admin.is_(True) if include_master_admin else False)

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
    client_id: int | None = None,
    project_id: int | None = None,
    category: str = "task",
    priority: str = "normal",
    entity_type: str | None = None,
    entity_id: int | str | None = None,
    entity_label: str | None = None,
    action_url: str | None = None,
    metadata: dict | None = None,
    due_at: datetime | None = None,
) -> Notification | None:
    category = _safe_category(category)
    priority = _safe_priority(priority)
    if project_id is not None and client_id is None:
        client_id = db.scalar(select(Project.client_id).where(Project.id == project_id))
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
        existing.client_id = client_id
        existing.project_id = project_id
        existing.entity_label = entity_label
        existing.action_url = action_url
        existing.event_metadata = metadata
        existing.due_at = due_at
        return existing

    notification = Notification(
        company_id=company_id,
        user_id=user_id,
        client_id=client_id,
        project_id=project_id,
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
    *,
    enforce_client_access: bool = True,
    **kwargs,
) -> int:
    count = 0
    client_id = kwargs.get("client_id")
    project_id = kwargs.get("project_id")
    if project_id is not None and client_id is None:
        client_id = db.scalar(select(Project.client_id).where(Project.id == project_id))
        kwargs["client_id"] = client_id
    for user in users:
        if enforce_client_access and not user_can_access_client_id(user, client_id):
            continue
        if create_notification(db, user_id=user.id, **kwargs) is not None:
            count += 1
    return count


def notify_permission(
    db: Session,
    *,
    company_id: int,
    module: str,
    action: str,
    include_master_admin: bool = False,
    fallback_to_master_admin: bool = True,
    enforce_client_access: bool = True,
    **kwargs,
) -> int:
    count = notify_users(
        db,
        users_with_permission(
            db,
            company_id=company_id,
            module=module,
            action=action,
            include_master_admin=include_master_admin,
        ),
        enforce_client_access=enforce_client_access,
        company_id=company_id,
        **kwargs,
    )
    if count or include_master_admin or not fallback_to_master_admin:
        return count

    fallback_users = list(
        db.scalars(
            select(User)
            .where(
                User.is_active.is_(True),
                User.is_master_admin.is_(True),
                or_(User.company_id == company_id, User.company_id.is_(None)),
            )
            .options(selectinload(User.roles), selectinload(User.user_client_accesses))
        ).unique().all()
    )
    if not fallback_users:
        logger.error(
            "Notification %s has no recipients for %s:%s in company %s",
            kwargs.get("notification_type", "unknown"),
            module,
            action,
            company_id,
        )
        return 0

    fallback_kwargs = dict(kwargs)
    metadata = dict(fallback_kwargs.get("metadata") or {})
    metadata["notification_routing"] = {
        "fallback": "master_admin",
        "permission": f"{module}:{action}",
    }
    fallback_kwargs["metadata"] = metadata
    logger.warning(
        "Notification %s routed to master admin fallback for %s:%s in company %s",
        kwargs.get("notification_type", "unknown"),
        module,
        action,
        company_id,
    )
    return notify_users(
        db,
        fallback_users,
        enforce_client_access=enforce_client_access,
        company_id=company_id,
        **fallback_kwargs,
    )


def notify_user_id(db: Session, *, user_id: int | None, company_id: int, **kwargs) -> int:
    if user_id is None:
        return 0
    user = db.scalar(
        select(User)
        .where(User.id == user_id, User.is_active.is_(True))
        .options(selectinload(User.user_client_accesses))
    )
    if user is None or user.company_id != company_id:
        return 0
    client_id = kwargs.get("client_id")
    project_id = kwargs.get("project_id")
    if project_id is not None and client_id is None:
        client_id = db.scalar(select(Project.client_id).where(Project.id == project_id))
        kwargs["client_id"] = client_id
    if not user_can_access_client_id(user, client_id):
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
    _sync_purchase_order_workflow_notifications(db, company_id=company_id)
    _sync_invoice_due_notifications(db, company_id=company_id)
    _sync_incomplete_purchase_order_notifications(db, company_id=company_id)


def _active_invoice_count(db: Session, purchase_order_id: int) -> int:
    return int(
        db.scalar(
            select(func.count(SupplierInvoice.id)).where(
                SupplierInvoice.purchase_order_id == purchase_order_id,
                SupplierInvoice.status.notin_(("rejected", "cancelled")),
            )
        )
        or 0
    )


def _uninvoiced_received_items(db: Session, purchase_order: PurchaseOrder) -> int:
    if not purchase_order.items:
        return 0
    if purchase_order.billing_mode != "partial":
        complete = all(
            item.received_quantity >= item.quantity_ordered for item in purchase_order.items
        )
        return (
            len(purchase_order.items)
            if complete and not _active_invoice_count(db, purchase_order.id)
            else 0
        )

    invoiced_rows = db.execute(
        select(
            SupplierInvoiceItem.purchase_order_item_id,
            func.coalesce(func.sum(SupplierInvoiceItem.quantity), Decimal("0")),
        )
        .join(SupplierInvoice, SupplierInvoice.id == SupplierInvoiceItem.supplier_invoice_id)
        .where(
            SupplierInvoice.purchase_order_id == purchase_order.id,
            SupplierInvoice.status.notin_(("rejected", "cancelled")),
        )
        .group_by(SupplierInvoiceItem.purchase_order_item_id)
    ).all()
    invoiced_by_item = {item_id: Decimal(quantity) for item_id, quantity in invoiced_rows}
    return sum(
        1
        for item in purchase_order.items
        if min(Decimal(item.received_quantity), Decimal(item.quantity_ordered))
        > invoiced_by_item.get(item.id, Decimal("0"))
    )


def sync_purchase_order_invoice_readiness(
    db: Session,
    *,
    purchase_order: PurchaseOrder,
) -> int:
    available_items = _uninvoiced_received_items(db, purchase_order)
    notification_types = (
        "purchase_order_partial_ready_for_invoice",
        "purchase_order_ready_for_invoice",
    )
    if not available_items:
        return sum(
            resolve_notifications(
                db,
                company_id=purchase_order.company_id,
                notification_type=notification_type,
                entity_type="PurchaseOrder",
                entity_id=purchase_order.id,
            )
            for notification_type in notification_types
        )

    complete = bool(purchase_order.items) and all(
        item.received_quantity >= item.quantity_ordered for item in purchase_order.items
    )
    notification_type = (
        "purchase_order_ready_for_invoice"
        if complete
        else "purchase_order_partial_ready_for_invoice"
    )
    alternate_type = next(item for item in notification_types if item != notification_type)
    resolve_notifications(
        db,
        company_id=purchase_order.company_id,
        notification_type=alternate_type,
        entity_type="PurchaseOrder",
        entity_id=purchase_order.id,
    )
    supplier_name = purchase_order.supplier.name if purchase_order.supplier else "Proveedor"
    return notify_permission(
        db,
        company_id=purchase_order.company_id,
        module="supplier_invoices",
        action="upload",
        notification_type=notification_type,
        title=(
            "Orden recibida: registra la factura"
            if complete
            else "Entrega parcial disponible para facturar"
        ),
        body=(
            f"{purchase_order.po_number} de {supplier_name} fue recibida por completo. "
            "Captura el PDF o XML de la factura para continuar."
            if complete
            else (
                f"{purchase_order.po_number} de {supplier_name} tiene {available_items} "
                "partida(s) recibida(s) todavia no facturada(s)."
            )
        ),
        category="task",
        priority="high" if complete else "normal",
        source_module="pagos_proveedores",
        project_id=purchase_order.project_id,
        entity_type="PurchaseOrder",
        entity_id=purchase_order.id,
        entity_label=purchase_order.po_number,
        action_url=(
            "/supplier-payments?view=invoices"
            f"&project_id={purchase_order.project_id}"
            f"&purchase_order_id={purchase_order.id}"
            "&focus=invoice-registration"
        ),
        metadata={
            "purchase_order_id": purchase_order.id,
            "supplier_id": purchase_order.supplier_id,
            "available_items": available_items,
            "billing_mode": purchase_order.billing_mode,
            "receipt_complete": complete,
        },
    )


def _sync_purchase_order_workflow_notifications(db: Session, *, company_id: int) -> None:
    purchase_orders = list(
        db.scalars(
            select(PurchaseOrder)
            .where(
                PurchaseOrder.company_id == company_id,
                PurchaseOrder.status.in_(
                    ("sent", "partially_received", "received", "factured", "closed")
                ),
            )
            .options(selectinload(PurchaseOrder.supplier), selectinload(PurchaseOrder.items))
        ).unique().all()
    )
    for purchase_order in purchase_orders:
        pending_items = [
            item
            for item in purchase_order.items
            if item.received_quantity < item.quantity_ordered
        ]
        if pending_items and purchase_order.status in {"sent", "partially_received"}:
            notify_permission(
                db,
                company_id=company_id,
                module="inventory_receiving",
                action="receive",
                notification_type="purchase_order_ready_to_receive",
                title="Material pendiente de recibir",
                body=(
                    f"{purchase_order.po_number} tiene {len(pending_items)} "
                    "partida(s) esperadas en Inventario."
                ),
                category="task",
                priority="normal",
                source_module="inventario",
                project_id=purchase_order.project_id,
                entity_type="PurchaseOrder",
                entity_id=purchase_order.id,
                entity_label=purchase_order.po_number,
                action_url=(
                    "/inventory/material-receiving?type=oc"
                    f"&project_id={purchase_order.project_id}"
                    f"&purchase_order_id={purchase_order.id}"
                    + (
                        f"&warehouse_id={purchase_order.warehouse_id}"
                        if purchase_order.warehouse_id is not None
                        else ""
                    )
                ),
                metadata={
                    "purchase_order_id": purchase_order.id,
                    "warehouse_id": purchase_order.warehouse_id,
                    "pending_items": len(pending_items),
                    "recovered_from_state": True,
                },
            )
        else:
            resolve_notifications(
                db,
                company_id=company_id,
                notification_type="purchase_order_ready_to_receive",
                entity_type="PurchaseOrder",
                entity_id=purchase_order.id,
            )
        sync_purchase_order_invoice_readiness(db, purchase_order=purchase_order)


def _sync_invoice_due_notifications(db: Session, *, company_id: int) -> None:
    today = date.today()
    warning_day = today + timedelta(days=7)
    invoices = db.scalars(
        select(SupplierInvoice)
        .where(
            SupplierInvoice.company_id == company_id,
            SupplierInvoice.status.notin_(("paid", "rejected", "cancelled")),
            SupplierInvoice.due_date <= warning_day,
        )
        .options(selectinload(SupplierInvoice.supplier), selectinload(SupplierInvoice.purchase_order))
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
            project_id=invoice.purchase_order.project_id if invoice.purchase_order else None,
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
            PurchaseOrder.status.in_(("sent", "partially_received")),
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
            module="inventory_receiving",
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
            project_id=purchase_order.project_id,
            entity_type="PurchaseOrder",
            entity_id=purchase_order.id,
            entity_label=purchase_order.po_number,
            action_url=(
                "/inventory/material-receiving?type=oc"
                f"&project_id={purchase_order.project_id}"
                f"&purchase_order_id={purchase_order.id}"
                + (
                    f"&warehouse_id={purchase_order.warehouse_id}"
                    if purchase_order.warehouse_id is not None
                    else ""
                )
            ),
            due_at=_day_to_datetime(purchase_order.issued_at),
            metadata={
                "purchase_order_id": purchase_order.id,
                "warehouse_id": purchase_order.warehouse_id,
                "pending_items": len(pending_items),
                "pending_quantity": str(pending_qty),
            },
        )
