from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models import LaborRate
from app.models import User
from app.schemas.business import LaborRateCreate, LaborRateRead, LaborRateUpdate
from app.services.crud import delete_item, get_or_404, update_item
from app.services.delete_guards import ensure_labor_has_no_approved_quote
from app.services.tenancy import company_id_for_write, ensure_same_company, scoped_select


router = APIRouter()


@router.get("", response_model=list[LaborRateRead])
def list_labor_rates(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("labor", "view")),
) -> list[LaborRate]:
    statement = scoped_select(select(LaborRate), LaborRate, current_user).offset(skip).limit(limit)
    return list(db.scalars(statement).all())


@router.post("", response_model=LaborRateRead, status_code=status.HTTP_201_CREATED)
def create_labor_rate(
    payload: LaborRateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("labor", "create")),
) -> LaborRate:
    data = payload.model_dump()
    data["company_id"] = company_id_for_write(current_user, data.get("company_id"))
    item = LaborRate(**data)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/{labor_rate_id}", response_model=LaborRateRead)
def get_labor_rate(
    labor_rate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("labor", "view")),
) -> LaborRate:
    item = get_or_404(db, LaborRate, labor_rate_id)
    ensure_same_company(current_user, item)
    return item


@router.patch("/{labor_rate_id}", response_model=LaborRateRead)
def update_labor_rate(
    labor_rate_id: int,
    payload: LaborRateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("labor", "edit")),
) -> LaborRate:
    item = get_or_404(db, LaborRate, labor_rate_id)
    ensure_same_company(current_user, item)
    data = payload.model_dump(exclude_unset=True)
    if "company_id" in data:
        data["company_id"] = company_id_for_write(current_user, data.get("company_id"))
    return update_item(db, item, data)


@router.delete("/{labor_rate_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_labor_rate(
    labor_rate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("labor", "delete")),
) -> None:
    item = get_or_404(db, LaborRate, labor_rate_id)
    ensure_same_company(current_user, item)
    ensure_labor_has_no_approved_quote(db, labor_rate_id)
    delete_item(db, item)
