from datetime import datetime, timezone

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
    MaterialRequisition,
    MaterialRequisitionItem,
    Project,
    ProjectHouseModel,
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
)
from app.services.audit import record_event
from app.services.crud import get_or_404
from app.services.email_outbox import process_email_outbox_for_company
from app.services.notifications import notify_permission, notify_user_id, resolve_notifications
from app.services.tenancy import ensure_same_company, scoped_select


router = APIRouter()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _requisition_options():
    return (
        selectinload(MaterialRequisition.requested_by),
        selectinload(MaterialRequisition.reviewed_by),
        selectinload(MaterialRequisition.items),
    )


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
    ensure_same_company(current_user, requisition, db=db)
    return requisition


def _project_for_user(db: Session, project_id: int, current_user: User) -> Project:
    project = get_or_404(db, Project, project_id)
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
    statement = scoped_select(
        select(MaterialRequisition).options(*_requisition_options()),
        MaterialRequisition,
        current_user,
    )
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
    _project_model_assignment(db, project.id, house_model.id)

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

    for item in payload.items:
        requirement = _requirement_for_requisition(
            db,
            requirement_id=item.house_model_material_requirement_id,
            project=project,
            house_model_id=house_model.id,
            current_user=current_user,
        )
        requested_unit = (item.requested_unit or "").strip() or requirement.unit
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
    )
    db.commit()
    return _get_requisition_for_user(db, requisition.id, current_user)


@router.get("/{requisition_id}", response_model=MaterialRequisitionRead)
def get_material_requisition(
    requisition_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("material_requisitions", "view")),
) -> MaterialRequisition:
    return _get_requisition_for_user(db, requisition_id, current_user)


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
        action_url="/field-requisitions",
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
    project = _project_for_user(db, requisition.project_id, current_user)
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
