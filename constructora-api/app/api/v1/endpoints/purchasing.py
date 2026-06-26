import hashlib
import json
import secrets
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, require_permission
from app.core.config import settings
from app.db.session import get_db
from app.models import (
    Client,
    ExpectedMaterialItem,
    ExpectedMaterialList,
    HouseModel,
    Material,
    MaterialRequisition,
    Project,
    ProjectHouseModel,
    ProjectWarehouse,
    PurchaseOrder,
    PurchaseOrderItem,
    Supplier,
    SupplierAgreement,
    SupplierAgreementItem,
    SupplierInvoice,
    SupplierInvoiceItem,
    SupplierPayment,
    SupplierQuote,
    SupplierQuoteApproval,
    SupplierQuoteItem,
    SupplierQuoteUpload,
    SupplierRFQ,
    SupplierRFQExceptionRequest,
    SupplierRFQItem,
    SupplierRFQSupplier,
    User,
)
from app.schemas.purchasing import (
    PurchaseOrderApprovalRead,
    PurchaseOrderBillingModeUpdate,
    PurchaseOrderRead,
    SupplierAgreementCreate,
    SupplierAgreementEligibility,
    SupplierAgreementItemCreate,
    SupplierAgreementItemRead,
    SupplierAgreementItemUpdate,
    SupplierAgreementRead,
    SupplierAgreementUpdate,
    SupplierCreate,
    SupplierInvoiceCreate,
    SupplierInvoiceRead,
    SupplierInvoiceValidation,
    SupplierPaymentCreate,
    SupplierPaymentRead,
    SupplierPaymentUpdate,
    SupplierQuoteCreate,
    SupplierQuoteApprovalDecision,
    SupplierQuoteApprovalRead,
    SupplierQuoteApprovalRequest,
    SupplierQuoteRead,
    SupplierQuoteUploadRead,
    SupplierRFQApprovalRequest,
    SupplierRFQComparisonRow,
    SupplierRFQCreate,
    SupplierRFQExceptionCreate,
    SupplierRFQExceptionDecision,
    SupplierRFQExceptionRead,
    SupplierRFQRead,
    SupplierRFQUpdate,
    SupplierRead,
    SupplierUpdate,
    invoice_due_date,
)
from app.services.audit import record_create, record_delete, record_event, record_update, snapshot
from app.services.crud import get_or_404
from app.services.email_outbox import (
    has_active_or_sent_message,
    process_email_outbox_for_company,
    queue_email,
)
from app.services.emailer import purchase_order_email_content, rfq_email_content
from app.services.notifications import notify_permission, notify_user_id, resolve_notifications
from app.services.permissions import user_has_permission
from app.services.tenancy import company_id_for_write, ensure_same_company, scoped_select


router = APIRouter()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _project_for_user(db: Session, project_id: int, current_user: User) -> Project:
    project = get_or_404(db, Project, project_id)
    ensure_same_company(current_user, project, db=db)
    return project


def _supplier_for_user(db: Session, supplier_id: int, current_user: User) -> Supplier:
    supplier = get_or_404(db, Supplier, supplier_id)
    ensure_same_company(current_user, supplier, db=db)
    if supplier.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El proveedor no esta activo",
        )
    return supplier


def _agreement_options():
    return (
        selectinload(SupplierAgreement.supplier),
        selectinload(SupplierAgreement.client),
        selectinload(SupplierAgreement.house_model),
        selectinload(SupplierAgreement.items),
        selectinload(SupplierAgreement.creator),
        selectinload(SupplierAgreement.decider),
    )


def _validate_agreement_scope(
    db: Session,
    agreement: SupplierAgreement,
    project: Project,
    supplier_ids: list[int],
    items: list,
) -> None:
    today = date.today()
    if agreement.approval_status != "approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El convenio esta pendiente de autorizacion administrativa",
        )
    if agreement.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El convenio no esta activo",
        )
    if agreement.valid_from and agreement.valid_from > today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El convenio aun no inicia vigencia",
        )
    if agreement.valid_until and agreement.valid_until < today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El convenio esta vencido",
        )
    if agreement.client_id != project.client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El convenio no pertenece a la inmobiliaria del desarrollo seleccionado",
        )
    is_project_model = db.scalar(
        select(ProjectHouseModel.id).where(
            ProjectHouseModel.project_id == project.id,
            ProjectHouseModel.house_model_id == agreement.house_model_id,
        )
    )
    if is_project_model is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El modelo del convenio no esta asignado al desarrollo seleccionado",
        )
    if len(set(supplier_ids)) != 1 or supplier_ids[0] != agreement.supplier_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La solicitud por convenio debe enviarse solo al proveedor del convenio",
        )


def _warehouse_for_project(db: Session, warehouse_id: int | None, project: Project) -> ProjectWarehouse | None:
    if warehouse_id is None:
        return db.scalar(
            select(ProjectWarehouse)
            .where(ProjectWarehouse.project_id == project.id, ProjectWarehouse.is_active.is_(True))
            .order_by(ProjectWarehouse.id)
            .limit(1)
        )
    warehouse = get_or_404(db, ProjectWarehouse, warehouse_id)
    if warehouse.project_id != project.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La bodega no pertenece al desarrollo",
        )
    return warehouse


def _next_number(db: Session, model: type, field_name: str, prefix: str, company_id: int) -> str:
    count = db.scalar(select(func.count(model.id)).where(model.company_id == company_id)) or 0
    candidate = f"{prefix}-{date.today().strftime('%Y%m')}-{count + 1:04d}"
    field = getattr(model, field_name)
    while db.scalar(select(model.id).where(field == candidate)) is not None:
        count += 1
        candidate = f"{prefix}-{date.today().strftime('%Y%m')}-{count + 1:04d}"
    return candidate


def _rfq_exception_snapshot(payload: SupplierRFQCreate | SupplierRFQExceptionCreate) -> dict:
    data = payload.model_dump(
        mode="json",
        exclude={
            "exception_request_id",
            "supplier_agreement_id",
            "material_requisition_id",
            "request_notes",
            "rfq_number",
            "notes",
            "warehouse_id",
        },
    )
    return {
        "project_id": data["project_id"],
        "title": data["title"].strip(),
        "required_by": data.get("required_by"),
        "response_deadline": data.get("response_deadline"),
        "supplier_ids": sorted(set(data["supplier_ids"])),
        "items": [
            {
                "material_id": item.get("material_id"),
                "source_code": item.get("source_code"),
                "description": item["description"].strip(),
                "unit": item["unit"].strip(),
                "quantity": str(item["quantity"]),
                "notes": item.get("notes"),
            }
            for item in data["items"]
        ],
    }


def _rfq_exception_fingerprint(snapshot_data: dict) -> str:
    canonical = json.dumps(snapshot_data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _ensure_unique_supplier_ids(supplier_ids: list[int]) -> None:
    if len(supplier_ids) != len(set(supplier_ids)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La solicitud contiene proveedores duplicados",
        )


def _ensure_exception_matches_payload(
    exception_request: SupplierRFQExceptionRequest,
    payload: SupplierRFQCreate,
) -> None:
    if exception_request.status != "approved" or exception_request.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La excepcion aun no esta aprobada o ya fue utilizada",
        )
    payload_snapshot = _rfq_exception_snapshot(payload)
    payload_fingerprint = _rfq_exception_fingerprint(payload_snapshot)
    if exception_request.payload_fingerprint:
        matches = exception_request.payload_fingerprint == payload_fingerprint
    else:
        matches = exception_request.payload_snapshot == payload_snapshot
    if not matches:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La excepcion aprobada no coincide con la solicitud actual",
        )


def _po_is_complete(purchase_order: PurchaseOrder) -> bool:
    return bool(purchase_order.items) and all(
        item.received_quantity >= item.quantity_ordered for item in purchase_order.items
    )


def _sync_purchase_order_status(purchase_order: PurchaseOrder) -> None:
    if not purchase_order.items:
        return
    received_any = any(item.received_quantity > 0 for item in purchase_order.items)
    complete = _po_is_complete(purchase_order)
    if complete:
        purchase_order.status = "received"
    elif received_any:
        purchase_order.status = "partially_received"
    elif purchase_order.status not in {"sent", "cancelled", "closed"}:
        purchase_order.status = "issued"


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _new_supplier_portal_token(link: SupplierRFQSupplier, rfq: SupplierRFQ) -> str:
    token = secrets.token_urlsafe(32)
    link.portal_token_hash = _token_hash(token)
    expires_at = _now() + timedelta(days=settings.supplier_quote_token_expire_days)
    if rfq.response_deadline:
        deadline = datetime.combine(rfq.response_deadline, datetime.max.time(), tzinfo=timezone.utc)
        expires_at = max(expires_at, deadline)
    link.portal_token_expires_at = expires_at
    link.portal_last_accessed_at = None
    return token


def _supplier_portal_url(token: str) -> str:
    return f"{settings.public_app_url.rstrip('/')}/supplier/quote/{token}"


def _queue_rfq_emails(db: Session, rfq: SupplierRFQ, requested_by: int | None = None) -> tuple[int, int]:
    queued_count = 0
    error_count = 0

    for link in rfq.supplier_links:
        supplier = link.supplier
        recipient = (supplier.contact_email or "").strip() if supplier else ""
        if not recipient:
            link.status = "missing_email"
            link.notes = "Proveedor sin correo de contacto."
            error_count += 1
            continue

        if has_active_or_sent_message(
            db,
            related_entity_type="SupplierRFQSupplier",
            related_entity_id=link.id,
            recipient_email=recipient,
        ):
            link.status = "queued"
            link.notes = "Correo ya esta en cola de envio."
            queued_count += 1
            continue

        token = _new_supplier_portal_token(link, rfq)
        subject, text_body, html_body = rfq_email_content(rfq, portal_url=_supplier_portal_url(token))
        queue_email(
            db,
            company_id=rfq.company_id,
            requested_by=requested_by,
            message_type="supplier_rfq",
            related_entity_type="SupplierRFQSupplier",
            related_entity_id=link.id,
            recipient_email=recipient,
            recipient_name=supplier.name if supplier else None,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
        )
        link.status = "queued"
        link.notes = "Correo en cola de envio."
        queued_count += 1

    if queued_count:
        rfq.status = "sent"
        rfq.sent_at = _now()
    else:
        rfq.status = "email_error"
    return queued_count, error_count


def _queue_purchase_order_email(
    db: Session,
    purchase_order: PurchaseOrder,
    requested_by: int | None = None,
) -> bool:
    supplier = purchase_order.supplier
    recipient = (supplier.contact_email or "").strip() if supplier else ""
    if not recipient:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El proveedor no tiene correo de contacto configurado.",
        )

    if has_active_or_sent_message(
        db,
        related_entity_type="PurchaseOrder",
        related_entity_id=purchase_order.id,
        recipient_email=recipient,
    ):
        return False

    subject, text_body, html_body = purchase_order_email_content(purchase_order)
    queue_email(
        db,
        company_id=purchase_order.company_id,
        requested_by=requested_by,
        message_type="purchase_order",
        related_entity_type="PurchaseOrder",
        related_entity_id=purchase_order.id,
        recipient_email=recipient,
        recipient_name=supplier.contact_name or supplier.name if supplier else None,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )
    return True


def _invoice_status_for_po(purchase_order: PurchaseOrder) -> tuple[str, int, str]:
    pending_items = sum(
        1 for item in purchase_order.items if item.received_quantity < item.quantity_ordered
    )
    if pending_items:
        return (
            "blocked",
            pending_items,
            "La factura queda bloqueada porque la orden de compra tiene material pendiente.",
        )
    return (
        "approved_for_payment",
        0,
        "Factura aprobada para gestion de pago. La orden de compra esta completa.",
    )


def _invoiced_quantities_by_po_item(
    db: Session,
    purchase_order: PurchaseOrder,
    *,
    exclude_invoice_id: int | None = None,
    paid_only: bool = False,
) -> dict[int, Decimal]:
    invoice_statuses = ("paid",) if paid_only else ("received", "approved_for_payment", "scheduled", "paid")
    statement = (
        select(SupplierInvoiceItem.purchase_order_item_id, func.coalesce(func.sum(SupplierInvoiceItem.quantity), 0))
        .join(SupplierInvoice, SupplierInvoice.id == SupplierInvoiceItem.supplier_invoice_id)
        .where(
            SupplierInvoice.purchase_order_id == purchase_order.id,
            SupplierInvoice.status.in_(invoice_statuses),
        )
        .group_by(SupplierInvoiceItem.purchase_order_item_id)
    )
    if exclude_invoice_id is not None:
        statement = statement.where(SupplierInvoice.id != exclude_invoice_id)
    return {item_id: Decimal(quantity) for item_id, quantity in db.execute(statement).all()}


def _invoice_status_for_items(
    db: Session,
    invoice: SupplierInvoice,
    *,
    exclude_invoice_id: int | None = None,
) -> tuple[str, int, str]:
    purchase_order = invoice.purchase_order
    if purchase_order.billing_mode != "partial":
        return (
            "blocked",
            len(invoice.items),
            "La orden de compra esta en modo pago unico. Cambiala a facturacion parcial para pagar entregas parciales.",
        )
    already_invoiced = _invoiced_quantities_by_po_item(
        db,
        purchase_order,
        exclude_invoice_id=exclude_invoice_id,
    )
    blocked_lines = 0
    for item in invoice.items:
        available = item.purchase_order_item.received_quantity - already_invoiced.get(
            item.purchase_order_item_id,
            Decimal("0"),
        )
        if item.quantity > available:
            blocked_lines += 1
    if blocked_lines:
        return (
            "blocked",
            blocked_lines,
            "La factura queda bloqueada porque incluye cantidades mayores a lo recibido o ya facturado.",
        )
    return (
        "approved_for_payment",
        0,
        "Factura aprobada para pago parcial contra material recibido.",
    )


def _invoice_status(invoice: SupplierInvoice, db: Session) -> tuple[str, int, str]:
    if invoice.items:
        return _invoice_status_for_items(db, invoice, exclude_invoice_id=invoice.id)
    return _invoice_status_for_po(invoice.purchase_order)


def _sync_purchase_order_after_payment(db: Session, purchase_order: PurchaseOrder) -> None:
    db.flush()
    if purchase_order.billing_mode == "partial":
        paid_quantities = _invoiced_quantities_by_po_item(db, purchase_order, paid_only=True)
        fully_paid = bool(purchase_order.items) and all(
            paid_quantities.get(item.id, Decimal("0")) >= item.quantity_ordered
            for item in purchase_order.items
        )
        if fully_paid:
            purchase_order.status = "closed"
        else:
            _sync_purchase_order_status(purchase_order)
        return
    paid_invoice_exists = db.scalar(
        select(SupplierInvoice.id)
        .where(
            SupplierInvoice.purchase_order_id == purchase_order.id,
            SupplierInvoice.status == "paid",
        )
        .limit(1)
    )
    if paid_invoice_exists and _po_is_complete(purchase_order):
        purchase_order.status = "closed"


@router.get("/suppliers", response_model=list[SupplierRead])
def list_suppliers(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("suppliers", "view")),
) -> list[Supplier]:
    statement = scoped_select(select(Supplier), Supplier, current_user).offset(skip).limit(limit)
    return list(db.scalars(statement.order_by(Supplier.name)).all())


@router.post("/suppliers", response_model=SupplierRead, status_code=status.HTTP_201_CREATED)
def create_supplier(
    payload: SupplierCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("suppliers", "create")),
) -> Supplier:
    data = payload.model_dump()
    data["company_id"] = company_id_for_write(current_user, data.get("company_id"))
    supplier = Supplier(**data)
    db.add(supplier)
    db.flush()
    record_create(db, current_user, module="proveedores", item=supplier)
    db.commit()
    db.refresh(supplier)
    return supplier


@router.get("/suppliers/{supplier_id}", response_model=SupplierRead)
def get_supplier(
    supplier_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("suppliers", "view")),
) -> Supplier:
    supplier = get_or_404(db, Supplier, supplier_id)
    ensure_same_company(current_user, supplier, db=db)
    return supplier


@router.patch("/suppliers/{supplier_id}", response_model=SupplierRead)
def update_supplier(
    supplier_id: int,
    payload: SupplierUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("suppliers", "edit")),
) -> Supplier:
    supplier = get_or_404(db, Supplier, supplier_id)
    ensure_same_company(current_user, supplier, db=db)
    data = payload.model_dump(exclude_unset=True)
    if "company_id" in data:
        data["company_id"] = company_id_for_write(current_user, data.get("company_id"))
    before = snapshot(supplier, list(data.keys()))
    for field, value in data.items():
        setattr(supplier, field, value)
    record_update(db, current_user, module="proveedores", item=supplier, before=before)
    db.commit()
    db.refresh(supplier)
    return supplier


@router.delete("/suppliers/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_supplier(
    supplier_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("suppliers", "delete")),
) -> None:
    supplier = get_or_404(db, Supplier, supplier_id)
    ensure_same_company(current_user, supplier, db=db)
    record_delete(db, current_user, module="proveedores", item=supplier)
    db.delete(supplier)
    db.commit()


def _agreement_for_user(db: Session, agreement_id: int, current_user: User) -> SupplierAgreement:
    agreement = db.scalar(
        select(SupplierAgreement)
        .where(SupplierAgreement.id == agreement_id)
        .options(*_agreement_options())
    )
    if agreement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro no encontrado")
    ensure_same_company(current_user, agreement, db=db)
    return agreement


def _validate_agreement_payload(
    db: Session,
    current_user: User,
    data: dict,
    existing: SupplierAgreement | None = None,
) -> dict:
    company_id = company_id_for_write(
        current_user,
        data.get("company_id", existing.company_id if existing else None),
    )
    supplier_id = data.get("supplier_id", existing.supplier_id if existing else None)
    client_id = data.get("client_id", existing.client_id if existing else None)
    house_model_id = data.get("house_model_id", existing.house_model_id if existing else None)
    if supplier_id is None or client_id is None or house_model_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Proveedor, inmobiliaria y modelo son obligatorios",
        )
    supplier = _supplier_for_user(db, supplier_id, current_user)
    client = get_or_404(db, Client, client_id)
    house_model = get_or_404(db, HouseModel, house_model_id)
    ensure_same_company(current_user, client, db=db)
    ensure_same_company(current_user, house_model, db=db)
    if supplier.company_id != company_id or client.company_id != company_id or house_model.company_id != company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El convenio debe pertenecer a la misma constructora",
        )
    if house_model.client_id != client.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El modelo seleccionado no pertenece a la inmobiliaria",
        )
    data["company_id"] = company_id
    data["supplier_id"] = supplier.id
    data["client_id"] = client.id
    data["house_model_id"] = house_model.id
    return data


def _validate_agreement_item_payload(
    db: Session,
    current_user: User,
    agreement: SupplierAgreement,
    data: dict,
    existing: SupplierAgreementItem | None = None,
) -> dict:
    material_id = data.get("material_id", existing.material_id if existing else None)
    if material_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El material es obligatorio",
        )
    material = get_or_404(db, Material, material_id)
    ensure_same_company(current_user, material, db=db)
    if material.company_id != agreement.company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El material no pertenece a la constructora del convenio",
        )
    data["material_id"] = material.id
    if existing is None and not data.get("description"):
        data["description"] = material.name
    elif "description" in data and not data.get("description"):
        data["description"] = material.name
    if existing is None and not data.get("unit"):
        data["unit"] = material.unit
    elif "unit" in data and not data.get("unit"):
        data["unit"] = material.unit
    return data


def _mark_agreement_pending_approval(
    db: Session,
    agreement: SupplierAgreement,
    current_user: User,
    reason: str,
) -> None:
    agreement.approval_status = "requested"
    agreement.requested_at = _now()
    agreement.decision_notes = None
    agreement.decided_by = None
    agreement.decided_at = None
    notify_permission(
        db,
        company_id=agreement.company_id,
        module="supplier_agreements",
        action="approve",
        notification_type="supplier_agreement_approval_requested",
        title="Convenio pendiente de autorizar",
        body=f"{current_user.full_name} solicito autorizar el convenio {agreement.name}.",
        category="task",
        priority="high",
        source_module="compras",
        entity_type="SupplierAgreement",
        entity_id=agreement.id,
        entity_label=agreement.name,
        action_url="/purchasing/approvals",
        metadata={
            "reason": reason,
            "supplier_id": agreement.supplier_id,
            "client_id": agreement.client_id,
            "house_model_id": agreement.house_model_id,
        },
    )


@router.get("/supplier-agreements", response_model=list[SupplierAgreementRead])
def list_supplier_agreements(
    supplier_id: int | None = None,
    client_id: int | None = None,
    house_model_id: int | None = None,
    status_filter: str | None = None,
    approval_status: str | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("supplier_agreements", "view")),
) -> list[SupplierAgreement]:
    statement = scoped_select(select(SupplierAgreement), SupplierAgreement, current_user)
    if supplier_id is not None:
        statement = statement.where(SupplierAgreement.supplier_id == supplier_id)
    if client_id is not None:
        statement = statement.where(SupplierAgreement.client_id == client_id)
    if house_model_id is not None:
        statement = statement.where(SupplierAgreement.house_model_id == house_model_id)
    if status_filter:
        statement = statement.where(SupplierAgreement.status == status_filter)
    if approval_status:
        statement = statement.where(SupplierAgreement.approval_status == approval_status)
    return list(
        db.scalars(
            statement.options(*_agreement_options())
            .order_by(SupplierAgreement.approval_status, SupplierAgreement.status, SupplierAgreement.name)
            .offset(skip)
            .limit(limit)
        ).all()
    )


@router.post("/supplier-agreements", response_model=SupplierAgreementRead, status_code=status.HTTP_201_CREATED)
def create_supplier_agreement(
    payload: SupplierAgreementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("supplier_agreements", "create")),
) -> SupplierAgreement:
    data = payload.model_dump(exclude={"items"})
    data = _validate_agreement_payload(db, current_user, data)
    agreement = SupplierAgreement(**data, created_by=current_user.id)
    db.add(agreement)
    db.flush()
    for item_payload in payload.items:
        item_data = _validate_agreement_item_payload(
            db,
            current_user,
            agreement,
            item_payload.model_dump(),
        )
        db.add(SupplierAgreementItem(agreement_id=agreement.id, **item_data))
    _mark_agreement_pending_approval(db, agreement, current_user, "create")
    record_create(db, current_user, module="convenios_proveedor", item=agreement)
    db.commit()
    return _agreement_for_user(db, agreement.id, current_user)


@router.get("/supplier-agreement-approvals", response_model=list[SupplierAgreementRead])
def list_supplier_agreement_approvals(
    approval_status: str = "requested",
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[SupplierAgreement]:
    can_create = user_has_permission(current_user, "supplier_agreements", "create")
    can_approve = user_has_permission(current_user, "supplier_agreements", "approve")
    if not can_create and not can_approve:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permiso requerido: supplier_agreements:create o supplier_agreements:approve",
        )
    statement = scoped_select(select(SupplierAgreement), SupplierAgreement, current_user)
    if approval_status != "all":
        statement = statement.where(SupplierAgreement.approval_status == approval_status)
    if not can_approve:
        statement = statement.where(SupplierAgreement.created_by == current_user.id)
    return list(
        db.scalars(
            statement.options(*_agreement_options())
            .order_by(SupplierAgreement.created_at.desc())
            .offset(skip)
            .limit(limit)
        ).all()
    )


@router.post("/supplier-agreements/{agreement_id}/approve", response_model=SupplierAgreementRead)
def approve_supplier_agreement(
    agreement_id: int,
    payload: SupplierRFQExceptionDecision,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("supplier_agreements", "approve")),
) -> SupplierAgreement:
    agreement = _agreement_for_user(db, agreement_id, current_user)
    if agreement.approval_status != "requested":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El convenio ya fue atendido")
    agreement.approval_status = "approved"
    agreement.decision_notes = payload.decision_notes
    agreement.decided_by = current_user.id
    agreement.decided_at = _now()
    record_event(
        db,
        current_user,
        module="convenios_proveedor",
        action="approve",
        entity_type="SupplierAgreement",
        entity_id=agreement.id,
        company_id=agreement.company_id,
        label=agreement.name,
        description=f"{current_user.full_name} autorizo el convenio {agreement.name}",
        metadata={"approval_status": agreement.approval_status},
    )
    resolve_notifications(
        db,
        company_id=agreement.company_id,
        notification_type="supplier_agreement_approval_requested",
        entity_type="SupplierAgreement",
        entity_id=agreement.id,
    )
    if agreement.created_by is not None:
        notify_user_id(
            db,
            user_id=agreement.created_by,
            company_id=agreement.company_id,
            notification_type="supplier_agreement_approved",
            title="Convenio autorizado",
            body=f"El convenio {agreement.name} ya puede usarse para cotizacion directa.",
            category="info",
            priority="normal",
            source_module="compras",
            entity_type="SupplierAgreement",
            entity_id=agreement.id,
            entity_label=agreement.name,
            action_url="/supplier-agreements",
            metadata={"approval_status": agreement.approval_status},
        )
    db.commit()
    return _agreement_for_user(db, agreement_id, current_user)


@router.post("/supplier-agreements/{agreement_id}/reject", response_model=SupplierAgreementRead)
def reject_supplier_agreement(
    agreement_id: int,
    payload: SupplierRFQExceptionDecision,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("supplier_agreements", "approve")),
) -> SupplierAgreement:
    agreement = _agreement_for_user(db, agreement_id, current_user)
    if agreement.approval_status != "requested":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El convenio ya fue atendido")
    agreement.approval_status = "rejected"
    agreement.decision_notes = payload.decision_notes
    agreement.decided_by = current_user.id
    agreement.decided_at = _now()
    record_event(
        db,
        current_user,
        module="convenios_proveedor",
        action="reject",
        entity_type="SupplierAgreement",
        entity_id=agreement.id,
        company_id=agreement.company_id,
        label=agreement.name,
        description=f"{current_user.full_name} rechazo el convenio {agreement.name}",
        metadata={"approval_status": agreement.approval_status},
    )
    resolve_notifications(
        db,
        company_id=agreement.company_id,
        notification_type="supplier_agreement_approval_requested",
        entity_type="SupplierAgreement",
        entity_id=agreement.id,
    )
    if agreement.created_by is not None:
        notify_user_id(
            db,
            user_id=agreement.created_by,
            company_id=agreement.company_id,
            notification_type="supplier_agreement_rejected",
            title="Convenio rechazado",
            body=f"El convenio {agreement.name} fue rechazado.",
            category="warning",
            priority="high",
            source_module="compras",
            entity_type="SupplierAgreement",
            entity_id=agreement.id,
            entity_label=agreement.name,
            action_url="/supplier-agreements",
            metadata={"decision_notes": agreement.decision_notes},
        )
    db.commit()
    return _agreement_for_user(db, agreement_id, current_user)


@router.get("/supplier-agreements/eligible", response_model=list[SupplierAgreementEligibility])
def list_eligible_supplier_agreements(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("supplier_agreements", "view")),
) -> list[SupplierAgreementEligibility]:
    project = _project_for_user(db, project_id, current_user)
    today = date.today()
    project_model_ids = select(ProjectHouseModel.house_model_id).where(ProjectHouseModel.project_id == project.id)
    statement = scoped_select(select(SupplierAgreement), SupplierAgreement, current_user).where(
        SupplierAgreement.client_id == project.client_id,
        SupplierAgreement.house_model_id.in_(project_model_ids),
        SupplierAgreement.status == "active",
        SupplierAgreement.approval_status == "approved",
    )
    agreements = db.scalars(statement.options(*_agreement_options()).order_by(SupplierAgreement.name)).all()
    result: list[SupplierAgreementEligibility] = []
    for agreement in agreements:
        if agreement.valid_from and agreement.valid_from > today:
            continue
        if agreement.valid_until and agreement.valid_until < today:
            continue
        result.append(
            SupplierAgreementEligibility(
                agreement=agreement,
                covered_material_ids=[],
                missing_material_ids=[],
                is_full_match=True,
            )
        )
    return result


@router.get("/supplier-agreements/{agreement_id}", response_model=SupplierAgreementRead)
def get_supplier_agreement(
    agreement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("supplier_agreements", "view")),
) -> SupplierAgreement:
    return _agreement_for_user(db, agreement_id, current_user)


@router.patch("/supplier-agreements/{agreement_id}", response_model=SupplierAgreementRead)
def update_supplier_agreement(
    agreement_id: int,
    payload: SupplierAgreementUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("supplier_agreements", "edit")),
) -> SupplierAgreement:
    agreement = _agreement_for_user(db, agreement_id, current_user)
    data = payload.model_dump(exclude_unset=True)
    if data:
        data = _validate_agreement_payload(db, current_user, data, agreement)
        before = snapshot(agreement, list(data.keys()) + ["approval_status"])
        for field, value in data.items():
            setattr(agreement, field, value)
        _mark_agreement_pending_approval(db, agreement, current_user, "update")
        record_update(db, current_user, module="convenios_proveedor", item=agreement, before=before)
    db.commit()
    return _agreement_for_user(db, agreement_id, current_user)


@router.delete("/supplier-agreements/{agreement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_supplier_agreement(
    agreement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("supplier_agreements", "delete")),
) -> None:
    agreement = _agreement_for_user(db, agreement_id, current_user)
    record_delete(db, current_user, module="convenios_proveedor", item=agreement)
    db.delete(agreement)
    db.commit()


@router.post(
    "/supplier-agreements/{agreement_id}/items",
    response_model=SupplierAgreementItemRead,
    status_code=status.HTTP_201_CREATED,
)
def create_supplier_agreement_item(
    agreement_id: int,
    payload: SupplierAgreementItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("supplier_agreements", "edit")),
) -> SupplierAgreementItem:
    agreement = _agreement_for_user(db, agreement_id, current_user)
    data = _validate_agreement_item_payload(db, current_user, agreement, payload.model_dump())
    item = SupplierAgreementItem(agreement_id=agreement.id, **data)
    db.add(item)
    db.flush()
    _mark_agreement_pending_approval(db, agreement, current_user, "item_create")
    record_create(db, current_user, module="convenios_proveedor", item=item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/supplier-agreements/{agreement_id}/items/{item_id}", response_model=SupplierAgreementItemRead)
def update_supplier_agreement_item(
    agreement_id: int,
    item_id: int,
    payload: SupplierAgreementItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("supplier_agreements", "edit")),
) -> SupplierAgreementItem:
    agreement = _agreement_for_user(db, agreement_id, current_user)
    item = get_or_404(db, SupplierAgreementItem, item_id)
    if item.agreement_id != agreement.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro no encontrado")
    data = payload.model_dump(exclude_unset=True)
    if data:
        data = _validate_agreement_item_payload(db, current_user, agreement, data, item)
        before = snapshot(item, list(data.keys()))
        for field, value in data.items():
            setattr(item, field, value)
        _mark_agreement_pending_approval(db, agreement, current_user, "item_update")
        record_update(db, current_user, module="convenios_proveedor", item=item, before=before)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/supplier-agreements/{agreement_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_supplier_agreement_item(
    agreement_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("supplier_agreements", "edit")),
) -> None:
    agreement = _agreement_for_user(db, agreement_id, current_user)
    item = get_or_404(db, SupplierAgreementItem, item_id)
    if item.agreement_id != agreement.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro no encontrado")
    record_delete(db, current_user, module="convenios_proveedor", item=item)
    _mark_agreement_pending_approval(db, agreement, current_user, "item_delete")
    db.delete(item)
    db.commit()


@router.get("/supplier-rfqs", response_model=list[SupplierRFQRead])
def list_supplier_rfqs(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("supplier_rfq", "view")),
) -> list[SupplierRFQ]:
    statement = scoped_select(select(SupplierRFQ), SupplierRFQ, current_user)
    return list(
        db.scalars(
            statement.options(
                selectinload(SupplierRFQ.creator),
                selectinload(SupplierRFQ.supplier_agreement),
                selectinload(SupplierRFQ.items),
                selectinload(SupplierRFQ.supplier_links).selectinload(SupplierRFQSupplier.supplier),
            )
            .order_by(SupplierRFQ.created_at.desc())
            .offset(skip)
            .limit(limit)
        ).all()
    )


@router.get("/supplier-rfq-exceptions", response_model=list[SupplierRFQExceptionRead])
def list_supplier_rfq_exceptions(
    approval_status: str = "requested",
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[SupplierRFQExceptionRequest]:
    can_create = user_has_permission(current_user, "supplier_rfq", "create")
    can_approve = user_has_permission(current_user, "supplier_quotes", "approve")
    if not can_create and not can_approve:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permiso requerido: supplier_rfq:create o supplier_quotes:approve",
        )
    statement = scoped_select(select(SupplierRFQExceptionRequest), SupplierRFQExceptionRequest, current_user)
    if approval_status != "all":
        statement = statement.where(SupplierRFQExceptionRequest.status == approval_status)
    if not can_approve:
        statement = statement.where(SupplierRFQExceptionRequest.requested_by == current_user.id)
    return list(
        db.scalars(
            statement.options(
                selectinload(SupplierRFQExceptionRequest.requester),
                selectinload(SupplierRFQExceptionRequest.decider),
            )
            .order_by(SupplierRFQExceptionRequest.created_at.desc())
            .offset(skip)
            .limit(limit)
        ).all()
    )


@router.post(
    "/supplier-rfq-exceptions",
    response_model=SupplierRFQExceptionRead,
    status_code=status.HTTP_201_CREATED,
)
def request_supplier_rfq_exception(
    payload: SupplierRFQExceptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("supplier_rfq", "create")),
) -> SupplierRFQExceptionRequest:
    project = _project_for_user(db, payload.project_id, current_user)
    _ensure_unique_supplier_ids(payload.supplier_ids)
    suppliers = [_supplier_for_user(db, supplier_id, current_user) for supplier_id in payload.supplier_ids]
    supplier_count = len({supplier.id for supplier in suppliers})
    if supplier_count >= 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La excepcion solo aplica cuando hay menos de 3 proveedores",
        )
    for item in payload.items:
        if item.material_id is not None:
            material = get_or_404(db, Material, item.material_id)
            ensure_same_company(current_user, material, db=db)
    payload_snapshot = _rfq_exception_snapshot(payload)
    exception_request = SupplierRFQExceptionRequest(
        company_id=project.company_id,
        project_id=project.id,
        title=payload.title,
        required_by=payload.required_by,
        response_deadline=payload.response_deadline,
        supplier_count=supplier_count,
        item_count=len(payload.items),
        payload_snapshot=payload_snapshot,
        payload_fingerprint=_rfq_exception_fingerprint(payload_snapshot),
        request_notes=payload.request_notes.strip(),
        requested_by=current_user.id,
        requested_at=_now(),
    )
    db.add(exception_request)
    db.flush()
    record_event(
        db,
        current_user,
        module="compras",
        action="request_exception",
        entity_type="SupplierRFQExceptionRequest",
        entity_id=exception_request.id,
        company_id=exception_request.company_id,
        label=exception_request.title,
        description=f"{current_user.full_name} solicito excepcion para cotizar con menos de 3 proveedores",
        metadata={"proveedores": supplier_count, "partidas": len(payload.items)},
    )
    notify_permission(
        db,
        company_id=exception_request.company_id,
        module="supplier_quotes",
        action="approve",
        notification_type="rfq_exception_requested",
        title="Excepcion de proveedores pendiente",
        body=(
            f"{current_user.full_name} solicito cotizar '{exception_request.title}' "
            f"con {supplier_count} proveedor(es)."
        ),
        category="exception",
        priority="high",
        source_module="compras",
        entity_type="SupplierRFQExceptionRequest",
        entity_id=exception_request.id,
        entity_label=exception_request.title,
        action_url="/purchasing/approvals",
        project_id=exception_request.project_id,
        metadata={"proveedores": supplier_count, "partidas": len(payload.items)},
    )
    db.commit()
    created_exception = db.scalar(
        select(SupplierRFQExceptionRequest)
        .where(SupplierRFQExceptionRequest.id == exception_request.id)
        .options(
            selectinload(SupplierRFQExceptionRequest.requester),
            selectinload(SupplierRFQExceptionRequest.decider),
        )
    )
    if created_exception is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro no encontrado")
    return created_exception


@router.post("/supplier-rfq-exceptions/{exception_id}/approve", response_model=SupplierRFQExceptionRead)
def approve_supplier_rfq_exception(
    exception_id: int,
    payload: SupplierRFQExceptionDecision,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("supplier_quotes", "approve")),
) -> SupplierRFQExceptionRequest:
    exception_request = get_or_404(db, SupplierRFQExceptionRequest, exception_id)
    ensure_same_company(current_user, exception_request, db=db)
    if exception_request.status != "requested":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La excepcion ya fue atendida")
    exception_request.status = "approved"
    exception_request.decision_notes = payload.decision_notes
    exception_request.decided_by = current_user.id
    exception_request.decided_at = _now()
    record_event(
        db,
        current_user,
        module="compras",
        action="approve_exception",
        entity_type="SupplierRFQExceptionRequest",
        entity_id=exception_request.id,
        company_id=exception_request.company_id,
        label=exception_request.title,
        description=f"{current_user.full_name} aprobo excepcion para solicitud de cotizacion",
    )
    resolve_notifications(
        db,
        company_id=exception_request.company_id,
        notification_type="rfq_exception_requested",
        entity_type="SupplierRFQExceptionRequest",
        entity_id=exception_request.id,
    )
    notify_user_id(
        db,
        user_id=exception_request.requested_by,
        company_id=exception_request.company_id,
        notification_type="rfq_exception_approved",
        title="Excepcion aprobada",
        body=f"Ya puedes crear la solicitud '{exception_request.title}' con menos de 3 proveedores.",
        category="info",
        priority="normal",
        source_module="compras",
        entity_type="SupplierRFQExceptionRequest",
        entity_id=exception_request.id,
        entity_label=exception_request.title,
        action_url="/purchasing",
        project_id=exception_request.project_id,
    )
    db.commit()
    db.refresh(exception_request)
    return exception_request


@router.post("/supplier-rfq-exceptions/{exception_id}/reject", response_model=SupplierRFQExceptionRead)
def reject_supplier_rfq_exception(
    exception_id: int,
    payload: SupplierRFQExceptionDecision,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("supplier_quotes", "approve")),
) -> SupplierRFQExceptionRequest:
    exception_request = get_or_404(db, SupplierRFQExceptionRequest, exception_id)
    ensure_same_company(current_user, exception_request, db=db)
    if exception_request.status != "requested":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La excepcion ya fue atendida")
    exception_request.status = "rejected"
    exception_request.decision_notes = payload.decision_notes
    exception_request.decided_by = current_user.id
    exception_request.decided_at = _now()
    record_event(
        db,
        current_user,
        module="compras",
        action="reject_exception",
        entity_type="SupplierRFQExceptionRequest",
        entity_id=exception_request.id,
        company_id=exception_request.company_id,
        label=exception_request.title,
        description=f"{current_user.full_name} rechazo excepcion para solicitud de cotizacion",
    )
    resolve_notifications(
        db,
        company_id=exception_request.company_id,
        notification_type="rfq_exception_requested",
        entity_type="SupplierRFQExceptionRequest",
        entity_id=exception_request.id,
    )
    notify_user_id(
        db,
        user_id=exception_request.requested_by,
        company_id=exception_request.company_id,
        notification_type="rfq_exception_rejected",
        title="Excepcion rechazada",
        body=f"La excepcion para '{exception_request.title}' fue rechazada.",
        category="warning",
        priority="high",
        source_module="compras",
        entity_type="SupplierRFQExceptionRequest",
        entity_id=exception_request.id,
        entity_label=exception_request.title,
        action_url="/purchasing",
        project_id=exception_request.project_id,
        metadata={"decision_notes": exception_request.decision_notes},
    )
    db.commit()
    db.refresh(exception_request)
    return exception_request


@router.post("/supplier-rfqs", response_model=SupplierRFQRead, status_code=status.HTTP_201_CREATED)
def create_supplier_rfq(
    payload: SupplierRFQCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("supplier_rfq", "create")),
) -> SupplierRFQ:
    project = _project_for_user(db, payload.project_id, current_user)
    warehouse = _warehouse_for_project(db, payload.warehouse_id, project)
    _ensure_unique_supplier_ids(payload.supplier_ids)
    suppliers = [_supplier_for_user(db, supplier_id, current_user) for supplier_id in payload.supplier_ids]
    supplier_count = len({supplier.id for supplier in suppliers})
    approved_exception: SupplierRFQExceptionRequest | None = None
    supplier_agreement: SupplierAgreement | None = None
    material_requisition: MaterialRequisition | None = None
    if payload.material_requisition_id is not None:
        material_requisition = db.scalar(
            select(MaterialRequisition)
            .where(MaterialRequisition.id == payload.material_requisition_id)
            .options(selectinload(MaterialRequisition.items))
        )
        if material_requisition is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requerimiento no encontrado")
        ensure_same_company(current_user, material_requisition, db=db)
        if material_requisition.status not in {"submitted", "in_review", "approved"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El requerimiento de obra debe estar pendiente o aprobado para enviarlo a cotizacion",
            )
        if material_requisition.converted_rfq_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El requerimiento de obra ya fue convertido a solicitud de cotizacion",
            )
        if material_requisition.project_id != project.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El requerimiento de obra no pertenece al desarrollo seleccionado",
            )
    if payload.supplier_agreement_id is not None:
        if not user_has_permission(current_user, "supplier_agreements", "use"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permiso requerido: supplier_agreements:use",
            )
        supplier_agreement = _agreement_for_user(db, payload.supplier_agreement_id, current_user)
        _validate_agreement_scope(
            db,
            supplier_agreement,
            project,
            [supplier.id for supplier in suppliers],
            payload.items,
        )
    if supplier_count < 3:
        if payload.exception_request_id is None and supplier_agreement is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Se requiere una excepcion aprobada o convenio activo para crear solicitud con menos de 3 proveedores",
            )
        if payload.exception_request_id is not None:
            approved_exception = get_or_404(db, SupplierRFQExceptionRequest, payload.exception_request_id)
            ensure_same_company(current_user, approved_exception, db=db)
            _ensure_exception_matches_payload(approved_exception, payload)
    rfq = SupplierRFQ(
        company_id=project.company_id,
        project_id=project.id,
        warehouse_id=warehouse.id if warehouse else None,
        rfq_number=payload.rfq_number
        or _next_number(db, SupplierRFQ, "rfq_number", "SC", project.company_id),
        title=payload.title,
        request_type=(
            "agreement"
            if supplier_agreement
            else ("exception" if approved_exception else ("work_requisition" if material_requisition else "standard"))
        ),
        supplier_agreement_id=supplier_agreement.id if supplier_agreement else None,
        required_by=payload.required_by,
        response_deadline=payload.response_deadline,
        notes=payload.notes,
        created_by=current_user.id,
    )
    db.add(rfq)
    db.flush()
    created_items: list[SupplierRFQItem] = []
    for item in payload.items:
        if item.material_id is not None:
            material = get_or_404(db, Material, item.material_id)
            ensure_same_company(current_user, material, db=db)
        rfq_item = SupplierRFQItem(rfq_id=rfq.id, **item.model_dump())
        db.add(rfq_item)
        db.flush()
        created_items.append(rfq_item)
    for supplier in suppliers:
        db.add(SupplierRFQSupplier(rfq_id=rfq.id, supplier_id=supplier.id))
    if approved_exception is not None:
        approved_exception.status = "used"
        approved_exception.rfq_id = rfq.id
        approved_exception.used_at = _now()
    if material_requisition is not None:
        material_requisition.status = "converted_to_rfq"
        if material_requisition.reviewed_by_user_id is None:
            material_requisition.reviewed_by_user_id = current_user.id
            material_requisition.reviewed_at = _now()
        material_requisition.converted_rfq_id = rfq.id
        for requisition_item, rfq_item in zip(material_requisition.items, created_items):
            if requisition_item.approved_quantity is None:
                requisition_item.approved_quantity = requisition_item.requested_quantity
            requisition_item.status = "converted"
            requisition_item.supplier_rfq_item_id = rfq_item.id
    db.commit()
    rfq = db.scalar(
        select(SupplierRFQ)
        .where(SupplierRFQ.id == rfq.id)
        .options(
            selectinload(SupplierRFQ.creator),
            selectinload(SupplierRFQ.supplier_agreement),
            selectinload(SupplierRFQ.items),
            selectinload(SupplierRFQ.supplier_links).selectinload(SupplierRFQSupplier.supplier),
        )
    )
    if rfq is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro no encontrado")
    queued_count, error_count = _queue_rfq_emails(db, rfq, requested_by=current_user.id)
    record_event(
        db,
        current_user,
        module="compras",
        action="create_agreement_rfq" if supplier_agreement else "create",
        entity_type="SupplierRFQ",
        entity_id=rfq.id,
        company_id=rfq.company_id,
        label=rfq.rfq_number,
        description=(
            f"{current_user.full_name} creo la solicitud por convenio {rfq.rfq_number}"
            if supplier_agreement
            else f"{current_user.full_name} creo la solicitud a proveedores {rfq.rfq_number}"
        ),
        metadata={
            "proveedores": len(rfq.supplier_links),
            "encolados": queued_count,
            "errores": error_count,
            "request_type": rfq.request_type,
            "supplier_agreement_id": rfq.supplier_agreement_id,
            "material_requisition_id": material_requisition.id if material_requisition else None,
        },
    )
    if material_requisition is not None and material_requisition.requested_by_user_id is not None:
        notify_user_id(
            db,
            user_id=material_requisition.requested_by_user_id,
            company_id=rfq.company_id,
            notification_type="material_requisition_converted",
            title="Requerimiento enviado a cotizar",
            body=(
                f"Compras convirtio {material_requisition.requisition_number} "
                f"en la solicitud {rfq.rfq_number}."
            ),
            category="info",
            priority="normal",
            source_module="compras",
            entity_type="SupplierRFQ",
            entity_id=rfq.id,
            entity_label=rfq.rfq_number,
            action_url="/purchasing",
            project_id=rfq.project_id,
            metadata={"material_requisition_id": material_requisition.id},
        )
    if supplier_agreement is not None:
        notify_permission(
            db,
            company_id=rfq.company_id,
            module="supplier_quotes",
            action="approve",
            notification_type="agreement_rfq_created",
            title="Cotizacion directa por convenio",
            body=(
                f"{current_user.full_name} envio {rfq.rfq_number} a "
                f"{supplier_agreement.supplier.name} por convenio, sin terna de proveedores."
            ),
            category="info",
            priority="normal",
            source_module="compras",
            entity_type="SupplierRFQ",
            entity_id=rfq.id,
            entity_label=rfq.rfq_number,
            action_url="/purchasing",
            project_id=rfq.project_id,
            metadata={
                "supplier_agreement_id": supplier_agreement.id,
                "supplier_id": supplier_agreement.supplier_id,
            },
        )
    db.commit()
    if queued_count:
        background_tasks.add_task(process_email_outbox_for_company, rfq.company_id)
    return get_supplier_rfq(rfq.id, db, current_user)


@router.get("/supplier-rfqs/{rfq_id}", response_model=SupplierRFQRead)
def get_supplier_rfq(
    rfq_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("supplier_rfq", "view")),
) -> SupplierRFQ:
    rfq = db.scalar(
        select(SupplierRFQ)
        .where(SupplierRFQ.id == rfq_id)
        .options(
            selectinload(SupplierRFQ.creator),
            selectinload(SupplierRFQ.supplier_agreement),
            selectinload(SupplierRFQ.items),
            selectinload(SupplierRFQ.supplier_links).selectinload(SupplierRFQSupplier.supplier),
        )
    )
    if rfq is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro no encontrado")
    ensure_same_company(current_user, rfq, db=db)
    return rfq


@router.patch("/supplier-rfqs/{rfq_id}", response_model=SupplierRFQRead)
def update_supplier_rfq(
    rfq_id: int,
    payload: SupplierRFQUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("supplier_rfq", "edit")),
) -> SupplierRFQ:
    rfq = get_or_404(db, SupplierRFQ, rfq_id)
    ensure_same_company(current_user, rfq, db=db)
    data = payload.model_dump(exclude_unset=True)
    before = snapshot(rfq, list(data.keys()))
    for field, value in data.items():
        setattr(rfq, field, value)
    record_update(db, current_user, module="compras", item=rfq, before=before)
    db.commit()
    db.refresh(rfq)
    return get_supplier_rfq(rfq_id, db, current_user)


@router.post("/supplier-rfqs/{rfq_id}/send", response_model=SupplierRFQRead)
def send_supplier_rfq(
    rfq_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("supplier_rfq", "send")),
) -> SupplierRFQ:
    rfq = get_supplier_rfq(rfq_id, db, current_user)
    queued_count, error_count = _queue_rfq_emails(db, rfq, requested_by=current_user.id)
    record_event(
        db,
        current_user,
        module="compras",
        action="send",
        entity_type="SupplierRFQ",
        entity_id=rfq.id,
        company_id=rfq.company_id,
        label=rfq.rfq_number,
        description=f"{current_user.full_name} envio la solicitud a proveedores {rfq.rfq_number}",
        metadata={"encolados": queued_count, "errores": error_count},
    )
    db.commit()
    if queued_count:
        background_tasks.add_task(process_email_outbox_for_company, rfq.company_id)
    return get_supplier_rfq(rfq_id, db, current_user)


@router.post(
    "/supplier-rfqs/{rfq_id}/quotes",
    response_model=SupplierQuoteRead,
    status_code=status.HTTP_201_CREATED,
)
def create_supplier_quote(
    rfq_id: int,
    payload: SupplierQuoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("supplier_quotes", "create")),
) -> SupplierQuote:
    rfq = get_supplier_rfq(rfq_id, db, current_user)
    if rfq.status in {"approval_pending", "awarded"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La solicitud ya esta en aprobacion o fue adjudicada",
        )
    if not payload.quote_number or not payload.quote_number.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El folio de cotizacion es obligatorio",
        )
    supplier = _supplier_for_user(db, payload.supplier_id, current_user)
    link = next((item for item in rfq.supplier_links if item.supplier_id == supplier.id), None)
    if link is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El proveedor no fue invitado a esta solicitud",
        )
    existing = db.scalar(
        select(SupplierQuote).where(
            SupplierQuote.rfq_id == rfq.id,
            SupplierQuote.supplier_id == supplier.id,
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este proveedor ya tiene una cotizacion registrada para la solicitud",
        )
    rfq_items = {item.id: item for item in rfq.items}
    quote = SupplierQuote(
        company_id=rfq.company_id,
        rfq_id=rfq.id,
        supplier_id=supplier.id,
        quote_number=payload.quote_number.strip(),
        received_at=payload.received_at or date.today(),
        valid_until=payload.valid_until,
        delivery_days=payload.delivery_days,
        payment_terms_days=payload.payment_terms_days,
        notes=payload.notes,
        attachment_name=payload.attachment_name,
    )
    db.add(quote)
    db.flush()
    subtotal = Decimal("0")
    for item_payload in payload.items:
        rfq_item = rfq_items.get(item_payload.rfq_item_id)
        if rfq_item is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La partida cotizada no pertenece a la solicitud",
            )
        quantity = item_payload.quantity or rfq_item.quantity
        line_total = quantity * item_payload.unit_price
        subtotal += line_total
        db.add(
            SupplierQuoteItem(
                supplier_quote_id=quote.id,
                rfq_item_id=rfq_item.id,
                material_id=rfq_item.material_id,
                description=rfq_item.description,
                unit=rfq_item.unit,
                quantity=quantity,
                unit_price=item_payload.unit_price,
                line_total=line_total,
                delivery_days=item_payload.delivery_days,
                notes=item_payload.notes,
            )
        )
    quote.subtotal = subtotal
    link.status = "responded"
    rfq.status = "quoted" if len(payload.items) == len(rfq.items) else "partially_quoted"
    record_create(db, current_user, module="compras", item=quote)
    db.commit()
    return db.scalar(
        select(SupplierQuote)
        .where(SupplierQuote.id == quote.id)
        .options(selectinload(SupplierQuote.supplier), selectinload(SupplierQuote.items))
    )


@router.get("/supplier-rfqs/{rfq_id}/quotes", response_model=list[SupplierQuoteRead])
def list_supplier_quotes(
    rfq_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("supplier_quotes", "view")),
) -> list[SupplierQuote]:
    rfq = get_supplier_rfq(rfq_id, db, current_user)
    return list(
        db.scalars(
            select(SupplierQuote)
            .where(SupplierQuote.rfq_id == rfq.id)
            .options(selectinload(SupplierQuote.supplier), selectinload(SupplierQuote.items))
            .order_by(SupplierQuote.subtotal)
        ).all()
    )


@router.get("/supplier-rfqs/{rfq_id}/quote-uploads", response_model=list[SupplierQuoteUploadRead])
def list_supplier_quote_uploads(
    rfq_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("supplier_quotes", "view")),
) -> list[SupplierQuoteUpload]:
    rfq = get_supplier_rfq(rfq_id, db, current_user)
    return list(
        db.scalars(
            select(SupplierQuoteUpload)
            .where(SupplierQuoteUpload.rfq_id == rfq.id)
            .options(selectinload(SupplierQuoteUpload.supplier))
            .order_by(SupplierQuoteUpload.uploaded_at.desc())
        ).all()
    )


@router.get("/supplier-quote-uploads/{upload_id}/download")
def download_supplier_quote_upload(
    upload_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("supplier_quotes", "view")),
) -> FileResponse:
    upload = db.scalar(
        select(SupplierQuoteUpload)
        .where(SupplierQuoteUpload.id == upload_id)
        .options(selectinload(SupplierQuoteUpload.supplier))
    )
    if upload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archivo no encontrado")
    ensure_same_company(current_user, upload, db=db)
    path = Path(upload.stored_file_path)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archivo no disponible")
    media_types = {
        ".pdf": "application/pdf",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xls": "application/vnd.ms-excel",
    }
    media_type = media_types.get(upload.file_extension.lower(), "application/octet-stream")
    return FileResponse(
        path,
        media_type=media_type,
        filename=upload.original_file_name,
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.delete("/supplier-quotes/{quote_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_supplier_quote(
    quote_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("supplier_quotes", "edit")),
) -> None:
    quote = db.scalar(
        select(SupplierQuote)
        .where(SupplierQuote.id == quote_id)
        .options(
            selectinload(SupplierQuote.rfq).selectinload(SupplierRFQ.quotes),
            selectinload(SupplierQuote.rfq).selectinload(SupplierRFQ.items),
            selectinload(SupplierQuote.rfq).selectinload(SupplierRFQ.supplier_links),
            selectinload(SupplierQuote.supplier),
            selectinload(SupplierQuote.items),
            selectinload(SupplierQuote.purchase_order),
            selectinload(SupplierQuote.approval),
        )
    )
    if quote is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro no encontrado")
    ensure_same_company(current_user, quote, db=db)
    if quote.rfq.status in {"approval_pending", "awarded"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede borrar una cotizacion que ya esta en aprobacion o adjudicada",
        )
    if quote.purchase_order is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede borrar una cotizacion con orden de compra",
        )
    if quote.approval is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede borrar una cotizacion con historial de aprobacion",
        )
    if quote.status != "received":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se pueden corregir cotizaciones recibidas antes de aprobacion",
        )

    rfq = quote.rfq
    supplier_name = quote.supplier.name if quote.supplier else str(quote.supplier_id)
    link = next((item for item in rfq.supplier_links if item.supplier_id == quote.supplier_id), None)
    if link is not None:
        link.status = "sent" if rfq.status in {"sent", "quoted", "partially_quoted"} else "invited"
    record_event(
        db,
        current_user,
        module="compras",
        action="delete",
        entity_type="SupplierQuote",
        entity_id=quote.id,
        company_id=quote.company_id,
        label=quote.quote_number or rfq.rfq_number,
        description=f"{current_user.full_name} borro la cotizacion de {supplier_name} para recaptura",
        metadata={"rfq_id": rfq.id, "supplier_id": quote.supplier_id},
    )
    db.delete(quote)
    db.flush()
    remaining_quotes = [item for item in rfq.quotes if item.id != quote.id]
    if not remaining_quotes:
        rfq.status = "sent"
    elif all(len(item.items) == len(rfq.items) for item in remaining_quotes):
        rfq.status = "quoted"
    else:
        rfq.status = "partially_quoted"
    db.commit()


@router.get("/supplier-rfqs/{rfq_id}/comparison", response_model=list[SupplierRFQComparisonRow])
def supplier_rfq_comparison(
    rfq_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("supplier_quotes", "compare")),
) -> list[SupplierRFQComparisonRow]:
    rfq = get_supplier_rfq(rfq_id, db, current_user)
    quotes = list_supplier_quotes(rfq.id, db, current_user)
    total_items = len(rfq.items)
    return [
        SupplierRFQComparisonRow(
            supplier_quote_id=quote.id,
            supplier_id=quote.supplier_id,
            supplier_name=quote.supplier.name if quote.supplier else str(quote.supplier_id),
            subtotal=quote.subtotal,
            delivery_days=quote.delivery_days,
            payment_terms_days=quote.payment_terms_days,
            status=quote.status,
            complete_items=len(quote.items),
            total_items=total_items,
        )
        for quote in quotes
    ]


@router.post(
    "/supplier-rfqs/{rfq_id}/request-approval",
    response_model=SupplierQuoteApprovalRead,
    status_code=status.HTTP_201_CREATED,
)
def request_supplier_rfq_approval(
    rfq_id: int,
    payload: SupplierRFQApprovalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("supplier_quotes", "request_approval")),
) -> SupplierQuoteApproval:
    rfq = db.scalar(
        select(SupplierRFQ)
        .where(SupplierRFQ.id == rfq_id)
        .options(
            selectinload(SupplierRFQ.supplier_agreement).selectinload(SupplierAgreement.supplier),
            selectinload(SupplierRFQ.items),
            selectinload(SupplierRFQ.quotes).selectinload(SupplierQuote.supplier),
            selectinload(SupplierRFQ.quotes).selectinload(SupplierQuote.items),
            selectinload(SupplierRFQ.quotes).selectinload(SupplierQuote.purchase_order),
            selectinload(SupplierRFQ.quotes).selectinload(SupplierQuote.approval),
        )
    )
    if rfq is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro no encontrado")
    ensure_same_company(current_user, rfq, db=db)
    if rfq.status == "awarded":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La solicitud ya tiene una cotizacion aprobada",
        )
    pending = db.scalar(
        select(SupplierQuoteApproval)
        .where(
            SupplierQuoteApproval.rfq_id == rfq.id,
            SupplierQuoteApproval.status == "requested",
        )
        .options(*_approval_options())
    )
    if pending is not None:
        return pending

    total_items = len(rfq.items)
    complete_quotes = sorted(
        [
            quote
            for quote in rfq.quotes
            if quote.purchase_order is None
            and quote.status in {"received", "rejected", "approval_requested"}
            and len(quote.items) == total_items
        ],
        key=lambda quote: quote.subtotal,
    )
    is_agreement_flow = rfq.request_type == "agreement" and rfq.supplier_agreement_id is not None
    if payload.is_exception:
        if not complete_quotes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Para solicitar excepcion se requiere al menos una cotizacion completa",
            )
        if not payload.request_notes or not payload.request_notes.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Captura el motivo de la excepcion",
            )
    elif not is_agreement_flow and len(complete_quotes) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Se requieren 3 cotizaciones completas o solicitar una excepcion",
        )
    elif is_agreement_flow and not complete_quotes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La solicitud por convenio requiere una cotizacion completa",
        )

    reference_quote = complete_quotes[0]
    requested_at = _now()
    request_notes = payload.request_notes.strip() if payload.request_notes else None
    if payload.is_exception:
        request_notes = f"EXCEPCION:\n{request_notes}"
    elif is_agreement_flow:
        agreement_name = rfq.supplier_agreement.name if rfq.supplier_agreement else "convenio"
        request_notes = f"CONVENIO:\nCotizacion directa por {agreement_name}."

    approval = reference_quote.approval
    if approval is None:
        approval = SupplierQuoteApproval(
            company_id=reference_quote.company_id,
            rfq_id=rfq.id,
            supplier_quote_id=reference_quote.id,
            status="requested",
            request_notes=request_notes,
            requested_by=current_user.id,
            requested_at=requested_at,
        )
        db.add(approval)
    else:
        approval.status = "requested"
        approval.request_notes = request_notes
        approval.decision_notes = None
        approval.requested_by = current_user.id
        approval.requested_at = requested_at
        approval.decided_by = None
        approval.decided_at = None
    reference_quote.status = "approval_requested"
    rfq.status = "approval_pending"
    db.flush()
    record_event(
        db,
        current_user,
        module="compras",
        action=(
            "request_approval_exception"
            if payload.is_exception
            else "request_approval_agreement"
            if is_agreement_flow
            else "request_approval"
        ),
        entity_type="SupplierRFQ",
        entity_id=rfq.id,
        company_id=rfq.company_id,
        label=rfq.rfq_number,
        description=(
            f"{current_user.full_name} solicito aprobacion del comparativo "
            f"{rfq.rfq_number}"
        ),
        metadata={
            "quotes": len(complete_quotes),
            "is_exception": payload.is_exception,
            "is_agreement": is_agreement_flow,
            "supplier_agreement_id": rfq.supplier_agreement_id,
            "reference_quote_id": reference_quote.id,
        },
    )
    notify_permission(
        db,
        company_id=rfq.company_id,
        module="supplier_quotes",
        action="approve",
        notification_type="supplier_quote_approval_requested",
        title="Cotizacion por convenio pendiente" if is_agreement_flow else "Comparativo pendiente de aprobar",
        body=(
            f"{current_user.full_name} solicito aprobar '{rfq.title}' por convenio."
            if is_agreement_flow
            else (
                f"{current_user.full_name} solicito aprobar '{rfq.title}' "
                f"con {len(complete_quotes)} cotizacion(es)."
            )
        ),
        category="info" if is_agreement_flow else ("exception" if payload.is_exception else "task"),
        priority="high",
        source_module="compras",
        entity_type="SupplierQuoteApproval",
        entity_id=approval.id,
        entity_label=rfq.rfq_number,
        action_url="/purchasing/approvals",
        project_id=rfq.project_id,
        metadata={
            "rfq_id": rfq.id,
            "quotes": len(complete_quotes),
            "is_exception": payload.is_exception,
            "is_agreement": is_agreement_flow,
            "supplier_agreement_id": rfq.supplier_agreement_id,
            "reference_quote_id": reference_quote.id,
        },
    )
    db.commit()
    db.refresh(approval)
    return _get_supplier_quote_approval(db, approval.id, current_user)


def _supplier_quote_for_approval(db: Session, quote_id: int, current_user: User) -> SupplierQuote:
    quote = db.scalar(
        select(SupplierQuote)
        .where(SupplierQuote.id == quote_id)
        .options(
            selectinload(SupplierQuote.supplier),
            selectinload(SupplierQuote.items),
            selectinload(SupplierQuote.purchase_order),
            selectinload(SupplierQuote.approval),
            selectinload(SupplierQuote.rfq).selectinload(SupplierRFQ.creator),
            selectinload(SupplierQuote.rfq).selectinload(SupplierRFQ.items),
            selectinload(SupplierQuote.rfq).selectinload(SupplierRFQ.quotes),
            selectinload(SupplierQuote.rfq)
            .selectinload(SupplierRFQ.supplier_links)
            .selectinload(SupplierRFQSupplier.supplier),
        )
    )
    if quote is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro no encontrado")
    ensure_same_company(current_user, quote, db=db)
    return quote


def _approval_options():
    return (
        selectinload(SupplierQuoteApproval.requester),
        selectinload(SupplierQuoteApproval.decider),
        selectinload(SupplierQuoteApproval.supplier_quote).selectinload(SupplierQuote.supplier),
        selectinload(SupplierQuoteApproval.supplier_quote).selectinload(SupplierQuote.items),
        selectinload(SupplierQuoteApproval.rfq).selectinload(SupplierRFQ.creator),
        selectinload(SupplierQuoteApproval.rfq).selectinload(SupplierRFQ.items),
        selectinload(SupplierQuoteApproval.rfq)
        .selectinload(SupplierRFQ.supplier_links)
        .selectinload(SupplierRFQSupplier.supplier),
    )


def _get_supplier_quote_approval(
    db: Session,
    approval_id: int,
    current_user: User,
) -> SupplierQuoteApproval:
    approval = db.scalar(
        select(SupplierQuoteApproval)
        .where(SupplierQuoteApproval.id == approval_id)
        .options(*_approval_options())
    )
    if approval is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro no encontrado")
    ensure_same_company(current_user, approval, db=db)
    return approval


@router.get("/supplier-quote-approvals", response_model=list[SupplierQuoteApprovalRead])
def list_supplier_quote_approvals(
    approval_status: str = "requested",
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("supplier_quotes", "approve")),
) -> list[SupplierQuoteApproval]:
    statement = scoped_select(select(SupplierQuoteApproval), SupplierQuoteApproval, current_user)
    if approval_status != "all":
        statement = statement.where(SupplierQuoteApproval.status == approval_status)
    return list(
        db.scalars(
            statement.options(*_approval_options())
            .order_by(SupplierQuoteApproval.requested_at.desc())
            .offset(skip)
            .limit(limit)
        ).all()
    )


@router.post(
    "/supplier-quotes/{quote_id}/request-approval",
    response_model=SupplierQuoteApprovalRead,
    status_code=status.HTTP_201_CREATED,
)
def request_supplier_quote_approval(
    quote_id: int,
    payload: SupplierQuoteApprovalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("supplier_quotes", "request_approval")),
) -> SupplierQuoteApproval:
    quote = _supplier_quote_for_approval(db, quote_id, current_user)
    if quote.purchase_order is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La cotizacion ya tiene orden de compra",
        )
    if quote.rfq.status == "awarded":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La solicitud ya tiene una cotizacion aprobada",
        )
    pending = db.scalar(
        select(SupplierQuoteApproval)
        .where(
            SupplierQuoteApproval.rfq_id == quote.rfq_id,
            SupplierQuoteApproval.status == "requested",
        )
        .options(*_approval_options())
    )
    if pending is not None and pending.supplier_quote_id != quote.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una cotizacion pendiente de aprobacion para esta solicitud",
        )
    if quote.status not in {"received", "rejected", "approval_requested"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se puede solicitar aprobacion de una cotizacion recibida o rechazada",
        )

    approval = quote.approval
    requested_at = _now()
    if approval is None:
        approval = SupplierQuoteApproval(
            company_id=quote.company_id,
            rfq_id=quote.rfq_id,
            supplier_quote_id=quote.id,
            status="requested",
            request_notes=payload.request_notes,
            requested_by=current_user.id,
            requested_at=requested_at,
        )
        db.add(approval)
    else:
        approval.status = "requested"
        approval.request_notes = payload.request_notes
        approval.decision_notes = None
        approval.requested_by = current_user.id
        approval.requested_at = requested_at
        approval.decided_by = None
        approval.decided_at = None
    quote.status = "approval_requested"
    quote.rfq.status = "approval_pending"
    db.flush()
    record_event(
        db,
        current_user,
        module="compras",
        action="request_approval",
        entity_type="SupplierQuote",
        entity_id=quote.id,
        company_id=quote.company_id,
        label=quote.quote_number or quote.rfq.rfq_number,
        description=(
            f"{current_user.full_name} solicito aprobacion para la cotizacion "
            f"de {quote.supplier.name if quote.supplier else 'proveedor'}"
        ),
        metadata={"rfq_id": quote.rfq_id, "supplier_id": quote.supplier_id, "subtotal": str(quote.subtotal)},
    )
    notify_permission(
        db,
        company_id=quote.company_id,
        module="supplier_quotes",
        action="approve",
        notification_type="supplier_quote_approval_requested",
        title="Cotizacion pendiente de aprobar",
        body=(
            f"{current_user.full_name} solicito aprobar la cotizacion de "
            f"{quote.supplier.name if quote.supplier else 'proveedor'} para {quote.rfq.rfq_number}."
        ),
        category="task",
        priority="high",
        source_module="compras",
        entity_type="SupplierQuoteApproval",
        entity_id=approval.id,
        entity_label=quote.quote_number or quote.rfq.rfq_number,
        action_url="/purchasing/approvals",
        project_id=quote.rfq.project_id,
        metadata={"rfq_id": quote.rfq_id, "supplier_id": quote.supplier_id, "subtotal": str(quote.subtotal)},
    )
    db.commit()
    db.refresh(approval)
    return _get_supplier_quote_approval(db, approval.id, current_user)


@router.post("/supplier-quotes/{quote_id}/approve", response_model=PurchaseOrderApprovalRead)
def approve_supplier_quote(
    quote_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("supplier_quotes", "approve")),
) -> dict:
    quote = _supplier_quote_for_approval(db, quote_id, current_user)
    if quote.purchase_order is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La cotizacion ya tiene orden de compra",
        )
    pending_approval = quote.approval if quote.approval and quote.approval.status == "requested" else None
    if pending_approval is None:
        pending_approval = db.scalar(
            select(SupplierQuoteApproval)
            .where(
                SupplierQuoteApproval.rfq_id == quote.rfq_id,
                SupplierQuoteApproval.status == "requested",
            )
            .options(*_approval_options())
        )
    if pending_approval is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La solicitud no tiene una aprobacion pendiente",
        )
    if quote.status not in {"received", "approval_requested", "rejected"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se puede aprobar una cotizacion recibida o pendiente de aprobacion",
        )
    rfq = quote.rfq
    requested_quote_id = pending_approval.supplier_quote_id
    if requested_quote_id != quote.id:
        if quote.approval is not None and quote.approval.id != pending_approval.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La cotizacion seleccionada ya tiene otro historial de aprobacion",
            )
        pending_approval.supplier_quote_id = quote.id
        pending_approval.supplier_quote = quote
    project = _project_for_user(db, rfq.project_id, current_user)
    warehouse = _warehouse_for_project(db, rfq.warehouse_id, project)
    purchase_order = PurchaseOrder(
        company_id=quote.company_id,
        project_id=project.id,
        warehouse_id=warehouse.id if warehouse else None,
        supplier_id=quote.supplier_id,
        supplier_quote_id=quote.id,
        po_number=_next_number(db, PurchaseOrder, "po_number", "OC", quote.company_id),
        status="issued",
        issued_at=date.today(),
        payment_terms_days=quote.payment_terms_days,
        subtotal=quote.subtotal,
        notes=quote.notes,
        approved_by=current_user.id,
        approved_at=_now(),
    )
    db.add(purchase_order)
    db.flush()
    record_event(
        db,
        current_user,
        module="compras",
        action="approve",
        entity_type="SupplierQuote",
        entity_id=quote.id,
        company_id=quote.company_id,
        label=quote.quote_number or f"Cotizacion proveedor {quote.id}",
        description=(
            f"{current_user.full_name} aprobo la cotizacion del proveedor "
            f"y genero la orden {purchase_order.po_number}"
        ),
        metadata={
            "supplier_id": quote.supplier_id,
            "subtotal": str(quote.subtotal),
            "requested_quote_id": requested_quote_id,
            "approved_quote_id": quote.id,
        },
    )
    record_create(db, current_user, module="ordenes_compra", item=purchase_order)

    expected_list = ExpectedMaterialList(
        company_id=quote.company_id,
        project_id=project.id,
        warehouse_id=warehouse.id if warehouse else None,
        purchase_order_id=purchase_order.id,
        name=f"OC {purchase_order.po_number}",
        document_number=purchase_order.po_number,
        supplier_name=quote.supplier.name if quote.supplier else None,
        document_date=purchase_order.issued_at,
        delivery_date=purchase_order.expected_delivery_date,
        source_document_name=f"{purchase_order.po_number}.pdf",
        source_notes="Lista esperada generada automaticamente desde orden de compra.",
        status="open",
    )
    db.add(expected_list)
    db.flush()

    for quote_item in quote.items:
        po_item = PurchaseOrderItem(
            purchase_order_id=purchase_order.id,
            rfq_item_id=quote_item.rfq_item_id,
            material_id=quote_item.material_id,
            description=quote_item.description,
            unit=quote_item.unit,
            quantity_ordered=quote_item.quantity,
            unit_price=quote_item.unit_price,
            line_total=quote_item.line_total,
            received_quantity=Decimal("0"),
            status="pending",
            notes=quote_item.notes,
        )
        db.add(po_item)
        db.flush()
        db.add(
            ExpectedMaterialItem(
                company_id=quote.company_id,
                expected_list_id=expected_list.id,
                material_id=quote_item.material_id,
                purchase_order_item_id=po_item.id,
                description=quote_item.description,
                unit=quote_item.unit,
                expected_quantity=quote_item.quantity,
                unit_price=quote_item.unit_price,
                line_total=quote_item.line_total,
                received_quantity=Decimal("0"),
                status="pending",
                notes=quote_item.notes,
            )
        )
    quote.status = "approved"
    pending_approval.status = "approved"
    pending_approval.decided_by = current_user.id
    pending_approval.decided_at = _now()
    rfq.status = "awarded"
    material_requisition = db.scalar(
        select(MaterialRequisition)
        .where(
            MaterialRequisition.converted_rfq_id == rfq.id,
            MaterialRequisition.company_id == rfq.company_id,
        )
        .options(selectinload(MaterialRequisition.items))
    )
    if material_requisition is not None:
        material_requisition.status = "ordered_to_suppliers"
        material_requisition.review_notes = (
            f"Compras realizo el pedido a proveedores mediante {purchase_order.po_number}."
        )
        for requisition_item in material_requisition.items:
            requisition_item.status = "ordered"
    for rfq_quote in rfq.quotes:
        if rfq_quote.id != quote.id and rfq_quote.status != "approved":
            rfq_quote.status = "discarded"
    for link in rfq.supplier_links:
        link.status = "awarded" if link.supplier_id == quote.supplier_id else "declined"
    resolve_notifications(
        db,
        company_id=quote.company_id,
        notification_type="supplier_quote_approval_requested",
        entity_type="SupplierQuoteApproval",
        entity_id=pending_approval.id,
    )
    notify_user_id(
        db,
        user_id=pending_approval.requested_by or rfq.created_by,
        company_id=quote.company_id,
        notification_type="supplier_quote_approved",
        title="Cotizacion aprobada",
        body=(
            f"Se aprobo {quote.supplier.name if quote.supplier else 'el proveedor'} "
            f"y se genero la orden {purchase_order.po_number}."
        ),
        category="info",
        priority="normal",
        source_module="compras",
        entity_type="PurchaseOrder",
        entity_id=purchase_order.id,
        entity_label=purchase_order.po_number,
        action_url="/purchasing",
        project_id=rfq.project_id,
        metadata={"rfq_id": rfq.id, "quote_id": quote.id, "purchase_order_id": purchase_order.id},
    )
    notify_permission(
        db,
        company_id=quote.company_id,
        module="inventory",
        action="receive",
        notification_type="purchase_order_ready_to_receive",
        title="OC lista para recibir",
        body=f"{purchase_order.po_number} quedo lista para recepcion en inventario.",
        category="task",
        priority="normal",
        source_module="inventario",
        entity_type="PurchaseOrder",
        entity_id=purchase_order.id,
        entity_label=purchase_order.po_number,
        action_url="/inventory/purchase-order-receiving",
        project_id=rfq.project_id,
        metadata={"supplier_id": quote.supplier_id, "subtotal": str(quote.subtotal)},
    )
    db.commit()
    db.refresh(purchase_order)
    db.refresh(expected_list)
    return {"purchase_order": purchase_order, "expected_list": expected_list}


@router.post("/supplier-quotes/{quote_id}/reject-approval", response_model=SupplierQuoteApprovalRead)
def reject_supplier_quote_approval(
    quote_id: int,
    payload: SupplierQuoteApprovalDecision,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("supplier_quotes", "approve")),
) -> SupplierQuoteApproval:
    quote = _supplier_quote_for_approval(db, quote_id, current_user)
    if quote.approval is None or quote.approval.status != "requested":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La cotizacion no tiene una solicitud de aprobacion pendiente",
        )
    quote.status = "rejected"
    quote.approval.status = "rejected"
    quote.approval.decision_notes = payload.decision_notes
    quote.approval.decided_by = current_user.id
    quote.approval.decided_at = _now()
    remaining_requested = db.scalar(
        select(SupplierQuoteApproval.id).where(
            SupplierQuoteApproval.rfq_id == quote.rfq_id,
            SupplierQuoteApproval.status == "requested",
            SupplierQuoteApproval.supplier_quote_id != quote.id,
        )
    )
    if remaining_requested is None and quote.rfq.status == "approval_pending":
        quote.rfq.status = "quoted"
    record_event(
        db,
        current_user,
        module="compras",
        action="reject",
        entity_type="SupplierQuote",
        entity_id=quote.id,
        company_id=quote.company_id,
        label=quote.quote_number or quote.rfq.rfq_number,
        description=f"{current_user.full_name} rechazo la cotizacion solicitada para aprobacion",
        metadata={"rfq_id": quote.rfq_id, "supplier_id": quote.supplier_id},
    )
    resolve_notifications(
        db,
        company_id=quote.company_id,
        notification_type="supplier_quote_approval_requested",
        entity_type="SupplierQuoteApproval",
        entity_id=quote.approval.id,
    )
    notify_user_id(
        db,
        user_id=quote.approval.requested_by or quote.rfq.created_by,
        company_id=quote.company_id,
        notification_type="supplier_quote_rejected",
        title="Cotizacion rechazada",
        body=f"La aprobacion de {quote.rfq.rfq_number} fue rechazada.",
        category="warning",
        priority="high",
        source_module="compras",
        entity_type="SupplierQuoteApproval",
        entity_id=quote.approval.id,
        entity_label=quote.quote_number or quote.rfq.rfq_number,
        action_url="/purchasing",
        project_id=quote.rfq.project_id,
        metadata={"decision_notes": quote.approval.decision_notes},
    )
    db.commit()
    return _get_supplier_quote_approval(db, quote.approval.id, current_user)


@router.get("/purchase-orders", response_model=list[PurchaseOrderRead])
def list_purchase_orders(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("purchase_orders", "view")),
) -> list[PurchaseOrder]:
    statement = scoped_select(select(PurchaseOrder), PurchaseOrder, current_user)
    return list(
        db.scalars(
            statement.options(selectinload(PurchaseOrder.supplier), selectinload(PurchaseOrder.items))
            .order_by(PurchaseOrder.created_at.desc())
            .offset(skip)
            .limit(limit)
        ).all()
    )


@router.get("/purchase-orders/{purchase_order_id}", response_model=PurchaseOrderRead)
def get_purchase_order(
    purchase_order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("purchase_orders", "view")),
) -> PurchaseOrder:
    purchase_order = db.scalar(
        select(PurchaseOrder)
        .where(PurchaseOrder.id == purchase_order_id)
        .options(
            selectinload(PurchaseOrder.project),
            selectinload(PurchaseOrder.supplier),
            selectinload(PurchaseOrder.items),
        )
    )
    if purchase_order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro no encontrado")
    ensure_same_company(current_user, purchase_order, db=db)
    return purchase_order


@router.post("/purchase-orders/{purchase_order_id}/send", response_model=PurchaseOrderRead)
def send_purchase_order(
    purchase_order_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("purchase_orders", "send")),
) -> PurchaseOrder:
    purchase_order = get_purchase_order(purchase_order_id, db, current_user)
    if purchase_order.status not in {"issued", "sent"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se pueden enviar ordenes de compra emitidas.",
        )
    queued_email = _queue_purchase_order_email(db, purchase_order, requested_by=current_user.id)
    if purchase_order.status == "issued":
        purchase_order.status = "sent"
    record_event(
        db,
        current_user,
        module="ordenes_compra",
        action="send",
        entity_type="PurchaseOrder",
        entity_id=purchase_order.id,
        company_id=purchase_order.company_id,
        label=purchase_order.po_number,
        description=f"{current_user.full_name} envio la orden de compra {purchase_order.po_number}",
        metadata={"status": purchase_order.status, "correo_encolado": queued_email},
    )
    db.commit()
    if queued_email:
        background_tasks.add_task(process_email_outbox_for_company, purchase_order.company_id)
    return get_purchase_order(purchase_order_id, db, current_user)


@router.patch("/purchase-orders/{purchase_order_id}/billing-mode", response_model=PurchaseOrderRead)
def update_purchase_order_billing_mode(
    purchase_order_id: int,
    payload: PurchaseOrderBillingModeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("purchase_orders", "send")),
) -> PurchaseOrder:
    purchase_order = get_purchase_order(purchase_order_id, db, current_user)
    if purchase_order.billing_mode != payload.billing_mode:
        invoice_count = db.scalar(
            select(func.count(SupplierInvoice.id)).where(
                SupplierInvoice.purchase_order_id == purchase_order.id
            )
        )
        if invoice_count:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede cambiar el modo de facturacion cuando la orden ya tiene facturas registradas.",
            )
    before = snapshot(purchase_order, ["billing_mode"])
    purchase_order.billing_mode = payload.billing_mode
    record_update(db, current_user, module="ordenes_compra", item=purchase_order, before=before)
    db.commit()
    return get_purchase_order(purchase_order_id, db, current_user)


@router.get("/supplier-invoices", response_model=list[SupplierInvoiceRead])
def list_supplier_invoices(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("supplier_invoices", "view")),
) -> list[SupplierInvoice]:
    statement = scoped_select(select(SupplierInvoice), SupplierInvoice, current_user)
    return list(
        db.scalars(
            statement.options(
                selectinload(SupplierInvoice.supplier),
                selectinload(SupplierInvoice.purchase_order)
                .selectinload(PurchaseOrder.items),
                selectinload(SupplierInvoice.items),
            )
            .order_by(SupplierInvoice.due_date, SupplierInvoice.created_at.desc())
            .offset(skip)
            .limit(limit)
        ).all()
    )


@router.post("/supplier-invoices", response_model=SupplierInvoiceRead, status_code=status.HTTP_201_CREATED)
def create_supplier_invoice(
    payload: SupplierInvoiceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("supplier_invoices", "upload")),
) -> SupplierInvoice:
    purchase_order = get_purchase_order(payload.purchase_order_id, db, current_user)
    supplier = purchase_order.supplier
    if purchase_order.billing_mode == "partial" and not payload.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Captura las partidas facturadas para una orden en modo parcial.",
        )
    if purchase_order.billing_mode != "partial" and payload.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cambia la orden a facturacion parcial antes de capturar partidas.",
        )
    due_date = payload.due_date or invoice_due_date(
        payload.invoice_date,
        purchase_order.payment_terms_days,
    )
    po_item_by_id = {item.id: item for item in purchase_order.items}
    invoice_items: list[SupplierInvoiceItem] = []
    items_total = Decimal("0")
    for item_payload in payload.items:
        po_item = po_item_by_id.get(item_payload.purchase_order_item_id)
        if po_item is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Una partida de factura no pertenece a la orden de compra.",
            )
        unit_price = item_payload.unit_price if item_payload.unit_price is not None else po_item.unit_price
        line_total = (item_payload.quantity * unit_price).quantize(Decimal("0.01"))
        items_total += line_total
        invoice_items.append(
            SupplierInvoiceItem(
                purchase_order_item_id=po_item.id,
                material_id=po_item.material_id,
                description=po_item.description,
                unit=po_item.unit,
                quantity=item_payload.quantity,
                unit_price=unit_price,
                line_total=line_total,
                notes=item_payload.notes,
            )
        )
    if invoice_items and abs(items_total - payload.total) > Decimal("0.01"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El total de la factura no coincide con las partidas capturadas.",
        )
    invoice = SupplierInvoice(
        company_id=purchase_order.company_id,
        supplier_id=supplier.id,
        purchase_order_id=purchase_order.id,
        invoice_number=payload.invoice_number,
        invoice_date=payload.invoice_date,
        due_date=due_date,
        subtotal=items_total if invoice_items else payload.subtotal,
        total=payload.total,
        status="received",
        document_name=payload.document_name,
        notes=payload.notes,
        validated_at=_now(),
        validated_by=current_user.id,
    )
    db.add(invoice)
    db.flush()
    for invoice_item in invoice_items:
        invoice_item.supplier_invoice_id = invoice.id
        db.add(invoice_item)
    db.flush()
    invoice = db.scalar(
        select(SupplierInvoice)
        .where(SupplierInvoice.id == invoice.id)
        .options(
            selectinload(SupplierInvoice.items).selectinload(SupplierInvoiceItem.purchase_order_item),
            selectinload(SupplierInvoice.purchase_order).selectinload(PurchaseOrder.items),
        )
    )
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro no encontrado")
    invoice_status, _pending, message = _invoice_status(invoice, db)
    invoice.status = invoice_status
    invoice.notes = payload.notes or message
    if invoice_status == "approved_for_payment":
        if not invoice.items:
            invoice.purchase_order.status = "factured"
    db.flush()
    record_create(db, current_user, module="facturas_proveedor", item=invoice)
    if invoice_status == "approved_for_payment":
        notify_permission(
            db,
            company_id=invoice.company_id,
            module="supplier_payments",
            action="view",
            notification_type="supplier_invoice_ready_to_pay",
            title="Factura lista para pago",
            body=f"La factura {invoice.invoice_number} esta validada y lista para gestion de pago.",
            category="task",
            priority="normal",
            source_module="pagos_proveedores",
            entity_type="SupplierInvoice",
            entity_id=invoice.id,
            entity_label=invoice.invoice_number,
            action_url="/supplier-payments",
            project_id=purchase_order.project_id,
            metadata={"purchase_order_id": purchase_order.id, "total": str(invoice.total)},
        )
    else:
        notify_permission(
            db,
            company_id=invoice.company_id,
            module="inventory",
            action="receive",
            notification_type="supplier_invoice_blocked",
            title="Factura bloqueada por material pendiente",
            body=f"La factura {invoice.invoice_number} no puede pagarse hasta completar la recepcion.",
            category="warning",
            priority="high",
            source_module="inventario",
            entity_type="SupplierInvoice",
            entity_id=invoice.id,
            entity_label=invoice.invoice_number,
            action_url="/inventory/purchase-order-receiving",
            project_id=purchase_order.project_id,
            metadata={"purchase_order_id": purchase_order.id, "total": str(invoice.total)},
        )
    db.commit()
    db.refresh(invoice)
    return invoice


@router.post("/supplier-invoices/{invoice_id}/validate", response_model=SupplierInvoiceValidation)
def validate_supplier_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("supplier_invoices", "validate")),
) -> SupplierInvoiceValidation:
    invoice = db.scalar(
        select(SupplierInvoice)
        .where(SupplierInvoice.id == invoice_id)
        .options(
            selectinload(SupplierInvoice.items).selectinload(SupplierInvoiceItem.purchase_order_item),
            selectinload(SupplierInvoice.purchase_order).selectinload(PurchaseOrder.items),
        )
    )
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro no encontrado")
    ensure_same_company(current_user, invoice, db=db)
    next_status, pending_items, message = _invoice_status(invoice, db)
    invoice.status = next_status
    invoice.validated_at = _now()
    invoice.validated_by = current_user.id
    invoice.notes = message
    record_event(
        db,
        current_user,
        module="facturas_proveedor",
        action="validate",
        entity_type="SupplierInvoice",
        entity_id=invoice.id,
        company_id=invoice.company_id,
        label=invoice.invoice_number,
        description=f"{current_user.full_name} valido la factura {invoice.invoice_number}",
        metadata={"status": next_status, "pendientes": pending_items},
    )
    if next_status == "approved_for_payment":
        resolve_notifications(
            db,
            company_id=invoice.company_id,
            notification_type="supplier_invoice_blocked",
            entity_type="SupplierInvoice",
            entity_id=invoice.id,
        )
        notify_permission(
            db,
            company_id=invoice.company_id,
            module="supplier_payments",
            action="view",
            notification_type="supplier_invoice_ready_to_pay",
            title="Factura lista para pago",
            body=f"La factura {invoice.invoice_number} ya no tiene material pendiente.",
            category="task",
            priority="normal",
            source_module="pagos_proveedores",
            entity_type="SupplierInvoice",
            entity_id=invoice.id,
            entity_label=invoice.invoice_number,
            action_url="/supplier-payments",
            project_id=invoice.purchase_order.project_id,
            metadata={"purchase_order_id": invoice.purchase_order_id, "total": str(invoice.total)},
        )
    db.commit()
    return SupplierInvoiceValidation(
        invoice_id=invoice.id,
        status=next_status,
        pending_items=pending_items,
        message=message,
    )


@router.get("/supplier-payments", response_model=list[SupplierPaymentRead])
def list_supplier_payments(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("supplier_payments", "view")),
) -> list[SupplierPayment]:
    statement = scoped_select(select(SupplierPayment), SupplierPayment, current_user)
    return list(
        db.scalars(
            statement.order_by(SupplierPayment.scheduled_date, SupplierPayment.created_at.desc())
            .offset(skip)
            .limit(limit)
        ).all()
    )


@router.post("/supplier-payments", response_model=SupplierPaymentRead, status_code=status.HTTP_201_CREATED)
def create_supplier_payment(
    payload: SupplierPaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("supplier_payments", "schedule")),
) -> SupplierPayment:
    invoice = get_or_404(db, SupplierInvoice, payload.supplier_invoice_id)
    ensure_same_company(current_user, invoice, db=db)
    if invoice.status not in {"approved_for_payment", "scheduled"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La factura no esta aprobada para pago",
        )
    payment = SupplierPayment(
        company_id=invoice.company_id,
        approved_by=current_user.id,
        **payload.model_dump(),
    )
    db.add(payment)
    invoice.status = "paid" if payment.status == "paid" else "scheduled"
    if invoice.status == "paid":
        purchase_order = db.scalar(
            select(PurchaseOrder)
            .where(PurchaseOrder.id == invoice.purchase_order_id)
            .options(selectinload(PurchaseOrder.items))
        )
        if purchase_order is not None:
            _sync_purchase_order_after_payment(db, purchase_order)
    db.flush()
    record_event(
        db,
        current_user,
        module="pagos_proveedores",
        action="pay" if payment.status == "paid" else "schedule",
        entity_type="SupplierPayment",
        entity_id=payment.id,
        company_id=payment.company_id,
        label=payment.reference or f"Pago {payment.id}",
        description=(
            f"{current_user.full_name} "
            f"{'registro pago' if payment.status == 'paid' else 'programo pago'} "
            f"de proveedor"
        ),
        metadata={"amount": str(payment.amount), "status": payment.status},
    )
    db.commit()
    db.refresh(payment)
    return payment


@router.patch("/supplier-payments/{payment_id}", response_model=SupplierPaymentRead)
def update_supplier_payment(
    payment_id: int,
    payload: SupplierPaymentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("supplier_payments", "pay")),
) -> SupplierPayment:
    payment = get_or_404(db, SupplierPayment, payment_id)
    ensure_same_company(current_user, payment, db=db)
    data = payload.model_dump(exclude_unset=True)
    before = snapshot(payment, list(data.keys()) + ["status"])
    for field, value in data.items():
        setattr(payment, field, value)
    updated = payment
    invoice = db.scalar(
        select(SupplierInvoice)
        .where(SupplierInvoice.id == updated.supplier_invoice_id)
        .options(selectinload(SupplierInvoice.purchase_order).selectinload(PurchaseOrder.items))
    )
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro no encontrado")
    if updated.status == "paid":
        invoice.status = "paid"
        _sync_purchase_order_after_payment(db, invoice.purchase_order)
    elif updated.status == "scheduled":
        invoice.status = "scheduled"
    record_update(db, current_user, module="pagos_proveedores", item=updated, before=before)
    db.commit()
    db.refresh(updated)
    return updated
