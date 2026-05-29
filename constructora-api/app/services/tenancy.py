from typing import Any, TypeVar

from fastapi import HTTPException, status
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models import Company, User


ModelT = TypeVar("ModelT")


def get_user_company_id(user: User) -> int:
    if user.company_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El usuario no tiene empresa asignada",
        )
    return user.company_id


def company_id_for_write(user: User, requested_company_id: int | None = None) -> int:
    if user.is_master_admin and requested_company_id is not None:
        return requested_company_id
    return get_user_company_id(user)


def scoped_select(statement: Select, model: type[ModelT], user: User) -> Select:
    if user.is_master_admin:
        return statement
    return statement.where(getattr(model, "company_id") == get_user_company_id(user))


def ensure_same_company(user: User, item: Any) -> None:
    if user.is_master_admin:
        return
    item_company_id = getattr(item, "company_id", None)
    if isinstance(item, Company):
        item_company_id = item.id
    if item_company_id != get_user_company_id(user):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registro no encontrado",
        )


def ensure_company_exists(db: Session, company_id: int) -> Company:
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empresa no encontrada",
        )
    return company


def ensure_company_license_allows_user(db: Session, company_id: int) -> None:
    company = ensure_company_exists(db, company_id)
    if company.license_status not in {"trial", "active"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La licencia de la empresa no esta activa",
        )
    active_users = db.scalar(
        select(func.count(User.id)).where(User.company_id == company_id, User.is_active.is_(True))
    )
    if active_users is not None and active_users >= company.max_users:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La empresa alcanzo el limite de usuarios de su licencia",
        )
