from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_permission
from app.core.security import get_password_hash
from app.db.session import get_db
from app.models import Role, User
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.services.crud import delete_item, get_or_404
from app.services.permissions import ensure_roles_assignable, set_user_roles
from app.services.tenancy import (
    company_id_for_write,
    ensure_company_license_allows_user,
    ensure_same_company,
    scoped_select,
)


router = APIRouter()


def _ensure_master_admin_change_allowed(current_user: User, is_master_admin: bool | None) -> None:
    if is_master_admin and not current_user.is_master_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo un administrador maestro puede crear administradores maestros",
        )


@router.get("", response_model=list[UserRead])
def list_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users", "view")),
) -> list[User]:
    statement = scoped_select(select(User), User, current_user)
    return list(
        db.scalars(
            statement
            .options(selectinload(User.roles).selectinload(Role.permissions))
            .offset(skip)
            .limit(limit)
        ).all()
    )


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users", "create")),
) -> User:
    data = payload.model_dump(exclude={"password", "role_ids"})
    _ensure_master_admin_change_allowed(current_user, data.get("is_master_admin"))
    data["company_id"] = company_id_for_write(current_user, data.get("company_id"))
    ensure_company_license_allows_user(db, data["company_id"])
    ensure_roles_assignable(
        db=db,
        role_ids=payload.role_ids,
        current_user=current_user,
        target_company_id=data["company_id"],
        allow_system_roles=bool(data.get("is_master_admin")),
    )
    user = User(**data, password_hash=get_password_hash(payload.password))
    db.add(user)
    db.flush()
    set_user_roles(db, user.id, payload.role_ids)
    db.commit()
    return get_or_404(db, User, user.id)


@router.get("/{user_id}", response_model=UserRead)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users", "view")),
) -> User:
    user = get_or_404(db, User, user_id)
    ensure_same_company(current_user, user)
    return user


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users", "edit")),
) -> User:
    user = get_or_404(db, User, user_id)
    ensure_same_company(current_user, user)
    if user.is_master_admin and not current_user.is_master_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo un administrador maestro puede modificar ese usuario",
        )
    data = payload.model_dump(exclude_unset=True, exclude={"password", "role_ids"})
    if "is_master_admin" in data and data["is_master_admin"] != user.is_master_admin:
        if not current_user.is_master_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo un administrador maestro puede cambiar ese privilegio",
            )
    if "company_id" in data:
        data["company_id"] = company_id_for_write(current_user, data.get("company_id"))
        if user.company_id != data["company_id"] or payload.is_active is True:
            ensure_company_license_allows_user(db, data["company_id"])
    elif payload.is_active is True and user.company_id is not None:
        ensure_company_license_allows_user(db, user.company_id)
    target_company_id = data.get("company_id", user.company_id)
    target_is_master_admin = data.get("is_master_admin", user.is_master_admin)
    if payload.role_ids is not None:
        ensure_roles_assignable(
            db=db,
            role_ids=payload.role_ids,
            current_user=current_user,
            target_company_id=target_company_id,
            allow_system_roles=bool(target_is_master_admin),
        )
    for field, value in data.items():
        setattr(user, field, value)
    if payload.password:
        user.password_hash = get_password_hash(payload.password)
    if payload.role_ids is not None:
        set_user_roles(db, user.id, payload.role_ids)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users", "delete")),
) -> None:
    user = get_or_404(db, User, user_id)
    ensure_same_company(current_user, user)
    if user.is_master_admin and not current_user.is_master_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo un administrador maestro puede eliminar ese usuario",
        )
    delete_item(db, user)
