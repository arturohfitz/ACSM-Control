from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_permission
from app.db.session import get_db
from app.models import Client, HouseModel, Project, ProjectHouseModel, Quote, User
from app.schemas.business import (
    ProjectCreate,
    ProjectHouseModelCreate,
    ProjectHouseModelRead,
    ProjectRead,
    ProjectSummary,
    ProjectUpdate,
)
from app.services.crud import create_item, delete_item, get_or_404, update_item
from app.services.delete_guards import ensure_project_has_no_approved_quote
from app.services.tenancy import company_id_for_write, ensure_same_company, get_user_company_id, scoped_select


router = APIRouter()


def _ensure_client_exists(db: Session, client_id: int, current_user: User) -> Client:
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se permite crear proyecto sin cliente valido",
        )
    ensure_same_company(current_user, client)
    return client


@router.get("", response_model=list[ProjectRead])
def list_projects(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("projects", "view")),
) -> list[Project]:
    statement = scoped_select(select(Project), Project, current_user).offset(skip).limit(limit)
    return list(db.scalars(statement).all())


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("projects", "create")),
) -> Project:
    client = _ensure_client_exists(db, payload.client_id, current_user)
    data = payload.model_dump()
    data["company_id"] = (
        company_id_for_write(current_user, data.get("company_id") or client.company_id)
        if current_user.is_master_admin
        else client.company_id
    )
    return create_item(db, Project, data)


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("projects", "view")),
) -> Project:
    project = get_or_404(db, Project, project_id)
    ensure_same_company(current_user, project)
    return project


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("projects", "edit")),
) -> Project:
    item = get_or_404(db, Project, project_id)
    ensure_same_company(current_user, item)
    if payload.client_id is not None:
        client = _ensure_client_exists(db, payload.client_id, current_user)
        mismatched_model = db.scalar(
            select(HouseModel)
            .join(ProjectHouseModel, ProjectHouseModel.house_model_id == HouseModel.id)
            .where(
                ProjectHouseModel.project_id == project_id,
                or_(HouseModel.client_id.is_(None), HouseModel.client_id != client.id),
            )
            .limit(1)
        )
        if mismatched_model is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "No se puede cambiar la desarrolladora porque el proyecto "
                    "tiene modelos asignados de otra desarrolladora"
                ),
            )
        item.company_id = client.company_id
    data = payload.model_dump(exclude_unset=True, exclude={"company_id"})
    return update_item(db, item, data)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("projects", "delete")),
) -> None:
    item = get_or_404(db, Project, project_id)
    ensure_same_company(current_user, item)
    ensure_project_has_no_approved_quote(db, project_id)
    delete_item(db, item)


@router.post(
    "/{project_id}/house-models",
    response_model=ProjectHouseModelRead,
    status_code=status.HTTP_201_CREATED,
)
def assign_house_model(
    project_id: int,
    payload: ProjectHouseModelCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("projects", "edit")),
) -> ProjectHouseModel:
    project = get_or_404(db, Project, project_id)
    ensure_same_company(current_user, project)
    house_model = get_or_404(db, HouseModel, payload.house_model_id)
    ensure_same_company(current_user, house_model)
    if house_model.client_id != project.client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El modelo de casa no pertenece a la desarrolladora del proyecto",
        )
    total_estimated_cost = (
        payload.estimated_cost_per_unit * payload.quantity
        if payload.estimated_cost_per_unit is not None
        else None
    )
    total_estimated_price = (
        payload.estimated_price_per_unit * payload.quantity
        if payload.estimated_price_per_unit is not None
        else None
    )
    assignment = ProjectHouseModel(
        project_id=project_id,
        **payload.model_dump(),
        total_estimated_cost=total_estimated_cost,
        total_estimated_price=total_estimated_price,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


@router.get("/{project_id}/summary", response_model=ProjectSummary)
def project_summary(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("projects", "view")),
) -> dict:
    project = get_or_404(db, Project, project_id)
    ensure_same_company(current_user, project)
    assigned_models = list(
        db.scalars(
            select(ProjectHouseModel)
            .where(ProjectHouseModel.project_id == project_id)
            .options(selectinload(ProjectHouseModel.house_model))
        ).all()
    )
    approved_statement = select(Quote.id).where(Quote.project_id == project_id, Quote.status == "approved")
    if not current_user.is_master_admin:
        approved_statement = approved_statement.where(Quote.company_id == get_user_company_id(current_user))
    approved_quote_id = db.scalar(approved_statement)
    quote_count = db.scalar(select(func.count(Quote.id)).where(Quote.project_id == project_id)) or 0
    total_estimated_cost = sum(
        item.total_estimated_cost or Decimal("0") for item in assigned_models
    )
    total_estimated_price = sum(
        item.total_estimated_price or Decimal("0") for item in assigned_models
    )
    return {
        "project": project,
        "assigned_models": assigned_models,
        "quote_count": quote_count,
        "approved_quote_id": approved_quote_id,
        "total_estimated_cost": total_estimated_cost,
        "total_estimated_price": total_estimated_price,
    }
