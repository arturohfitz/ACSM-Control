from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_permission
from app.db.session import get_db
from app.models import Client, HouseModelMaterialRequirement, Material, Project, ProjectHouseModel
from app.models import User
from app.schemas.business import (
    MaterialCreate,
    MaterialModelCatalogRead,
    MaterialRead,
    MaterialUpdate,
)
from app.services.audit import record_create, record_delete, record_update, snapshot
from app.services.crud import get_or_404
from app.services.delete_guards import ensure_material_has_no_approved_quote
from app.services.tenancy import company_id_for_write, ensure_same_company, scoped_select


router = APIRouter()


@router.get("", response_model=list[MaterialRead])
def list_materials(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("materials", "view")),
) -> list[Material]:
    statement = scoped_select(select(Material), Material, current_user).offset(skip).limit(limit)
    return list(db.scalars(statement).all())


@router.get("/model-catalog", response_model=list[MaterialModelCatalogRead])
def list_model_material_catalog(
    project_id: int,
    house_model_id: int,
    q: str | None = None,
    limit: int = Query(default=500, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("materials", "view")),
) -> list[MaterialModelCatalogRead]:
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
        select(HouseModelMaterialRequirement)
        .where(
            HouseModelMaterialRequirement.client_id == project.client_id,
            HouseModelMaterialRequirement.house_model_id == house_model_id,
            HouseModelMaterialRequirement.validation_status != "ignored",
        )
        .options(selectinload(HouseModelMaterialRequirement.material))
        .order_by(
            HouseModelMaterialRequirement.sort_order,
            HouseModelMaterialRequirement.id,
        )
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
        MaterialModelCatalogRead(
            id=item.id,
            project_id=project.id,
            project_name=project.name,
            client_id=client.id,
            client_name=client.name,
            house_model_id=assignment.house_model_id,
            house_model_name=assignment.house_model.name,
            material_id=item.material_id,
            material_name=item.material.name if item.material is not None else item.description,
            source_code=item.source_code,
            family=item.family,
            unit=item.material.unit if item.material is not None else item.unit,
            quantity_per_house=item.quantity_per_house,
            assigned_houses=assignment.quantity,
            total_required=item.quantity_per_house * assignment.quantity,
            unit_cost_reference=item.unit_cost_reference,
            total_cost_reference=item.total_cost_reference,
            catalog_unit_price=(
                item.material.current_unit_price if item.material is not None else None
            ),
            supplier_name=item.material.supplier_name if item.material is not None else None,
            validation_status=item.validation_status,
            is_linked=item.material_id is not None,
        )
        for item in requirements
    ]


@router.post("", response_model=MaterialRead, status_code=status.HTTP_201_CREATED)
def create_material(
    payload: MaterialCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("materials", "create")),
) -> Material:
    data = payload.model_dump()
    data["company_id"] = company_id_for_write(current_user, data.get("company_id"))
    item = Material(**data)
    db.add(item)
    db.flush()
    record_create(db, current_user, module="materiales", item=item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/{material_id}", response_model=MaterialRead)
def get_material(
    material_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("materials", "view")),
) -> Material:
    item = get_or_404(db, Material, material_id)
    ensure_same_company(current_user, item)
    return item


@router.patch("/{material_id}", response_model=MaterialRead)
def update_material(
    material_id: int,
    payload: MaterialUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("materials", "edit")),
) -> Material:
    item = get_or_404(db, Material, material_id)
    ensure_same_company(current_user, item)
    data = payload.model_dump(exclude_unset=True)
    if "company_id" in data:
        data["company_id"] = company_id_for_write(current_user, data.get("company_id"))
    before = snapshot(item, list(data.keys()))
    for field, value in data.items():
        setattr(item, field, value)
    record_update(db, current_user, module="materiales", item=item, before=before)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_material(
    material_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("materials", "delete")),
) -> None:
    item = get_or_404(db, Material, material_id)
    ensure_same_company(current_user, item)
    ensure_material_has_no_approved_quote(db, material_id)
    record_delete(db, current_user, module="materiales", item=item)
    db.delete(item)
    db.commit()
