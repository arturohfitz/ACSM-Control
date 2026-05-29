from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_master_admin, require_permission
from app.core.security import get_password_hash
from app.db.session import get_db
from app.models import Company, Role, User
from app.schemas.company import (
    CompanyCreate,
    CompanyLicenseRead,
    CompanyOnboardCreate,
    CompanyOnboardRead,
    CompanyRead,
    CompanyUpdate,
)
from app.services.crud import create_item, delete_item, get_or_404, update_item
from app.services.permissions import ensure_default_company_roles, set_user_roles
from app.services.tenancy import ensure_same_company


router = APIRouter()


@router.get("", response_model=list[CompanyRead])
def list_companies(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("companies", "view")),
) -> list[Company]:
    statement = select(Company).offset(skip).limit(limit)
    if not current_user.is_master_admin:
        statement = statement.where(Company.id == current_user.company_id)
    return list(db.scalars(statement).all())


@router.post("", response_model=CompanyRead, status_code=status.HTTP_201_CREATED)
def create_company(
    payload: CompanyCreate,
    db: Session = Depends(get_db),
    _=Depends(require_master_admin),
) -> Company:
    return create_item(db, Company, payload.model_dump())


@router.post("/onboard", response_model=CompanyOnboardRead, status_code=status.HTTP_201_CREATED)
def onboard_company(
    payload: CompanyOnboardCreate,
    db: Session = Depends(get_db),
    _=Depends(require_master_admin),
) -> dict[str, Company | User | list[Role]]:
    existing_user = db.scalar(select(User).where(User.email == payload.admin_email))
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un usuario con ese correo",
        )

    data = payload.model_dump(
        exclude={
            "admin_full_name",
            "admin_email",
            "admin_password",
            "create_default_roles",
        }
    )
    company = Company(**data)
    db.add(company)
    db.flush()

    roles = (
        ensure_default_company_roles(db, company.id)
        if payload.create_default_roles
        else []
    )
    admin_role = next(
        (role for role in roles if role.name == "Administrador de constructora"),
        None,
    )
    if admin_role is None:
        all_roles = ensure_default_company_roles(db, company.id)
        roles = all_roles
        admin_role = next(
            role for role in all_roles if role.name == "Administrador de constructora"
        )

    admin_user = User(
        company_id=company.id,
        full_name=payload.admin_full_name,
        email=payload.admin_email,
        password_hash=get_password_hash(payload.admin_password),
        is_active=True,
        is_master_admin=False,
    )
    db.add(admin_user)
    db.flush()
    set_user_roles(db, admin_user.id, [admin_role.id])

    db.commit()

    company = get_or_404(db, Company, company.id)
    admin_user = db.scalar(
        select(User)
        .where(User.id == admin_user.id)
        .options(selectinload(User.roles).selectinload(Role.permissions))
    )
    roles = list(
        db.scalars(
            select(Role)
            .where(Role.company_id == company.id)
            .options(selectinload(Role.permissions))
        ).all()
    )
    return {
        "company": company,
        "admin_user": admin_user,
        "roles": roles,
    }


@router.get("/license", response_model=CompanyLicenseRead)
def my_license(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings", "view")),
) -> Company:
    company = get_or_404(db, Company, current_user.company_id)
    ensure_same_company(current_user, company)
    return company


@router.get("/{company_id}", response_model=CompanyRead)
def get_company(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("companies", "view")),
) -> Company:
    company = get_or_404(db, Company, company_id)
    ensure_same_company(current_user, company)
    return company


@router.patch("/{company_id}", response_model=CompanyRead)
def update_company(
    company_id: int,
    payload: CompanyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_master_admin),
) -> Company:
    company = get_or_404(db, Company, company_id)
    ensure_same_company(current_user, company)
    return update_item(db, company, payload.model_dump(exclude_unset=True))


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(
    company_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_master_admin),
) -> None:
    company = get_or_404(db, Company, company_id)
    delete_item(db, company)
