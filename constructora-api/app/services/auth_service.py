from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.orm import Session

from app.core.security import create_access_token, verify_password
from app.models import User


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email).options(selectinload(User.company)))
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    if not user.is_master_admin:
        if user.company is None or user.company.license_status not in {"trial", "active"}:
            return None
        if user.company.license_expires_at and user.company.license_expires_at < date.today():
            return None
    return user


def issue_token(user: User) -> str:
    return create_access_token(subject=str(user.id))
