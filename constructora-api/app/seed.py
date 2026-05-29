from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models import Company, Role, User
from app.services.permissions import ensure_default_permissions, set_role_permissions, set_user_roles


def seed_admin(db: Session) -> User:
    permissions = ensure_default_permissions(db)

    company = db.scalar(select(Company).where(Company.name == settings.owner_company_name))
    if company is None:
        company = Company(
            name=settings.owner_company_name,
            legal_name=settings.owner_company_name,
            plan_name="owner",
            max_users=999,
            license_status="active",
            notes="Empresa propietaria del sistema ACSM Control",
        )
        db.add(company)
        db.flush()

    role = db.scalar(select(Role).where(Role.name == "master_admin"))
    if role is None:
        role = Role(
            name="master_admin",
            description="Rol sistema con todos los permisos iniciales",
            is_system_role=True,
        )
        db.add(role)
        db.flush()
    set_role_permissions(db, role.id, [permission.id for permission in permissions])

    user = db.scalar(select(User).where(User.email == settings.admin_email))
    if user is None:
        user = User(
            full_name=settings.admin_full_name,
            company_id=company.id,
            email=settings.admin_email,
            password_hash=get_password_hash(settings.admin_password),
            is_active=True,
            is_master_admin=True,
        )
        db.add(user)
        db.flush()
    else:
        user.full_name = settings.admin_full_name
        user.company_id = company.id
        user.is_active = True
        user.is_master_admin = True

    set_user_roles(db, user.id, [role.id])
    db.commit()
    db.refresh(user)
    return user


def main() -> None:
    db = SessionLocal()
    try:
        user = seed_admin(db)
        print(f"Usuario administrador listo: {user.email}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
