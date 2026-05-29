from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models import HouseModel, Material, Project, ProjectHouseModel, ProjectMaterialPrice, User
from app.schemas.business import (
    ProjectMaterialPriceCreate,
    ProjectMaterialPriceRead,
    ProjectMaterialPriceUpdate,
)
from app.services.crud import delete_item, get_or_404, update_item
from app.services.tenancy import ensure_same_company, scoped_select


router = APIRouter()


def _project_for_user(db: Session, project_id: int, current_user: User) -> Project:
    project = get_or_404(db, Project, project_id)
    ensure_same_company(current_user, project)
    return project


def _material_for_project(
    db: Session,
    material_id: int,
    project: Project,
    current_user: User,
) -> Material:
    material = get_or_404(db, Material, material_id)
    ensure_same_company(current_user, material)
    if material.company_id != project.company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El material no pertenece a la constructora del desarrollo",
        )
    return material


def _house_model_for_project(
    db: Session,
    house_model_id: int | None,
    project: Project,
    current_user: User,
) -> HouseModel | None:
    if house_model_id is None:
        return None

    house_model = get_or_404(db, HouseModel, house_model_id)
    ensure_same_company(current_user, house_model)
    if house_model.client_id != project.client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El modelo no pertenece a la desarrolladora del desarrollo",
        )
    assignment_id = db.scalar(
        select(ProjectHouseModel.id).where(
            ProjectHouseModel.project_id == project.id,
            ProjectHouseModel.house_model_id == house_model.id,
        )
    )
    if assignment_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El modelo no esta asignado a este desarrollo",
        )
    return house_model


def _ensure_unique_price(
    db: Session,
    project_id: int,
    material_id: int,
    house_model_id: int | None,
    current_id: int | None = None,
) -> None:
    statement = select(ProjectMaterialPrice.id).where(
        ProjectMaterialPrice.project_id == project_id,
        ProjectMaterialPrice.material_id == material_id,
    )
    if house_model_id is None:
        statement = statement.where(ProjectMaterialPrice.house_model_id.is_(None))
    else:
        statement = statement.where(ProjectMaterialPrice.house_model_id == house_model_id)
    if current_id is not None:
        statement = statement.where(ProjectMaterialPrice.id != current_id)
    existing_id = db.scalar(statement)
    if existing_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un precio para ese material en el desarrollo y modelo indicado",
        )


def _validated_data(
    db: Session,
    payload_data: dict,
    current_user: User,
    existing: ProjectMaterialPrice | None = None,
) -> dict:
    project_id = payload_data.get("project_id", existing.project_id if existing else None)
    material_id = payload_data.get("material_id", existing.material_id if existing else None)
    house_model_id = payload_data.get(
        "house_model_id",
        existing.house_model_id if existing else None,
    )
    if project_id is None or material_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Desarrollo y material son requeridos",
        )

    project = _project_for_user(db, project_id, current_user)
    material = _material_for_project(db, material_id, project, current_user)
    _house_model_for_project(db, house_model_id, project, current_user)
    _ensure_unique_price(
        db,
        project_id=project.id,
        material_id=material.id,
        house_model_id=house_model_id,
        current_id=existing.id if existing else None,
    )

    payload_data["company_id"] = project.company_id
    payload_data["project_id"] = project.id
    payload_data["material_id"] = material.id
    payload_data["house_model_id"] = house_model_id
    if not payload_data.get("unit"):
        if existing is None or "material_id" in payload_data:
            payload_data["unit"] = material.unit
        else:
            payload_data.pop("unit", None)
    return payload_data


@router.get("", response_model=list[ProjectMaterialPriceRead])
def list_project_material_prices(
    project_id: int | None = None,
    house_model_id: int | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("materials", "view")),
) -> list[ProjectMaterialPrice]:
    statement = scoped_select(select(ProjectMaterialPrice), ProjectMaterialPrice, current_user)
    if project_id is not None:
        statement = statement.where(ProjectMaterialPrice.project_id == project_id)
    if house_model_id is not None:
        statement = statement.where(ProjectMaterialPrice.house_model_id == house_model_id)
    return list(
        db.scalars(
            statement.order_by(ProjectMaterialPrice.project_id, ProjectMaterialPrice.id)
            .offset(skip)
            .limit(limit)
        ).all()
    )


@router.post("", response_model=ProjectMaterialPriceRead, status_code=status.HTTP_201_CREATED)
def create_project_material_price(
    payload: ProjectMaterialPriceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("materials", "create")),
) -> ProjectMaterialPrice:
    data = _validated_data(db, payload.model_dump(), current_user)
    item = ProjectMaterialPrice(**data)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/{price_id}", response_model=ProjectMaterialPriceRead)
def get_project_material_price(
    price_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("materials", "view")),
) -> ProjectMaterialPrice:
    item = get_or_404(db, ProjectMaterialPrice, price_id)
    ensure_same_company(current_user, item)
    return item


@router.patch("/{price_id}", response_model=ProjectMaterialPriceRead)
def update_project_material_price(
    price_id: int,
    payload: ProjectMaterialPriceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("materials", "edit")),
) -> ProjectMaterialPrice:
    item = get_or_404(db, ProjectMaterialPrice, price_id)
    ensure_same_company(current_user, item)
    data = payload.model_dump(exclude_unset=True, exclude={"company_id"})
    data = _validated_data(db, data, current_user, existing=item)
    return update_item(db, item, data)


@router.delete("/{price_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project_material_price(
    price_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("materials", "delete")),
) -> None:
    item = get_or_404(db, ProjectMaterialPrice, price_id)
    ensure_same_company(current_user, item)
    delete_item(db, item)
