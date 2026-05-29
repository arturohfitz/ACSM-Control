from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_permission
from app.db.session import get_db
from app.models import ConceptLabor, ConceptMaterial, ConstructionConcept, LaborRate, Material, User
from app.schemas.business import (
    ConstructionConceptCreate,
    ConstructionConceptRead,
    ConstructionConceptUpdate,
)
from app.services.crud import delete_item, get_or_404
from app.services.delete_guards import ensure_concept_has_no_approved_quote
from app.services.tenancy import company_id_for_write, ensure_same_company, scoped_select


router = APIRouter()


def _concept_options():
    return (
        selectinload(ConstructionConcept.concept_materials),
        selectinload(ConstructionConcept.concept_labor),
    )


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
