from datetime import date
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORMModel, TimestampRead
from app.schemas.user import RoleRead, UserRead


LicenseStatus = Literal["trial", "active", "expired", "suspended", "cancelled"]


class CompanyBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    legal_name: str | None = None
    tax_id: str | None = None
    contact_email: EmailStr | None = None
    contact_phone: str | None = None
    plan_name: str = Field(default="standard", min_length=1, max_length=80)
    max_users: int = Field(default=5, ge=1)
    license_status: LicenseStatus = "active"
    license_starts_at: date | None = None
    license_expires_at: date | None = None
    notes: str | None = None


class CompanyCreate(CompanyBase):
    pass


class CompanyOnboardCreate(CompanyBase):
    admin_full_name: str = Field(min_length=1, max_length=200)
    admin_email: str = Field(min_length=3, max_length=255)
    admin_password: str = Field(min_length=8)
    create_default_roles: bool = True


class CompanyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    legal_name: str | None = None
    tax_id: str | None = None
    contact_email: EmailStr | None = None
    contact_phone: str | None = None
    plan_name: str | None = Field(default=None, min_length=1, max_length=80)
    max_users: int | None = Field(default=None, ge=1)
    license_status: LicenseStatus | None = None
    license_starts_at: date | None = None
    license_expires_at: date | None = None
    notes: str | None = None


class CompanyRead(CompanyBase, TimestampRead):
    id: int


class CompanyOnboardRead(ORMModel):
    company: CompanyRead
    admin_user: UserRead
    roles: list[RoleRead] = Field(default_factory=list)


class CompanyLicenseRead(ORMModel):
    id: int
    name: str
    plan_name: str
    max_users: int
    license_status: LicenseStatus
    license_starts_at: date | None = None
    license_expires_at: date | None = None
