from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_permission
from app.db.session import get_db
from app.models import (
    Client,
    ConceptLabor,
    ConceptMaterial,
    ConstructionConcept,
    HouseModelBudgetActivity,
    HouseModelDocument,
    LaborRate,
    Material,
    Project,
    ProjectHouseModel,
    User,
)
from app.schemas.business import (
    ConstructionConceptModelCatalogRead,
    ConstructionConceptModelCatalogCreate,
    ConstructionConceptCreate,
    ConstructionConceptRead,
    ConstructionConceptUpdate,
)
from app.services.crud import delete_item, get_or_404
from app.services.audit import record_event
from app.services.delete_guards import ensure_concept_has_no_approved_quote
from app.services.tenancy import company_id_for_write, ensure_same_company, scoped_select


router = APIRouter()


def _concept_options():
    return (
        selectinload(ConstructionConcept.concept_materials),
        selectinload(ConstructionConcept.concept_labor),
    )


def _manual_budget_document(
    db: Session,
    *,
    company_id: int,
    client_id: int,
    house_model_id: int,
) -> HouseModelDocument:
    file_hash = f"manual-budget:{company_id}:{client_id}:{house_model_id}"
    document = db.scalar(
        select(HouseModelDocument).where(
            HouseModelDocument.company_id == company_id,
            HouseModelDocument.house_model_id == house_model_id,
            HouseModelDocument.document_type == "budget",
            HouseModelDocument.file_hash == file_hash,
        )
    )
    if document is not None:
        return document
    document = HouseModelDocument(
        company_id=company_id,
        client_id=client_id,
        house_model_id=house_model_id,
        document_type="budget",
        version="manual",
        source_code="manual",
        source_date=date.today(),
        file_name="Alta manual de conceptos",
        file_hash=file_hash,
        status="manual",
        total_items=0,
        total_amount=Decimal("0"),
        notes="Conceptos agregados manualmente al presupuesto del modelo.",
    )
    db.add(document)
    db.flush()
    return document


@router.get("", response_model=list[ConstructionConceptRead])
def list_concepts(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("construction_concepts", "view")),
) -> list[ConstructionConcept]:
    statement = scoped_select(select(ConstructionConcept), ConstructionConcept, current_user)
    return list(
        db.scalars(
            statement.options(*_concept_options()).offset(skip).limit(limit)
        ).all()
    )


@router.get("/model-catalog", response_model=list[ConstructionConceptModelCatalogRead])
def list_model_concept_catalog(
    project_id: int,
    house_model_id: int,
    q: str | None = None,
    limit: int = Query(default=500, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("construction_concepts", "view")),
) -> list[ConstructionConceptModelCatalogRead]:
    project = get_or_404(db, Project, project_id)
    ensure_same_company(current_user, project, db=db)
    client = get_or_404(db, Client, project.client_id)
    assignment = db.scalar(
        select(ProjectHouseModel)
        .where(
            ProjectHouseModel.project_id == project_id,
            ProjectHouseModel.house_model_id == house_model_id,
        )
        .options(selectinload(ProjectHouseModel.house_model))
    )
    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El modelo no esta asignado al desarrollo seleccionado",
        )

    statement = (
        select(HouseModelBudgetActivity)
        .where(
            HouseModelBudgetActivity.client_id == project.client_id,
            HouseModelBudgetActivity.house_model_id == house_model_id,
            HouseModelBudgetActivity.validation_status != "ignored",
        )
        .options(selectinload(HouseModelBudgetActivity.construction_concept))
        .order_by(
            HouseModelBudgetActivity.sort_order,
            HouseModelBudgetActivity.id,
        )
        .limit(limit)
    )
    if q:
        needle = f"%{q.strip()}%"
        statement = statement.where(
            or_(
                HouseModelBudgetActivity.description.ilike(needle),
                HouseModelBudgetActivity.source_code.ilike(needle),
                HouseModelBudgetActivity.chapter_name.ilike(needle),
            )
        )

    activities = list(db.scalars(statement).all())
    return [
        ConstructionConceptModelCatalogRead(
            id=activity.id,
            project_id=project.id,
            project_name=project.name,
            client_id=client.id,
            client_name=client.name,
            house_model_id=assignment.house_model_id,
            house_model_name=assignment.house_model.name,
            construction_concept_id=activity.construction_concept_id,
            concept_code=(
                activity.construction_concept.code
                if activity.construction_concept is not None
                else activity.source_code
            ),
            concept_name=(
                activity.construction_concept.name
                if activity.construction_concept is not None
                else activity.description
            ),
            chapter_code=activity.chapter_code,
            chapter_name=activity.chapter_name,
            source_code=activity.source_code,
            unit=(
                activity.construction_concept.unit
                if activity.construction_concept is not None
                else activity.unit
            ),
            quantity_per_house=activity.quantity_per_house,
            assigned_houses=assignment.quantity,
            total_required=activity.quantity_per_house * assignment.quantity,
            unit_price_reference=activity.unit_price_reference,
            total_price_reference=activity.total_price_reference,
            validation_status=activity.validation_status,
            is_linked=activity.construction_concept_id is not None,
        )
        for activity in activities
    ]


@router.post(
    "/model-catalog",
    response_model=ConstructionConceptModelCatalogRead,
    status_code=status.HTTP_201_CREATED,
)
def create_model_concept_catalog(
    payload: ConstructionConceptModelCatalogCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("construction_concepts", "create")),
) -> ConstructionConceptModelCatalogRead:
    project = get_or_404(db, Project, payload.project_id)
    ensure_same_company(current_user, project, db=db)
    client = get_or_404(db, Client, project.client_id)
    ensure_same_company(current_user, client, db=db)
    assignment = db.scalar(
        select(ProjectHouseModel)
        .where(
            ProjectHouseModel.project_id == project.id,
            ProjectHouseModel.house_model_id == payload.house_model_id,
        )
        .options(selectinload(ProjectHouseModel.house_model))
    )
    if assignment is None or assignment.house_model.client_id != project.client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El modelo no pertenece al desarrollo seleccionado",
        )
    code = payload.code.strip().upper()
    existing = db.scalar(
        select(ConstructionConcept).where(
            ConstructionConcept.company_id == project.company_id,
            func.lower(ConstructionConcept.code) == code.lower(),
        )
    )
    if existing is not None:
        if (
            existing.name.strip().casefold() != payload.name.strip().casefold()
            or existing.unit.strip().upper() != payload.unit.strip().upper()
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El codigo ya pertenece a otro concepto o unidad en la constructora",
            )
        duplicate_activity = db.scalar(
            select(HouseModelBudgetActivity.id).where(
                HouseModelBudgetActivity.client_id == project.client_id,
                HouseModelBudgetActivity.house_model_id == assignment.house_model_id,
                HouseModelBudgetActivity.construction_concept_id == existing.id,
                HouseModelBudgetActivity.validation_status != "ignored",
            )
        )
        if duplicate_activity is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El concepto ya esta registrado en el modelo seleccionado",
            )
        concept = existing
    else:
        concept = ConstructionConcept(
            company_id=project.company_id,
            code=code,
            name=payload.name.strip(),
            unit=payload.unit.strip().upper(),
            description=payload.description,
            default_waste_percent=payload.default_waste_percent,
            default_indirect_percent=payload.default_indirect_percent,
        )
        db.add(concept)
        db.flush()
    document = _manual_budget_document(
        db,
        company_id=project.company_id,
        client_id=project.client_id,
        house_model_id=assignment.house_model_id,
    )
    next_sort_order = db.scalar(
        select(func.coalesce(func.max(HouseModelBudgetActivity.sort_order), 0) + 1).where(
            HouseModelBudgetActivity.house_model_id == assignment.house_model_id,
            HouseModelBudgetActivity.client_id == project.client_id,
        )
    ) or 1
    total_price = payload.unit_price_reference * payload.quantity_per_house
    activity = HouseModelBudgetActivity(
        company_id=project.company_id,
        client_id=project.client_id,
        house_model_id=assignment.house_model_id,
        document_id=document.id,
        construction_concept_id=concept.id,
        chapter_code=payload.chapter_code,
        chapter_name=payload.chapter_name,
        source_code=code,
        description=concept.name,
        unit=concept.unit,
        quantity_per_house=payload.quantity_per_house,
        unit_price_reference=payload.unit_price_reference,
        total_price_reference=total_price,
        validation_status="validated",
        sort_order=next_sort_order,
        notes=payload.description,
    )
    db.add(activity)
    db.flush()
    document.total_items = db.scalar(
        select(func.count(HouseModelBudgetActivity.id)).where(
            HouseModelBudgetActivity.document_id == document.id,
            HouseModelBudgetActivity.validation_status != "ignored",
        )
    ) or 0
    document.total_amount = db.scalar(
        select(func.coalesce(func.sum(HouseModelBudgetActivity.total_price_reference), 0)).where(
            HouseModelBudgetActivity.document_id == document.id,
            HouseModelBudgetActivity.validation_status != "ignored",
        )
    )
    record_event(
        db,
        current_user,
        module="obra",
        action="create",
        entity_type="HouseModelBudgetActivity",
        entity_id=activity.id,
        company_id=project.company_id,
        label=concept.name,
        description=(
            f"{current_user.full_name} agrego el concepto {concept.code} al modelo "
            f"{assignment.house_model.name}"
        ),
        metadata={
            "project_id": project.id,
            "house_model_id": assignment.house_model_id,
            "construction_concept_id": concept.id,
        },
    )
    db.commit()
    return ConstructionConceptModelCatalogRead(
        id=activity.id,
        project_id=project.id,
        project_name=project.name,
        client_id=client.id,
        client_name=client.name,
        house_model_id=assignment.house_model_id,
        house_model_name=assignment.house_model.name,
        construction_concept_id=concept.id,
        concept_code=concept.code,
        concept_name=concept.name,
        chapter_code=activity.chapter_code,
        chapter_name=activity.chapter_name,
        source_code=activity.source_code,
        unit=concept.unit,
        quantity_per_house=activity.quantity_per_house,
        assigned_houses=assignment.quantity,
        total_required=activity.quantity_per_house * assignment.quantity,
        unit_price_reference=activity.unit_price_reference,
        total_price_reference=activity.total_price_reference,
        validation_status=activity.validation_status,
        is_linked=True,
    )


@router.post("", response_model=ConstructionConceptRead, status_code=status.HTTP_201_CREATED)
def create_concept(
    payload: ConstructionConceptCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("construction_concepts", "create")),
) -> ConstructionConcept:
    data = payload.model_dump(exclude={"materials", "labor"})
    data["company_id"] = company_id_for_write(current_user, data.get("company_id"))
    concept = ConstructionConcept(**data)
    db.add(concept)
    db.flush()
    for material in payload.materials:
        material_item = get_or_404(db, Material, material.material_id)
        ensure_same_company(current_user, material_item)
        db.add(ConceptMaterial(construction_concept_id=concept.id, **material.model_dump()))
    for labor in payload.labor:
        labor_item = get_or_404(db, LaborRate, labor.labor_rate_id)
        ensure_same_company(current_user, labor_item)
        db.add(ConceptLabor(construction_concept_id=concept.id, **labor.model_dump()))
    db.commit()
    db.refresh(concept)
    return concept


@router.get("/{concept_id}", response_model=ConstructionConceptRead)
def get_concept(
    concept_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("construction_concepts", "view")),
) -> ConstructionConcept:
    concept = get_or_404(db, ConstructionConcept, concept_id)
    ensure_same_company(current_user, concept)
    return concept


@router.patch("/{concept_id}", response_model=ConstructionConceptRead)
def update_concept(
    concept_id: int,
    payload: ConstructionConceptUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("construction_concepts", "edit")),
) -> ConstructionConcept:
    concept = get_or_404(db, ConstructionConcept, concept_id)
    ensure_same_company(current_user, concept)
    data = payload.model_dump(exclude_unset=True, exclude={"materials", "labor"})
    if "company_id" in data:
        data["company_id"] = company_id_for_write(current_user, data.get("company_id"))
    for field, value in data.items():
        setattr(concept, field, value)
    if payload.materials is not None:
        for current in list(concept.concept_materials):
            db.delete(current)
        for material in payload.materials:
            material_item = get_or_404(db, Material, material.material_id)
            ensure_same_company(current_user, material_item)
            db.add(ConceptMaterial(construction_concept_id=concept.id, **material.model_dump()))
    if payload.labor is not None:
        for current in list(concept.concept_labor):
            db.delete(current)
        for labor in payload.labor:
            labor_item = get_or_404(db, LaborRate, labor.labor_rate_id)
            ensure_same_company(current_user, labor_item)
            db.add(ConceptLabor(construction_concept_id=concept.id, **labor.model_dump()))
    db.commit()
    db.refresh(concept)
    return concept


@router.delete("/{concept_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_concept(
    concept_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("construction_concepts", "delete")),
) -> None:
    concept = get_or_404(db, ConstructionConcept, concept_id)
    ensure_same_company(current_user, concept)
    ensure_concept_has_no_approved_quote(db, concept_id)
    delete_item(db, concept)
