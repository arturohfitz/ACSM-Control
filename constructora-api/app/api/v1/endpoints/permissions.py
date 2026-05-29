from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import require_master_admin, require_permission
from app.db.session import get_db
from app.models import Permission
from app.schemas.user import PermissionCreate, PermissionRead, PermissionUpdate
from app.services.crud import create_item, delete_item, get_or_404, list_items, update_item


router = APIRouter()


@router.get("", response_model=list[PermissionRead])
def list_permissions(
    skip: int = 0,
    limit: int = 200,
    db: Session = Depends(get_db),
    _=Depends(require_permission("roles", "view")),
) -> list[Permission]:
    return list_items(db, Permission, skip, limit)


@router.post("", response_model=PermissionRead, status_code=status.HTTP_201_CREATED)
def create_permission(
    payload: PermissionCreate,
    db: Session = Depends(get_db),
    _=Depends(require_master_admin),
) -> Permission:
    return create_item(db, Permission, payload.model_dump())


@router.patch("/{permission_id}", response_model=PermissionRead)
def update_permission(
    permission_id: int,
    payload: PermissionUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_master_admin),
) -> Permission:
    item = get_or_404(db, Permission, permission_id)
    return update_item(db, item, payload.model_dump(exclude_unset=True))


@router.delete("/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_permission(
    permission_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_master_admin),
) -> None:
    item = get_or_404(db, Permission, permission_id)
    delete_item(db, item)
