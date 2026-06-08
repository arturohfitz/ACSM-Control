from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel, TimestampRead


class PermissionBase(BaseModel):
    module: str = Field(min_length=1, max_length=80)
    action: str = Field(min_length=1, max_length=80)
    description: str | None = None


class PermissionCreate(PermissionBase):
    pass


class PermissionUpdate(BaseModel):
    module: str | None = Field(default=None, min_length=1, max_length=80)
    action: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = None


class PermissionRead(PermissionBase, ORMModel):
    id: int


class RoleBase(BaseModel):
    company_id: int | None = None
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    is_system_role: bool = False


class RoleCreate(RoleBase):
    permission_ids: list[int] = Field(default_factory=list)


class RoleUpdate(BaseModel):
    company_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    is_system_role: bool | None = None
    permission_ids: list[int] | None = None


class RoleRead(RoleBase, TimestampRead):
    id: int
    permissions: list[PermissionRead] = Field(default_factory=list)


class UserClientScopeRead(ORMModel):
    id: int
    name: str


class UserBase(BaseModel):
    company_id: int | None = None
    full_name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=255)
    is_active: bool = True
    is_master_admin: bool = False
    client_access_mode: str = Field(default="all", pattern="^(all|restricted)$")


class UserCreate(UserBase):
    password: str = Field(min_length=8)
    role_ids: list[int] = Field(default_factory=list)
    client_ids: list[int] = Field(default_factory=list)


class UserUpdate(BaseModel):
    company_id: int | None = None
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    email: str | None = Field(default=None, min_length=3, max_length=255)
    password: str | None = Field(default=None, min_length=8)
    is_active: bool | None = None
    is_master_admin: bool | None = None
    client_access_mode: str | None = Field(default=None, pattern="^(all|restricted)$")
    role_ids: list[int] | None = None
    client_ids: list[int] | None = None


class UserRead(UserBase, TimestampRead):
    id: int
    roles: list[RoleRead] = Field(default_factory=list)
    clients: list[UserClientScopeRead] = Field(default_factory=list)


class UserMe(ORMModel):
    id: int
    company_id: int | None = None
    full_name: str
    email: str
    is_active: bool
    is_master_admin: bool
    client_access_mode: str
    created_at: datetime
    updated_at: datetime
    permissions: list[str] = Field(default_factory=list)
