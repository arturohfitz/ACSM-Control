from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models import (
    ExpectedMaterialItem,
    ExpectedMaterialList,
    Material,
    Project,
    ProjectWarehouse,
    PurchaseOrder,
    PurchaseOrderItem,
    Supplier,
    SupplierInvoice,
    SupplierPayment,
    SupplierQuote,
    SupplierQuoteApproval,
    SupplierQuoteItem,
    SupplierRFQ,
    SupplierRFQExceptionRequest,
    SupplierRFQItem,
    SupplierRFQSupplier,
    SystemEmailSettings,
    User,
)
from app.schemas.purchasing import (
    PurchaseOrderApprovalRead,
    PurchaseOrderRead,
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
from app.services.emailer import EmailConfigurationError, rfq_email_content, send_email
from app.services.permissions import user_has_permission
from app.services.tenancy import company_id_for_write, ensure_same_company, scoped_select


router = APIRouter()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _project_for_user(db: Session, project_id: int, current_user: User) -> Project:
    project = get_or_404(db, Project, project_id)
    ensure_same_company(current_user, project)
    return project


def _supplier_for_user(db: Session, supplier_id: int, current_user: User) -> Supplier:
    supplier = get_or_404(db, Supplier, supplier_id)
    ensure_same_company(current_user, supplier)
    if supplier.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El proveedor no esta activo",
        )
    return supplier


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
    data = payload.model_dump(mode="json", exclude={"exception_request_id", "request_notes", "rfq_number", "notes", "warehouse_id"})
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


def _ensure_exception_matches_payload(
    exception_request: SupplierRFQExceptionRequest,
    payload: SupplierRFQCreate,
) -> None:
    if exception_request.status != "approved" or exception_request.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La excepcion aun no esta aprobada o ya fue utilizada",
        )
    if exception_request.payload_snapshot != _rfq_exception_snapshot(payload):
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


def _send_rfq_emails(db: Session, rfq: SupplierRFQ) -> tuple[int, int]:
    settings = db.scalar(
        select(SystemEmailSettings).where(
            SystemEmailSettings.company_id == rfq.company_id,
            SystemEmailSettings.is_active.is_(True),
        )
    )
    sent_at = _now()
    sent_count = 0
    error_count = 0
    subject, text_body, html_body = rfq_email_content(rfq)

    if settings is None:
        rfq.status = "email_error"
        rfq.notes = (rfq.notes or "") + "\nCorreo no enviado: falta configurar SMTP."
        for link in rfq.supplier_links:
            link.status = "email_error"
            link.notes = "Falta configurar SMTP en Ajustes."
        return sent_count, len(rfq.supplier_links)

    for link in rfq.supplier_links:
        supplier = link.supplier
        recipient = (supplier.contact_email or "").strip() if supplier else ""
        if not recipient:
            link.status = "missing_email"
            link.notes = "Proveedor sin correo de contacto."
            error_count += 1
            continue
        try:
            send_email(settings, [recipient], subject, text_body, html_body)
        except EmailConfigurationError as exc:
            link.status = "email_error"
            link.notes = str(exc)
            error_count += 1
            continue
        except Exception as exc:
            link.status = "email_error"
            link.notes = f"No fue posible enviar correo: {exc}"
            error_count += 1
            continue
        link.status = "sent"
        link.sent_at = sent_at
        link.notes = None
        sent_count += 1

    if sent_count:
        rfq.status = "sent"
        rfq.sent_at = sent_at
    else:
        rfq.status = "email_error"
    return sent_count, error_count


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
    ensure_same_company(current_user, supplier)
    return supplier


@router.patch("/suppliers/{supplier_id}", response_model=SupplierRead)
def update_supplier(
    supplier_id: int,
    payload: SupplierUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("suppliers", "edit")),
) -> Supplier:
    supplier = get_or_404(db, Supplier, supplier_id)
    ensure_same_company(current_user, supplier)
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
    ensure_same_company(current_user, supplier)
    record_delete(db, current_user, module="proveedores", item=supplier)
    db.delete(supplier)
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
            ensure_same_company(current_user, material)
    exception_request = SupplierRFQExceptionRequest(
        company_id=project.company_id,
        project_id=project.id,
        title=payload.title,
        required_by=payload.required_by,
        response_deadline=payload.response_deadline,
        supplier_count=supplier_count,
        item_count=len(payload.items),
        payload_snapshot=_rfq_exception_snapshot(payload),
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
    ensure_same_company(current_user, exception_request)
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
    ensure_same_company(current_user, exception_request)
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
    db.commit()
    db.refresh(exception_request)
    return exception_request


@router.post("/supplier-rfqs", response_model=SupplierRFQRead, status_code=status.HTTP_201_CREATED)
def create_supplier_rfq(
    payload: SupplierRFQCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("supplier_rfq", "create")),
) -> SupplierRFQ:
    project = _project_for_user(db, payload.project_id, current_user)
    warehouse = _warehouse_for_project(db, payload.warehouse_id, project)
    suppliers = [_supplier_for_user(db, supplier_id, current_user) for supplier_id in payload.supplier_ids]
    supplier_count = len({supplier.id for supplier in suppliers})
    approved_exception: SupplierRFQExceptionRequest | None = None
    if supplier_count < 3:
        if payload.exception_request_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Se requiere una excepcion aprobada para crear solicitud con menos de 3 proveedores",
            )
        approved_exception = get_or_404(db, SupplierRFQExceptionRequest, payload.exception_request_id)
        ensure_same_company(current_user, approved_exception)
        _ensure_exception_matches_payload(approved_exception, payload)
    rfq = SupplierRFQ(
        company_id=project.company_id,
        project_id=project.id,
        warehouse_id=warehouse.id if warehouse else None,
        rfq_number=payload.rfq_number
        or _next_number(db, SupplierRFQ, "rfq_number", "SC", project.company_id),
        title=payload.title,
        required_by=payload.required_by,
        response_deadline=payload.response_deadline,
        notes=payload.notes,
        created_by=current_user.id,
    )
    db.add(rfq)
    db.flush()
    for item in payload.items:
        if item.material_id is not None:
            material = get_or_404(db, Material, item.material_id)
            ensure_same_company(current_user, material)
        db.add(SupplierRFQItem(rfq_id=rfq.id, **item.model_dump()))
    for supplier in suppliers:
        db.add(SupplierRFQSupplier(rfq_id=rfq.id, supplier_id=supplier.id))
    if approved_exception is not None:
        approved_exception.status = "used"
        approved_exception.rfq_id = rfq.id
        approved_exception.used_at = _now()
    db.commit()
    rfq = db.scalar(
        select(SupplierRFQ)
        .where(SupplierRFQ.id == rfq.id)
        .options(
            selectinload(SupplierRFQ.creator),
            selectinload(SupplierRFQ.items),
            selectinload(SupplierRFQ.supplier_links).selectinload(SupplierRFQSupplier.supplier),
        )
    )
    if rfq is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro no encontrado")
    sent_count, error_count = _send_rfq_emails(db, rfq)
    record_event(
        db,
        current_user,
        module="compras",
        action="create",
        entity_type="SupplierRFQ",
        entity_id=rfq.id,
        company_id=rfq.company_id,
        label=rfq.rfq_number,
        description=f"{current_user.full_name} creo la solicitud a proveedores {rfq.rfq_number}",
        metadata={"proveedores": len(rfq.supplier_links), "enviados": sent_count, "errores": error_count},
    )
    db.commit()
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
            selectinload(SupplierRFQ.items),
            selectinload(SupplierRFQ.supplier_links).selectinload(SupplierRFQSupplier.supplier),
        )
    )
    if rfq is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro no encontrado")
    ensure_same_company(current_user, rfq)
    return rfq


@router.patch("/supplier-rfqs/{rfq_id}", response_model=SupplierRFQRead)
def update_supplier_rfq(
    rfq_id: int,
    payload: SupplierRFQUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("supplier_rfq", "edit")),
) -> SupplierRFQ:
    rfq = get_or_404(db, SupplierRFQ, rfq_id)
    ensure_same_company(current_user, rfq)
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
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("supplier_rfq", "send")),
) -> SupplierRFQ:
    rfq = get_supplier_rfq(rfq_id, db, current_user)
    sent_count, error_count = _send_rfq_emails(db, rfq)
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
        metadata={"enviados": sent_count, "errores": error_count},
    )
    db.commit()
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
    ensure_same_company(current_user, quote)
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
            selectinload(SupplierRFQ.items),
            selectinload(SupplierRFQ.quotes).selectinload(SupplierQuote.supplier),
            selectinload(SupplierRFQ.quotes).selectinload(SupplierQuote.items),
            selectinload(SupplierRFQ.quotes).selectinload(SupplierQuote.purchase_order),
            selectinload(SupplierRFQ.quotes).selectinload(SupplierQuote.approval),
        )
    )
    if rfq is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro no encontrado")
    ensure_same_company(current_user, rfq)
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
    elif len(complete_quotes) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Se requieren 3 cotizaciones completas o solicitar una excepcion",
        )

    reference_quote = complete_quotes[0]
    requested_at = _now()
    request_notes = payload.request_notes.strip() if payload.request_notes else None
    if payload.is_exception:
        request_notes = f"EXCEPCION:\n{request_notes}"

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
    record_event(
        db,
        current_user,
        module="compras",
        action="request_approval_exception" if payload.is_exception else "request_approval",
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
    ensure_same_company(current_user, quote)
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
    ensure_same_company(current_user, approval)
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
    for rfq_quote in rfq.quotes:
        if rfq_quote.id != quote.id and rfq_quote.status != "approved":
            rfq_quote.status = "discarded"
    for link in rfq.supplier_links:
        link.status = "awarded" if link.supplier_id == quote.supplier_id else "declined"
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
        .options(selectinload(PurchaseOrder.supplier), selectinload(PurchaseOrder.items))
    )
    if purchase_order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro no encontrado")
    ensure_same_company(current_user, purchase_order)
    return purchase_order


@router.post("/purchase-orders/{purchase_order_id}/send", response_model=PurchaseOrderRead)
def send_purchase_order(
    purchase_order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("purchase_orders", "send")),
) -> PurchaseOrder:
    purchase_order = get_purchase_order(purchase_order_id, db, current_user)
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
        metadata={"status": purchase_order.status},
    )
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
    invoice_status, _pending, message = _invoice_status_for_po(purchase_order)
    due_date = payload.due_date or invoice_due_date(
        payload.invoice_date,
        purchase_order.payment_terms_days,
    )
    invoice = SupplierInvoice(
        company_id=purchase_order.company_id,
        supplier_id=supplier.id,
        purchase_order_id=purchase_order.id,
        invoice_number=payload.invoice_number,
        invoice_date=payload.invoice_date,
        due_date=due_date,
        subtotal=payload.subtotal,
        total=payload.total,
        status=invoice_status,
        document_name=payload.document_name,
        notes=payload.notes or message,
        validated_at=_now(),
        validated_by=current_user.id,
    )
    db.add(invoice)
    if invoice_status == "approved_for_payment":
        purchase_order.status = "factured"
    db.flush()
    record_create(db, current_user, module="facturas_proveedor", item=invoice)
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
        .options(selectinload(SupplierInvoice.purchase_order).selectinload(PurchaseOrder.items))
    )
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro no encontrado")
    ensure_same_company(current_user, invoice)
    next_status, pending_items, message = _invoice_status_for_po(invoice.purchase_order)
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
    ensure_same_company(current_user, invoice)
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
    ensure_same_company(current_user, payment)
    data = payload.model_dump(exclude_unset=True)
    before = snapshot(payment, list(data.keys()) + ["status"])
    for field, value in data.items():
        setattr(payment, field, value)
    updated = payment
    invoice = get_or_404(db, SupplierInvoice, updated.supplier_invoice_id)
    if updated.status == "paid":
        invoice.status = "paid"
        invoice.purchase_order.status = "closed"
    elif updated.status == "scheduled":
        invoice.status = "scheduled"
    record_update(db, current_user, module="pagos_proveedores", item=updated, before=before)
    db.commit()
    db.refresh(updated)
    return updated
