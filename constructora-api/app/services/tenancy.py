from typing import Any, TypeVar

from fastapi import HTTPException, status
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models import (
    Client,
    Company,
    ExpectedMaterialList,
    HouseModel,
    MaterialReception,
    Project,
    ProjectWarehouse,
    PurchaseOrder,
    SupplierInvoice,
    SupplierRFQ,
    User,
    UserClientAccess,
)


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
    statement = statement.where(getattr(model, "company_id") == get_user_company_id(user))
    return scope_client_access(statement, model, user)


def _is_client_restricted(user: User) -> bool:
    return not user.is_master_admin and user.client_access_mode == "restricted"


def _assigned_client_ids_from_user(user: User) -> set[int]:
    accesses = getattr(user, "user_client_accesses", []) or []
    return {access.client_id for access in accesses}


def allowed_client_ids(db: Session, user: User) -> list[int] | None:
    if not _is_client_restricted(user):
        return None
    return list(
        db.scalars(
            select(UserClientAccess.client_id).where(
                UserClientAccess.user_id == user.id,
                UserClientAccess.company_id == get_user_company_id(user),
            )
        ).all()
    )


def user_can_access_client_id(user: User, client_id: int | None) -> bool:
    if client_id is None or not _is_client_restricted(user):
        return True
    assigned_ids = _assigned_client_ids_from_user(user)
    return client_id in assigned_ids


def ensure_client_access(db: Session, user: User, client_id: int | None) -> None:
    if client_id is None or not _is_client_restricted(user):
        return
    exists = db.scalar(
        select(UserClientAccess.id).where(
            UserClientAccess.user_id == user.id,
            UserClientAccess.client_id == client_id,
            UserClientAccess.company_id == get_user_company_id(user),
        )
    )
    if exists is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registro no encontrado",
        )


def ensure_project_access(db: Session, user: User, project_id: int | None) -> None:
    if project_id is None or not _is_client_restricted(user):
        return
    project_client_id = db.scalar(select(Project.client_id).where(Project.id == project_id))
    ensure_client_access(db, user, project_client_id)


def ensure_clients_assignable(
    db: Session,
    *,
    client_ids: list[int],
    current_user: User,
    target_company_id: int,
) -> None:
    if not client_ids:
        return
    clients = list(
        db.scalars(
            select(Client).where(
                Client.id.in_(client_ids),
                Client.company_id == target_company_id,
            )
        ).all()
    )
    if len({client.id for client in clients}) != len(set(client_ids)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Una o mas desarrolladoras no pertenecen a la constructora del usuario",
        )
    if current_user.is_master_admin:
        return
    for client in clients:
        ensure_client_access(db, current_user, client.id)


def set_user_client_access(
    db: Session,
    *,
    user_id: int,
    company_id: int,
    client_ids: list[int],
) -> None:
    db.query(UserClientAccess).filter(UserClientAccess.user_id == user_id).delete()
    for client_id in sorted(set(client_ids)):
        db.add(
            UserClientAccess(
                company_id=company_id,
                user_id=user_id,
                client_id=client_id,
            )
        )


def scope_client_access(statement: Select, model: type[ModelT], user: User) -> Select:
    if not _is_client_restricted(user):
        return statement
    allowed_clients = select(UserClientAccess.client_id).where(
        UserClientAccess.user_id == user.id,
        UserClientAccess.company_id == get_user_company_id(user),
    )
    if model is Client:
        return statement.where(Client.id.in_(allowed_clients))
    if hasattr(model, "client_id"):
        return statement.where(getattr(model, "client_id").in_(allowed_clients))
    allowed_projects = select(Project.id).where(Project.client_id.in_(allowed_clients))
    if hasattr(model, "project_id"):
        return statement.where(getattr(model, "project_id").in_(allowed_projects))
    allowed_house_models = select(HouseModel.id).where(HouseModel.client_id.in_(allowed_clients))
    if hasattr(model, "house_model_id"):
        return statement.where(getattr(model, "house_model_id").in_(allowed_house_models))
    allowed_rfqs = select(SupplierRFQ.id).where(SupplierRFQ.project_id.in_(allowed_projects))
    if hasattr(model, "rfq_id"):
        return statement.where(getattr(model, "rfq_id").in_(allowed_rfqs))
    allowed_purchase_orders = select(PurchaseOrder.id).where(
        PurchaseOrder.project_id.in_(allowed_projects)
    )
    if hasattr(model, "purchase_order_id"):
        return statement.where(getattr(model, "purchase_order_id").in_(allowed_purchase_orders))
    allowed_invoices = select(SupplierInvoice.id).where(
        SupplierInvoice.purchase_order_id.in_(allowed_purchase_orders)
    )
    if hasattr(model, "supplier_invoice_id"):
        return statement.where(getattr(model, "supplier_invoice_id").in_(allowed_invoices))
    allowed_expected_lists = select(ExpectedMaterialList.id).where(
        ExpectedMaterialList.project_id.in_(allowed_projects)
    )
    if hasattr(model, "expected_list_id"):
        return statement.where(getattr(model, "expected_list_id").in_(allowed_expected_lists))
    allowed_warehouses = select(ProjectWarehouse.id).where(
        ProjectWarehouse.project_id.in_(allowed_projects)
    )
    if hasattr(model, "warehouse_id"):
        return statement.where(getattr(model, "warehouse_id").in_(allowed_warehouses))
    allowed_receptions = select(MaterialReception.id).where(
        MaterialReception.project_id.in_(allowed_projects)
    )
    if hasattr(model, "reception_id"):
        return statement.where(getattr(model, "reception_id").in_(allowed_receptions))
    return statement


def ensure_same_company(user: User, item: Any, db: Session | None = None) -> None:
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
    if isinstance(item, Client):
        client_id = item.id
    else:
        client_id = getattr(item, "client_id", None)
    if client_id is not None:
        if db is not None:
            ensure_client_access(db, user, client_id)
        elif not user_can_access_client_id(user, client_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Registro no encontrado",
            )
    elif db is not None and getattr(item, "project_id", None) is not None:
        ensure_project_access(db, user, getattr(item, "project_id"))
    elif db is not None and getattr(item, "house_model_id", None) is not None:
        client_id = db.scalar(
            select(HouseModel.client_id).where(HouseModel.id == getattr(item, "house_model_id"))
        )
        ensure_client_access(db, user, client_id)
    elif db is not None and getattr(item, "rfq_id", None) is not None:
        project_id = db.scalar(select(SupplierRFQ.project_id).where(SupplierRFQ.id == getattr(item, "rfq_id")))
        ensure_project_access(db, user, project_id)
    elif db is not None and getattr(item, "purchase_order_id", None) is not None:
        project_id = db.scalar(
            select(PurchaseOrder.project_id).where(PurchaseOrder.id == getattr(item, "purchase_order_id"))
        )
        ensure_project_access(db, user, project_id)
    elif db is not None and getattr(item, "supplier_invoice_id", None) is not None:
        project_id = db.scalar(
            select(PurchaseOrder.project_id)
            .join(SupplierInvoice, SupplierInvoice.purchase_order_id == PurchaseOrder.id)
            .where(SupplierInvoice.id == getattr(item, "supplier_invoice_id"))
        )
        ensure_project_access(db, user, project_id)
    elif db is not None and getattr(item, "expected_list_id", None) is not None:
        project_id = db.scalar(
            select(ExpectedMaterialList.project_id).where(
                ExpectedMaterialList.id == getattr(item, "expected_list_id")
            )
        )
        ensure_project_access(db, user, project_id)
    elif db is not None and getattr(item, "warehouse_id", None) is not None:
        project_id = db.scalar(
            select(ProjectWarehouse.project_id).where(ProjectWarehouse.id == getattr(item, "warehouse_id"))
        )
        ensure_project_access(db, user, project_id)
    elif db is not None and getattr(item, "reception_id", None) is not None:
        project_id = db.scalar(
            select(MaterialReception.project_id).where(MaterialReception.id == getattr(item, "reception_id"))
        )
        ensure_project_access(db, user, project_id)


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
