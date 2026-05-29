from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models import Material
from app.models import User
from app.schemas.business import MaterialCreate, MaterialRead, MaterialUpdate
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
