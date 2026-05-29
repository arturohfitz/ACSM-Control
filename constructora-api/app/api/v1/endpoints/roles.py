from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_permission
from app.db.session import get_db
from app.models import Role, User
from app.schemas.user import RoleCreate, RoleRead, RoleUpdate
from app.services.crud import delete_item, get_or_404
from app.services.permissions import set_role_permissions
from app.services.tenancy import get_user_company_id


router = APIRouter()


def _role_company_id_for_write(
    current_user: User,
    requested_company_id: int | None,
    is_system_role: bool,
) -> int | None:
    if is_system_role:
        if not current_user.is_master_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo un administrador maestro puede crear roles de sistema",
            )
        return None
    if current_user.is_master_admin:
        return requested_company_id
    return get_user_company_id(current_user)


def _get_role_for_user(db: Session, role_id: int, current_user: User) -> Role:
    role = get_or_404(db, Role, role_id)
    if current_user.is_master_admin:
        return role
    if role.is_system_role or role.company_id != get_user_company_id(current_user):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registro no encontrado",
        )
    return role


@router.get("", response_model=list[RoleRead])
def list_roles(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("roles", "view")),
) -> list[Role]:
    statement = select(Role).options(selectinload(Role.permissions)).offset(skip).limit(limit)
    if not current_user.is_master_admin:
        statement = statement.where(
            Role.company_id == get_user_company_id(current_user),
            Role.is_system_role.is_(False),
        )
    return list(db.scalars(statement).all())


@router.post("", response_model=RoleRead, status_code=status.HTTP_201_CREATED)
def create_role(
    payload: RoleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("roles", "create")),
) -> Role:
    data = payload.model_dump(exclude={"permission_ids"})
    data["company_id"] = _role_company_id_for_write(
        current_user,
        data.get("company_id"),
        bool(data.get("is_system_role")),
    )
    if not current_user.is_master_admin:
        data["is_system_role"] = False
    role = Role(**data)
    db.add(role)
    db.flush()
    set_role_permissions(db, role.id, payload.permission_ids)
    db.commit()
    db.refresh(role)
    return role


@router.get("/{role_id}", response_model=RoleRead)
def get_role(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("roles", "view")),
) -> Role:
    return _get_role_for_user(db, role_id, current_user)


@router.patch("/{role_id}", response_model=RoleRead)
def update_role(
    role_id: int,
    payload: RoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("roles", "edit")),
) -> Role:
    role = _get_role_for_user(db, role_id, current_user)
    data = payload.model_dump(exclude_unset=True, exclude={"permission_ids"})
    if "is_system_role" in data and data["is_system_role"] != role.is_system_role:
        if not current_user.is_master_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo un administrador maestro puede cambiar roles de sistema",
            )
    if "company_id" in data or "is_system_role" in data:
        data["company_id"] = _role_company_id_for_write(
            current_user,
            data.get("company_id", role.company_id),
            bool(data.get("is_system_role", role.is_system_role)),
        )
    for field, value in data.items():
        setattr(role, field, value)
    if payload.permission_ids is not None:
        set_role_permissions(db, role.id, payload.permission_ids)
    db.commit()
    db.refresh(role)
    return role


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("roles", "delete")),
) -> None:
    role = _get_role_for_user(db, role_id, current_user)
    if role.is_system_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede eliminar un rol de sistema",
        )
    delete_item(db, role)
