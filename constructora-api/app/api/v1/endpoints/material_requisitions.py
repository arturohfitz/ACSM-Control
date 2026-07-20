from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_permission
from app.api.v1.endpoints.purchasing import (
    _ensure_unique_supplier_ids,
    _next_number,
    _queue_rfq_emails,
    _supplier_for_user,
    _warehouse_for_project,
)
from app.db.session import get_db
from app.models import (
    HouseModel,
    HouseModelMaterialRequirement,
    Material,
    MaterialUnitConversion,
    MaterialRequisition,
    MaterialRequisitionItem,
    PurchaseOrder,
    PurchaseOrderItem,
    Project,
    ProjectHouseModel,
    SupplierInvoice,
    SupplierQuote,
    SupplierRFQ,
    SupplierRFQItem,
    SupplierRFQSupplier,
    User,
)
from app.schemas.material_requisition import (
    AvailableRequirementRead,
    MaterialRequisitionConvertResult,
    MaterialRequisitionConvertToRFQ,
    MaterialRequisitionCreate,
    MaterialRequisitionRead,
    MaterialRequisitionReview,
    MaterialRequisitionTrackingItem,
    MaterialRequisitionTrackingRead,
    MaterialRequisitionTrackingStep,
    MaterialRequisitionUpdate,
)
from app.services.audit import record_event
from app.services.crud import get_or_404
from app.services.email_outbox import process_email_outbox_for_company
from app.services.notifications import notify_permission, notify_user_id, resolve_notifications
from app.services.permissions import user_has_permission
from app.services.tenancy import ensure_same_company, get_user_company_id, scoped_select


router = APIRouter()

ZERO = Decimal("0")
TrackingStepStatus = Literal["pending", "active", "complete", "blocked", "warning"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _requisition_options():
    return (
        selectinload(MaterialRequisition.requested_by),
        selectinload(MaterialRequisition.reviewed_by),
        selectinload(MaterialRequisition.project),
        selectinload(MaterialRequisition.house_model),
        selectinload(MaterialRequisition.items),
    )


def _can_manage_company_requisitions(user: User) -> bool:
    return user_has_permission(user, "material_requisitions", "review") or user_has_permission(
        user, "material_requisitions", "convert_to_rfq"
    )


def _ensure_same_requisition_company(current_user: User, requisition: MaterialRequisition) -> None:
    if current_user.is_master_admin:
        return
    if requisition.company_id != get_user_company_id(current_user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro no encontrado")


def _get_requisition_for_user(
    db: Session,
    requisition_id: int,
    current_user: User,
) -> MaterialRequisition:
    requisition = db.scalar(
        select(MaterialRequisition)
        .where(MaterialRequisition.id == requisition_id)
        .options(*_requisition_options())
    )
    if requisition is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro no encontrado")
    if _can_manage_company_requisitions(current_user):
        _ensure_same_requisition_company(current_user, requisition)
    else:
        ensure_same_company(current_user, requisition, db=db)
    return requisition


def _project_for_user(
    db: Session,
    project_id: int,
    current_user: User,
    *,
    company_scope: bool = False,
) -> Project:
    project = get_or_404(db, Project, project_id)
    if company_scope and _can_manage_company_requisitions(current_user):
        if not current_user.is_master_admin and project.company_id != get_user_company_id(current_user):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro no encontrado")
    else:
        ensure_same_company(current_user, project, db=db)
    return project


def _project_model_assignment(
    db: Session,
    project_id: int,
    house_model_id: int,
) -> ProjectHouseModel:
    assignment = db.scalar(
        select(ProjectHouseModel).where(
            ProjectHouseModel.project_id == project_id,
            ProjectHouseModel.house_model_id == house_model_id,
        )
    )
    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El modelo de casa no esta asignado al desarrollo seleccionado",
        )
    return assignment


def _requirement_for_requisition(
    db: Session,
    *,
    requirement_id: int,
    project: Project,
    house_model_id: int,
    current_user: User,
) -> HouseModelMaterialRequirement:
    requirement = get_or_404(db, HouseModelMaterialRequirement, requirement_id)
    ensure_same_company(current_user, requirement, db=db)
    if requirement.client_id != project.client_id or requirement.house_model_id != house_model_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La partida de material no pertenece al modelo o inmobiliaria seleccionada",
        )
    if requirement.material_id is not None:
        material = get_or_404(db, Material, requirement.material_id)
        ensure_same_company(current_user, material, db=db)
    return requirement


def _normalize_unit(value: str | None) -> str:
    return (value or "").strip().upper()


def _quantity_snapshot(
    db: Session,
    *,
    requirement: HouseModelMaterialRequirement,
    requested_unit: str,
    requested_quantity: Decimal,
) -> tuple[Decimal, Decimal]:
    base_unit = _normalize_unit(requirement.unit)
    normalized_requested_unit = _normalize_unit(requested_unit)
    if normalized_requested_unit == base_unit:
        return Decimal("1"), requested_quantity
    if requirement.material_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"{requirement.description} no esta vinculado al catalogo y no puede convertir "
                f"{normalized_requested_unit} a {base_unit}"
            ),
        )
    conversion = db.scalar(
        select(MaterialUnitConversion).where(
            MaterialUnitConversion.material_id == requirement.material_id,
            MaterialUnitConversion.from_unit == normalized_requested_unit,
            MaterialUnitConversion.to_unit == base_unit,
            MaterialUnitConversion.is_active.is_(True),
        )
    )
    if conversion is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Falta registrar la equivalencia de {normalized_requested_unit} a {base_unit} "
                f"para {requirement.description}"
            ),
        )
    return conversion.factor_to_base, requested_quantity * conversion.factor_to_base


def _item_base_quantity(db: Session, item: MaterialRequisitionItem) -> Decimal:
    if item.requested_base_quantity is not None:
        return item.requested_base_quantity
    if _normalize_unit(item.requested_unit) in {"", _normalize_unit(item.unit)}:
        return item.requested_quantity
    if item.material_id is None:
        return Decimal("0")
    conversion = db.scalar(
        select(MaterialUnitConversion).where(
            MaterialUnitConversion.material_id == item.material_id,
            MaterialUnitConversion.from_unit == _normalize_unit(item.requested_unit),
            MaterialUnitConversion.to_unit == _normalize_unit(item.unit),
            MaterialUnitConversion.is_active.is_(True),
        )
    )
    return item.requested_quantity * conversion.factor_to_base if conversion is not None else Decimal("0")


def _requested_base_by_requirement(
    db: Session,
    requirement_ids: list[int],
    *,
    project_id: int,
    exclude_requisition_id: int | None = None,
) -> dict[int, Decimal]:
    if not requirement_ids:
        return {}
    statement = (
        select(MaterialRequisitionItem)
        .join(MaterialRequisition)
        .where(
            MaterialRequisitionItem.house_model_material_requirement_id.in_(requirement_ids),
            MaterialRequisition.project_id == project_id,
            MaterialRequisition.status.notin_({"rejected", "cancelled"}),
        )
    )
    if exclude_requisition_id is not None:
        statement = statement.where(MaterialRequisitionItem.requisition_id != exclude_requisition_id)
    totals: dict[int, Decimal] = {}
    for item in db.scalars(statement).all():
        if item.house_model_material_requirement_id is None:
            continue
        totals[item.house_model_material_requirement_id] = (
            totals.get(item.house_model_material_requirement_id, Decimal("0"))
            + _item_base_quantity(db, item)
        )
    return totals


@router.get("/available-materials", response_model=list[AvailableRequirementRead])
def list_available_materials(
    project_id: int,
    house_model_id: int | None = None,
    q: str | None = None,
    limit: int = Query(default=250, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("material_requisitions", "view")),
) -> list[AvailableRequirementRead]:
    project = _project_for_user(db, project_id, current_user)
    assignments = list(
        db.scalars(
            select(ProjectHouseModel)
            .where(ProjectHouseModel.project_id == project.id)
            .options(selectinload(ProjectHouseModel.house_model))
        ).all()
    )
    if house_model_id is not None:
        assignments = [item for item in assignments if item.house_model_id == house_model_id]
    if not assignments:
        return []

    quantities_by_model = {item.house_model_id: item.quantity for item in assignments}
    model_names = {item.house_model_id: item.house_model.name for item in assignments}
    statement = (
        select(HouseModelMaterialRequirement)
        .where(
            HouseModelMaterialRequirement.house_model_id.in_(quantities_by_model),
            HouseModelMaterialRequirement.client_id == project.client_id,
        )
        .order_by(HouseModelMaterialRequirement.house_model_id, HouseModelMaterialRequirement.sort_order)
        .limit(limit)
    )
    if q:
        needle = f"%{q.strip()}%"
        statement = statement.where(
            or_(
                HouseModelMaterialRequirement.description.ilike(needle),
                HouseModelMaterialRequirement.source_code.ilike(needle),
                HouseModelMaterialRequirement.family.ilike(needle),
            )
        )
    requirements = list(db.scalars(statement).all())
    requested_by_requirement = _requested_base_by_requirement(
        db,
        [item.id for item in requirements],
        project_id=project.id,
    )
    return [
        AvailableRequirementRead(
            id=item.id,
            house_model_id=item.house_model_id,
            house_model_name=model_names.get(item.house_model_id, f"Modelo {item.house_model_id}"),
            material_id=item.material_id,
            source_code=item.source_code,
            description=item.description,
            unit=item.unit,
            quantity_per_house=item.quantity_per_house,
            assigned_houses=quantities_by_model[item.house_model_id],
            total_required=item.quantity_per_house * quantities_by_model[item.house_model_id],
            already_requested=requested_by_requirement.get(item.id, Decimal("0")),
            available_to_request=max(
                item.quantity_per_house * quantities_by_model[item.house_model_id]
                - requested_by_requirement.get(item.id, Decimal("0")),
                Decimal("0"),
            ),
            requested_percent=min(
                (
                    requested_by_requirement.get(item.id, Decimal("0"))
                    / (item.quantity_per_house * quantities_by_model[item.house_model_id])
                    * Decimal("100")
                )
                if item.quantity_per_house * quantities_by_model[item.house_model_id] > 0
                else Decimal("0"),
                Decimal("100"),
            ),
            validation_status=item.validation_status,
            family=item.family,
        )
        for item in requirements
    ]


@router.get("", response_model=list[MaterialRequisitionRead])
def list_material_requisitions(
    status_filter: str | None = None,
    project_id: int | None = None,
    client_id: int | None = None,
    q: str | None = None,
    skip: int = 0,
    limit: int = Query(default=100, ge=1, le=250),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("material_requisitions", "view")),
) -> list[MaterialRequisition]:
    base_statement = select(MaterialRequisition).options(*_requisition_options())
    if _can_manage_company_requisitions(current_user) and not current_user.is_master_admin:
        statement = base_statement.where(MaterialRequisition.company_id == get_user_company_id(current_user))
    else:
        statement = scoped_select(base_statement, MaterialRequisition, current_user)
    if status_filter:
        statement = statement.where(MaterialRequisition.status == status_filter)
    if project_id is not None:
        statement = statement.where(MaterialRequisition.project_id == project_id)
    if client_id is not None:
        statement = statement.where(MaterialRequisition.client_id == client_id)
    if q:
        needle = f"%{q.strip()}%"
        statement = statement.where(
            or_(
                MaterialRequisition.requisition_number.ilike(needle),
                MaterialRequisition.title.ilike(needle),
                MaterialRequisition.notes.ilike(needle),
            )
        )
    statement = (
        statement.order_by(MaterialRequisition.created_at.desc(), MaterialRequisition.id.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(db.scalars(statement).unique().all())


@router.post("", response_model=MaterialRequisitionRead, status_code=status.HTTP_201_CREATED)
def create_material_requisition(
    payload: MaterialRequisitionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("material_requisitions", "create")),
) -> MaterialRequisition:
    project = _project_for_user(db, payload.project_id, current_user)
    house_model = get_or_404(db, HouseModel, payload.house_model_id)
    ensure_same_company(current_user, house_model, db=db)
    if house_model.client_id != project.client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El modelo de casa no pertenece a la inmobiliaria del desarrollo",
        )
    assignment = _project_model_assignment(db, project.id, house_model.id)

    requisition = MaterialRequisition(
        company_id=project.company_id,
        client_id=project.client_id,
        project_id=project.id,
        house_model_id=house_model.id,
        requested_by_user_id=current_user.id,
        requisition_number=_next_number(db, MaterialRequisition, "requisition_number", "RO", project.company_id),
        title=payload.title,
        status="submitted",
        priority=payload.priority,
        required_date=payload.required_date,
        submitted_at=_now(),
        notes=payload.notes,
    )
    db.add(requisition)
    db.flush()

    if len({item.house_model_material_requirement_id for item in payload.items}) != len(payload.items):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes agregar dos veces el mismo material al requerimiento",
        )
    requested_by_requirement = _requested_base_by_requirement(
        db,
        [item.house_model_material_requirement_id for item in payload.items],
        project_id=project.id,
    )
    for item in payload.items:
        requirement = _requirement_for_requisition(
            db,
            requirement_id=item.house_model_material_requirement_id,
            project=project,
            house_model_id=house_model.id,
            current_user=current_user,
        )
        requested_unit = _normalize_unit(item.requested_unit) or _normalize_unit(requirement.unit)
        conversion_factor, requested_base_quantity = _quantity_snapshot(
            db,
            requirement=requirement,
            requested_unit=requested_unit,
            requested_quantity=item.requested_quantity,
        )
        total_required = requirement.quantity_per_house * assignment.quantity
        available = max(
            total_required - requested_by_requirement.get(requirement.id, Decimal("0")),
            Decimal("0"),
        )
        if requested_base_quantity > available:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"{requirement.description} supera lo disponible por solicitar. "
                    f"Disponible: {available} {requirement.unit}"
                ),
            )
        db.add(
            MaterialRequisitionItem(
                requisition_id=requisition.id,
                house_model_material_requirement_id=requirement.id,
                material_id=requirement.material_id,
                source_code=requirement.source_code,
                description=requirement.description,
                unit=requirement.unit,
                requested_unit=requested_unit,
                requested_quantity=item.requested_quantity,
                requested_base_quantity=requested_base_quantity,
                unit_conversion_factor=conversion_factor,
                coverage_houses=item.coverage_houses,
                status="pending",
                notes=item.notes,
            )
        )

    record_event(
        db,
        current_user,
        module="obra",
        action="create",
        entity_type="MaterialRequisition",
        entity_id=requisition.id,
        company_id=requisition.company_id,
        label=requisition.requisition_number,
        description=f"{current_user.full_name} creo el requerimiento de obra {requisition.requisition_number}",
        metadata={"partidas": len(payload.items), "project_id": project.id},
    )
    notify_permission(
        db,
        company_id=requisition.company_id,
        module="material_requisitions",
        action="review",
        notification_type="material_requisition_submitted",
        title="Requerimiento de obra pendiente",
        body=f"{current_user.full_name} envio {requisition.requisition_number} para revision de Compras.",
        category="task",
        priority="high" if payload.priority in {"high", "urgent"} else "normal",
        source_module="obra",
        entity_type="MaterialRequisition",
        entity_id=requisition.id,
        entity_label=requisition.requisition_number,
        action_url="/purchasing",
        project_id=project.id,
        enforce_client_access=False,
    )
    db.commit()
    return _get_requisition_for_user(db, requisition.id, current_user)


def _tracking_status(
    *,
    complete: bool = False,
    active: bool = False,
    blocked: bool = False,
    warning: bool = False,
) -> TrackingStepStatus:
    if blocked:
        return "blocked"
    if warning:
        return "warning"
    if complete:
        return "complete"
    if active:
        return "active"
    return "pending"


def _tracking_step(
    key: str,
    label: str,
    step_status: TrackingStepStatus,
    *,
    detail: str | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    entity_label: str | None = None,
    timestamp: datetime | None = None,
) -> MaterialRequisitionTrackingStep:
    return MaterialRequisitionTrackingStep(
        key=key,
        label=label,
        status=step_status,
        detail=detail,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_label=entity_label,
        timestamp=timestamp,
    )


@router.get("/{requisition_id}/tracking", response_model=MaterialRequisitionTrackingRead)
def get_material_requisition_tracking(
    requisition_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("material_requisitions", "view")),
) -> MaterialRequisitionTrackingRead:
    requisition = _get_requisition_for_user(db, requisition_id, current_user)
    rfq: SupplierRFQ | None = None
    if requisition.converted_rfq_id is not None:
        rfq = db.scalar(
            select(SupplierRFQ)
            .where(SupplierRFQ.id == requisition.converted_rfq_id)
            .options(
                selectinload(SupplierRFQ.items),
                selectinload(SupplierRFQ.supplier_links),
                selectinload(SupplierRFQ.quotes).selectinload(SupplierQuote.supplier),
                selectinload(SupplierRFQ.quotes).selectinload(SupplierQuote.items),
                selectinload(SupplierRFQ.quotes).selectinload(SupplierQuote.approval),
                selectinload(SupplierRFQ.quotes)
                .selectinload(SupplierQuote.purchase_order)
                .selectinload(PurchaseOrder.items),
                selectinload(SupplierRFQ.quotes)
                .selectinload(SupplierQuote.purchase_order)
                .selectinload(PurchaseOrder.invoices)
                .selectinload(SupplierInvoice.items),
                selectinload(SupplierRFQ.quotes)
                .selectinload(SupplierQuote.purchase_order)
                .selectinload(PurchaseOrder.invoices)
                .selectinload(SupplierInvoice.payments),
            )
        )

    quotes = list(rfq.quotes if rfq is not None else [])
    purchase_orders = [quote.purchase_order for quote in quotes if quote.purchase_order is not None]
    invoices = [invoice for order in purchase_orders for invoice in order.invoices]
    payments = [payment for invoice in invoices for payment in invoice.payments]

    quote_count = len(quotes)
    supplier_count = len(rfq.supplier_links) if rfq is not None else 0
    approved_quote_count = sum(1 for quote in quotes if quote.status == "approved")
    purchase_order_count = len(purchase_orders)
    invoice_count = len(invoices)
    payment_count = len(payments)

    rfq_items_by_id = {item.id: item for item in (rfq.items if rfq is not None else [])}
    po_items_by_rfq_item: dict[int, list[PurchaseOrderItem]] = {}
    for order in purchase_orders:
        for item in order.items:
            if item.rfq_item_id is not None:
                po_items_by_rfq_item.setdefault(item.rfq_item_id, []).append(item)

    requested_quantity = sum((item.requested_quantity for item in requisition.items), ZERO)
    rfq_quantity = sum((item.quantity for item in (rfq.items if rfq is not None else [])), ZERO)
    ordered_quantity = sum(
        (item.quantity_ordered for order in purchase_orders for item in order.items),
        ZERO,
    )
    received_quantity = sum(
        (item.received_quantity for order in purchase_orders for item in order.items),
        ZERO,
    )
    invoiced_amount = sum((invoice.total for invoice in invoices), ZERO)
    paid_amount = sum((payment.amount for payment in payments if payment.status == "paid"), ZERO)

    requested_items = []
    for item in requisition.items:
        rfq_item = rfq_items_by_id.get(item.supplier_rfq_item_id or 0)
        related_po_items = po_items_by_rfq_item.get(item.supplier_rfq_item_id or 0, [])
        requested_items.append(
            MaterialRequisitionTrackingItem(
                requisition_item_id=item.id,
                description=item.description,
                source_code=item.source_code,
                unit=item.unit,
                requested_unit=item.requested_unit,
                requested_quantity=item.requested_quantity,
                rfq_quantity=rfq_item.quantity if rfq_item is not None else ZERO,
                ordered_quantity=sum((po_item.quantity_ordered for po_item in related_po_items), ZERO),
                received_quantity=sum((po_item.received_quantity for po_item in related_po_items), ZERO),
            )
        )

    rejected = requisition.status == "rejected"
    cancelled = requisition.status == "cancelled"
    approval_requested = any(quote.approval is not None and quote.approval.status == "requested" for quote in quotes)
    all_orders_received = bool(purchase_orders) and all(
        bool(order.items) and all(item.received_quantity >= item.quantity_ordered for item in order.items)
        for order in purchase_orders
    )
    has_paid_invoice = any(payment.status == "paid" for payment in payments)
    all_payments_closed = bool(invoices) and all(
        invoice.status in {"paid", "closed"} or any(payment.status == "paid" for payment in invoice.payments)
        for invoice in invoices
    )

    steps = [
        _tracking_step(
            "origin",
            "Obra creo requerimiento",
            "complete",
            detail=f"{requisition.requisition_number} enviado a Compras.",
            entity_type="MaterialRequisition",
            entity_id=requisition.id,
            entity_label=requisition.requisition_number,
            timestamp=requisition.submitted_at,
        ),
        _tracking_step(
            "review",
            "Revision de Compras",
            _tracking_status(
                complete=requisition.status
                in {"approved", "converted_to_rfq", "ordered_to_suppliers"},
                active=requisition.status in {"submitted", "in_review"},
                blocked=rejected or cancelled,
            ),
            detail=(
                requisition.review_notes
                if rejected
                else "Compras valida partidas, desarrollo y prioridad antes de cotizar."
            ),
            entity_type="MaterialRequisition",
            entity_id=requisition.id,
            entity_label=requisition.requisition_number,
            timestamp=requisition.reviewed_at,
        ),
        _tracking_step(
            "rfq",
            "Solicitud a proveedores",
            _tracking_status(
                complete=rfq is not None,
                active=requisition.status == "approved",
                blocked=rejected or cancelled,
            ),
            detail=(
                f"{rfq.rfq_number} con {supplier_count} proveedor(es) invitado(s)."
                if rfq is not None
                else "Pendiente de convertir a solicitud de cotizacion."
            ),
            entity_type="SupplierRFQ" if rfq is not None else None,
            entity_id=rfq.id if rfq is not None else None,
            entity_label=rfq.rfq_number if rfq is not None else None,
            timestamp=rfq.sent_at if rfq is not None else None,
        ),
        _tracking_step(
            "quotes",
            "Cotizaciones recibidas",
            _tracking_status(
                complete=bool(rfq is not None and supplier_count > 0 and quote_count >= supplier_count),
                active=quote_count > 0 or (rfq is not None and rfq.status in {"sent", "quoted"}),
                blocked=rejected or cancelled,
            ),
            detail=(
                f"{quote_count} de {supplier_count} cotizacion(es) capturada(s)."
                if rfq is not None
                else "Sin solicitud a proveedores."
            ),
        ),
        _tracking_step(
            "approval",
            "Aprobacion gerencial",
            _tracking_status(
                complete=approved_quote_count > 0 or (rfq is not None and rfq.status == "awarded"),
                active=approval_requested or (rfq is not None and rfq.status == "approval_pending"),
                blocked=rejected or cancelled,
                warning=bool(rfq is not None and rfq.status == "exception_requested"),
            ),
            detail=(
                f"{approved_quote_count} cotizacion(es) aprobada(s)."
                if approved_quote_count
                else "Pendiente de solicitar o resolver aprobacion."
            ),
        ),
        _tracking_step(
            "purchase_order",
            "Orden de compra",
            _tracking_status(
                complete=purchase_order_count > 0,
                active=approved_quote_count > 0,
                blocked=rejected or cancelled,
            ),
            detail=(
                ", ".join(order.po_number for order in purchase_orders)
                if purchase_orders
                else "Compras aun no genera o envia la OC."
            ),
            entity_type="PurchaseOrder" if purchase_order_count == 1 else None,
            entity_id=purchase_orders[0].id if purchase_order_count == 1 else None,
            entity_label=purchase_orders[0].po_number if purchase_order_count == 1 else None,
            timestamp=purchase_orders[0].created_at if purchase_order_count == 1 else None,
        ),
        _tracking_step(
            "inventory",
            "Recepcion de inventario",
            _tracking_status(
                complete=all_orders_received,
                active=received_quantity > 0,
                blocked=rejected or cancelled,
            ),
            detail=(
                f"Recibido {received_quantity} de {ordered_quantity} unidad(es) ordenadas."
                if purchase_orders
                else "Inventario recibe cuando exista OC."
            ),
        ),
        _tracking_step(
            "payments",
            "Facturas y pagos",
            _tracking_status(
                complete=all_payments_closed,
                active=invoice_count > 0 or has_paid_invoice,
                blocked=rejected or cancelled,
            ),
            detail=(
                f"{invoice_count} factura(s), {payment_count} pago(s), pagado ${paid_amount}."
                if invoice_count or payment_count
                else "Pagos se habilita conforme se validan recepciones y facturas."
            ),
        ),
    ]

    return MaterialRequisitionTrackingRead(
        requisition=requisition,
        project_name=requisition.project.name if requisition.project else None,
        house_model_name=requisition.house_model.name if requisition.house_model else None,
        rfq_id=rfq.id if rfq is not None else None,
        rfq_number=rfq.rfq_number if rfq is not None else None,
        rfq_status=rfq.status if rfq is not None else None,
        supplier_count=supplier_count,
        quote_count=quote_count,
        approved_quote_count=approved_quote_count,
        purchase_order_count=purchase_order_count,
        invoice_count=invoice_count,
        payment_count=payment_count,
        requested_quantity=requested_quantity,
        rfq_quantity=rfq_quantity,
        ordered_quantity=ordered_quantity,
        received_quantity=received_quantity,
        invoiced_amount=invoiced_amount,
        paid_amount=paid_amount,
        steps=steps,
        items=requested_items,
    )


@router.get("/{requisition_id}", response_model=MaterialRequisitionRead)
def get_material_requisition(
    requisition_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("material_requisitions", "view")),
) -> MaterialRequisition:
    return _get_requisition_for_user(db, requisition_id, current_user)


@router.patch("/{requisition_id}", response_model=MaterialRequisitionRead)
def update_material_requisition(
    requisition_id: int,
    payload: MaterialRequisitionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("material_requisitions", "create")),
) -> MaterialRequisition:
    requisition = _get_requisition_for_user(db, requisition_id, current_user)
    if requisition.status != "submitted" or requisition.converted_rfq_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo puedes editar requerimientos pendientes que aun no han sido tomados por Compras",
        )
    if not current_user.is_master_admin and requisition.requested_by_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el usuario que genero el requerimiento puede editarlo mientras esta pendiente",
        )

    if payload.title is not None:
        requisition.title = payload.title
    if payload.priority is not None:
        requisition.priority = payload.priority
    if "required_date" in payload.model_fields_set:
        requisition.required_date = payload.required_date
    if "notes" in payload.model_fields_set:
        requisition.notes = payload.notes

    if payload.items is not None:
        project = _project_for_user(db, requisition.project_id, current_user)
        assignment = _project_model_assignment(db, requisition.project_id, requisition.house_model_id)
        items_by_id = {item.id: item for item in requisition.items}
        requested_by_requirement = _requested_base_by_requirement(
            db,
            [
                item.house_model_material_requirement_id
                for item in requisition.items
                if item.house_model_material_requirement_id is not None
            ],
            project_id=requisition.project_id,
            exclude_requisition_id=requisition.id,
        )
        for item_payload in payload.items:
            item = items_by_id.get(item_payload.id)
            if item is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Una partida no pertenece al requerimiento seleccionado",
                )
            if item.house_model_material_requirement_id is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="La partida no conserva relacion con la explosion del modelo",
                )
            requirement = _requirement_for_requisition(
                db,
                requirement_id=item.house_model_material_requirement_id,
                project=project,
                house_model_id=requisition.house_model_id,
                current_user=current_user,
            )
            requested_unit = _normalize_unit(item_payload.requested_unit) or _normalize_unit(item.unit)
            conversion_factor, requested_base_quantity = _quantity_snapshot(
                db,
                requirement=requirement,
                requested_unit=requested_unit,
                requested_quantity=item_payload.requested_quantity,
            )
            total_required = requirement.quantity_per_house * assignment.quantity
            available = max(
                total_required - requested_by_requirement.get(requirement.id, Decimal("0")),
                Decimal("0"),
            )
            if requested_base_quantity > available:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"{requirement.description} supera lo disponible por solicitar. "
                        f"Disponible: {available} {requirement.unit}"
                    ),
                )
            item.requested_quantity = item_payload.requested_quantity
            item.requested_unit = requested_unit
            item.requested_base_quantity = requested_base_quantity
            item.unit_conversion_factor = conversion_factor
            item.coverage_houses = item_payload.coverage_houses
            item.notes = item_payload.notes

    record_event(
        db,
        current_user,
        module="obra",
        action="update",
        entity_type="MaterialRequisition",
        entity_id=requisition.id,
        company_id=requisition.company_id,
        label=requisition.requisition_number,
        description=f"{current_user.full_name} actualizo el requerimiento {requisition.requisition_number}",
        metadata={"partidas": len(requisition.items), "project_id": requisition.project_id},
    )
    db.commit()
    return _get_requisition_for_user(db, requisition.id, current_user)


@router.post("/{requisition_id}/start-review", response_model=MaterialRequisitionRead)
def start_material_requisition_review(
    requisition_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("material_requisitions", "review")),
) -> MaterialRequisition:
    requisition = _get_requisition_for_user(db, requisition_id, current_user)
    if requisition.status == "in_review":
        return requisition
    if requisition.status != "submitted" or requisition.converted_rfq_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo puedes tomar requerimientos pendientes de revision",
        )
    requisition.status = "in_review"
    requisition.reviewed_by_user_id = current_user.id
    requisition.reviewed_at = _now()
    resolve_notifications(
        db,
        company_id=requisition.company_id,
        notification_type="material_requisition_submitted",
        entity_type="MaterialRequisition",
        entity_id=requisition.id,
    )
    notify_user_id(
        db,
        user_id=requisition.requested_by_user_id,
        company_id=requisition.company_id,
        notification_type="material_requisition_in_review",
        title="Compras inicio la revision",
        body=f"{current_user.full_name} tomo {requisition.requisition_number} para revision.",
        category="info",
        priority="normal",
        source_module="compras",
        entity_type="MaterialRequisition",
        entity_id=requisition.id,
        entity_label=requisition.requisition_number,
        action_url=(
            f"/work?project_id={requisition.project_id}"
            f"&house_model_id={requisition.house_model_id}"
            f"&requisition_id={requisition.id}"
        ),
        project_id=requisition.project_id,
    )
    record_event(
        db,
        current_user,
        module="compras",
        action="start_review",
        entity_type="MaterialRequisition",
        entity_id=requisition.id,
        company_id=requisition.company_id,
        label=requisition.requisition_number,
        description=f"{current_user.full_name} tomo {requisition.requisition_number} para revision",
    )
    db.commit()
    return _get_requisition_for_user(db, requisition.id, current_user)


@router.post("/{requisition_id}/review", response_model=MaterialRequisitionRead)
def review_material_requisition(
    requisition_id: int,
    payload: MaterialRequisitionReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("material_requisitions", "review")),
) -> MaterialRequisition:
    requisition = _get_requisition_for_user(db, requisition_id, current_user)
    if requisition.status not in {"submitted", "in_review", "approved", "rejected"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El requerimiento ya no puede revisarse en su estado actual",
        )

    requisition.status = payload.decision
    requisition.review_notes = payload.review_notes
    requisition.reviewed_by_user_id = current_user.id
    requisition.reviewed_at = _now()
    for item in requisition.items:
        item.status = "approved" if payload.decision == "approved" else "rejected"
        if payload.decision == "approved" and item.approved_quantity is None:
            item.approved_quantity = item.requested_quantity

    resolve_notifications(
        db,
        company_id=requisition.company_id,
        notification_type="material_requisition_submitted",
        entity_type="MaterialRequisition",
        entity_id=requisition.id,
    )
    notify_user_id(
        db,
        user_id=requisition.requested_by_user_id,
        company_id=requisition.company_id,
        notification_type=f"material_requisition_{payload.decision}",
        title="Requerimiento de obra aprobado" if payload.decision == "approved" else "Requerimiento de obra rechazado",
        body=(
            f"Compras aprobo {requisition.requisition_number}."
            if payload.decision == "approved"
            else f"Compras rechazo {requisition.requisition_number}."
        ),
        category="info" if payload.decision == "approved" else "warning",
        priority="normal",
        source_module="compras",
        entity_type="MaterialRequisition",
        entity_id=requisition.id,
        entity_label=requisition.requisition_number,
        action_url=(
            f"/work?project_id={requisition.project_id}"
            f"&house_model_id={requisition.house_model_id}"
            f"&requisition_id={requisition.id}"
        ),
        project_id=requisition.project_id,
        metadata={"review_notes": payload.review_notes},
    )
    record_event(
        db,
        current_user,
        module="compras",
        action=payload.decision,
        entity_type="MaterialRequisition",
        entity_id=requisition.id,
        company_id=requisition.company_id,
        label=requisition.requisition_number,
        description=f"{current_user.full_name} marco {requisition.requisition_number} como {payload.decision}",
    )
    db.commit()
    return _get_requisition_for_user(db, requisition.id, current_user)


@router.post("/{requisition_id}/convert-to-rfq", response_model=MaterialRequisitionConvertResult)
def convert_material_requisition_to_rfq(
    requisition_id: int,
    payload: MaterialRequisitionConvertToRFQ,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("material_requisitions", "convert_to_rfq")),
) -> MaterialRequisitionConvertResult:
    requisition = _get_requisition_for_user(db, requisition_id, current_user)
    if requisition.status not in {"submitted", "in_review", "approved"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo puedes convertir requerimientos pendientes o aprobados por Compras",
        )
    _ensure_unique_supplier_ids(payload.supplier_ids)
    project = _project_for_user(db, requisition.project_id, current_user, company_scope=True)
    warehouse = _warehouse_for_project(db, None, project)
    suppliers = [_supplier_for_user(db, supplier_id, current_user) for supplier_id in payload.supplier_ids]
    if len(suppliers) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Para compras sin convenio o excepcion se requieren al menos 3 proveedores",
        )
    rfq = SupplierRFQ(
        company_id=requisition.company_id,
        project_id=requisition.project_id,
        warehouse_id=warehouse.id if warehouse else None,
        rfq_number=_next_number(db, SupplierRFQ, "rfq_number", "SC", requisition.company_id),
        title=payload.title or requisition.title,
        request_type="work_requisition",
        required_by=payload.required_by or requisition.required_date,
        response_deadline=payload.response_deadline,
        notes=payload.notes or f"Generada desde requerimiento de obra {requisition.requisition_number}.",
        created_by=current_user.id,
    )
    db.add(rfq)
    db.flush()

    for item in requisition.items:
        quantity = item.approved_quantity or item.requested_quantity
        requested_unit = item.requested_unit or item.unit
        item_notes = item.notes
        if requested_unit != item.unit:
            base_unit_note = f"Unidad base de explosion: {item.unit}"
            item_notes = f"{item_notes}. {base_unit_note}" if item_notes else base_unit_note
        rfq_item = SupplierRFQItem(
            rfq_id=rfq.id,
            house_model_id=requisition.house_model_id,
            house_model_material_requirement_id=item.house_model_material_requirement_id,
            material_id=item.material_id,
            source_code=item.source_code,
            description=item.description,
            unit=requested_unit,
            quantity=quantity,
            notes=item_notes,
        )
        db.add(rfq_item)
        db.flush()
        if item.approved_quantity is None:
            item.approved_quantity = item.requested_quantity
        item.supplier_rfq_item_id = rfq_item.id
        item.status = "converted"

    for supplier in suppliers:
        db.add(SupplierRFQSupplier(rfq_id=rfq.id, supplier_id=supplier.id))

    requisition.status = "converted_to_rfq"
    if requisition.reviewed_by_user_id is None:
        requisition.reviewed_by_user_id = current_user.id
        requisition.reviewed_at = _now()
    requisition.converted_rfq_id = rfq.id
    db.flush()
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
    notify_user_id(
        db,
        user_id=requisition.requested_by_user_id,
        company_id=requisition.company_id,
        notification_type="material_requisition_converted_to_rfq",
        title="Requerimiento enviado a cotizar",
        body=f"Compras convirtio {requisition.requisition_number} en {rfq.rfq_number}.",
        category="info",
        priority="normal",
        source_module="compras",
        entity_type="SupplierRFQ",
        entity_id=rfq.id,
        entity_label=rfq.rfq_number,
        action_url="/purchasing",
        project_id=requisition.project_id,
    )
    record_event(
        db,
        current_user,
        module="compras",
        action="convert_to_rfq",
        entity_type="MaterialRequisition",
        entity_id=requisition.id,
        company_id=requisition.company_id,
        label=requisition.requisition_number,
        description=f"{current_user.full_name} convirtio {requisition.requisition_number} en {rfq.rfq_number}",
        metadata={"rfq_id": rfq.id, "encolados": queued_count, "errores": error_count},
    )
    db.commit()
    if queued_count:
        background_tasks.add_task(process_email_outbox_for_company, rfq.company_id)
    return MaterialRequisitionConvertResult(
        requisition=_get_requisition_for_user(db, requisition.id, current_user),
        rfq=rfq,
    )
