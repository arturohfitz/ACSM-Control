from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models import Client
from app.models import User
from app.schemas.business import ClientCreate, ClientRead, ClientUpdate
from app.services.audit import record_create, record_delete, record_update, snapshot
from app.services.crud import get_or_404
from app.services.delete_guards import ensure_can_delete_client
from app.services.tenancy import company_id_for_write, ensure_same_company, scoped_select


router = APIRouter()


@router.get("", response_model=list[ClientRead])
def list_clients(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("clients", "view")),
) -> list[Client]:
    statement = scoped_select(select(Client), Client, current_user).offset(skip).limit(limit)
    return list(db.scalars(statement).all())


@router.post("", response_model=ClientRead, status_code=status.HTTP_201_CREATED)
def create_client(
    payload: ClientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("clients", "create")),
) -> Client:
    data = payload.model_dump()
    data["company_id"] = company_id_for_write(current_user, data.get("company_id"))
    item = Client(**data)
    db.add(item)
    db.flush()
    record_create(db, current_user, module="desarrolladoras", item=item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/{client_id}", response_model=ClientRead)
def get_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("clients", "view")),
) -> Client:
    item = get_or_404(db, Client, client_id)
    ensure_same_company(current_user, item)
    return item


@router.patch("/{client_id}", response_model=ClientRead)
def update_client(
    client_id: int,
    payload: ClientUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("clients", "edit")),
) -> Client:
    item = get_or_404(db, Client, client_id)
    ensure_same_company(current_user, item)
    data = payload.model_dump(exclude_unset=True)
    if "company_id" in data:
        data["company_id"] = company_id_for_write(current_user, data.get("company_id"))
    before = snapshot(item, list(data.keys()))
    for field, value in data.items():
        setattr(item, field, value)
    record_update(db, current_user, module="desarrolladoras", item=item, before=before)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("clients", "delete")),
) -> None:
    item = get_or_404(db, Client, client_id)
    ensure_same_company(current_user, item)
    ensure_can_delete_client(db, client_id)
    record_delete(db, current_user, module="desarrolladoras", item=item)
    db.delete(item)
    db.commit()
