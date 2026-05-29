from collections.abc import Callable
from datetime import date

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import Role, User
from app.services.permissions import user_has_permission


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    subject = decode_access_token(token)
    if subject is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.scalar(
        select(User)
        .where(User.id == int(subject))
        .options(selectinload(User.roles).selectinload(Role.permissions), selectinload(User.company))
    )
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario inactivo o inexistente",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_master_admin:
        if user.company is None or user.company.license_status not in {"trial", "active"}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Licencia de empresa inactiva",
            )
        if user.company.license_expires_at and user.company.license_expires_at < date.today():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Licencia de empresa vencida",
            )
    return user


def require_permission(module: str, action: str) -> Callable[[User], User]:
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if not user_has_permission(current_user, module, action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permiso requerido: {module}:{action}",
            )
        return current_user

    return dependency


def require_master_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_master_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere administrador maestro",
        )
    return current_user
