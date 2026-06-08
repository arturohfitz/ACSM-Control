from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_permission
from app.db.session import get_db
from app.models import Project, Quote, User
from app.schemas.quote import QuoteCalculateRequest, QuoteCreate, QuoteRead, QuoteUpdate
from app.services.audit import record_create, record_delete, record_event, record_update, snapshot
from app.services.crud import get_or_404
from app.services.quote_calculator import create_project_quote
from app.services.tenancy import company_id_for_write, ensure_same_company, scoped_select


router = APIRouter()


def _ensure_quote_can_change_status(status_value: str | None) -> None:
    if status_value == "approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La aprobacion debe hacerse desde el flujo de aprobacion",
        )


@router.get("", response_model=list[QuoteRead])
def list_quotes(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("quotes", "view")),
) -> list[Quote]:
    statement = scoped_select(select(Quote), Quote, current_user)
    return list(
        db.scalars(statement.options(selectinload(Quote.items)).offset(skip).limit(limit)).all()
    )


@router.post("", response_model=QuoteRead, status_code=status.HTTP_201_CREATED)
def create_quote(
    payload: QuoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("quotes", "create")),
) -> Quote:
    project = db.get(Project, payload.project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se permite crear cotizacion sin proyecto valido",
        )
    _ensure_quote_can_change_status(payload.status)
    ensure_same_company(current_user, project, db=db)
    company_id = (
        company_id_for_write(current_user, payload.company_id or project.company_id)
        if current_user.is_master_admin
        else project.company_id
    )
    quote_number = payload.quote_number or f"COT-MANUAL-{payload.project_id:04d}-V{payload.version}"
    quote = Quote(
        company_id=company_id,
        project_id=payload.project_id,
        quote_number=quote_number,
        version=payload.version,
        status=payload.status,
        notes=payload.notes,
        valid_until=payload.valid_until,
        created_by=current_user.id,
    )
    db.add(quote)
    db.flush()
    record_create(db, current_user, module="cotizaciones", item=quote)
    db.commit()
    db.refresh(quote)
    return quote


@router.get("/{quote_id}", response_model=QuoteRead)
def get_quote(
    quote_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("quotes", "view")),
) -> Quote:
    quote = get_or_404(db, Quote, quote_id)
    ensure_same_company(current_user, quote, db=db)
    return quote


@router.patch("/{quote_id}", response_model=QuoteRead)
def update_quote(
    quote_id: int,
    payload: QuoteUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("quotes", "edit")),
) -> Quote:
    quote = get_or_404(db, Quote, quote_id)
    ensure_same_company(current_user, quote, db=db)
    if quote.status == "approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede editar una cotizacion aprobada",
        )
    data = payload.model_dump(exclude_unset=True)
    _ensure_quote_can_change_status(data.get("status"))
    before = snapshot(quote, list(data.keys()))
    for field, value in data.items():
        setattr(quote, field, value)
    record_update(db, current_user, module="cotizaciones", item=quote, before=before)
    db.commit()
    db.refresh(quote)
    return quote


@router.delete("/{quote_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_quote(
    quote_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("quotes", "edit")),
) -> None:
    quote = get_or_404(db, Quote, quote_id)
    ensure_same_company(current_user, quote, db=db)
    if quote.status == "approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede eliminar una cotizacion aprobada",
        )
    record_delete(db, current_user, module="cotizaciones", item=quote)
    db.delete(quote)
    db.commit()


@router.post("/calculate/project/{project_id}", response_model=QuoteRead)
def calculate_project_quote(
    project_id: int,
    payload: QuoteCalculateRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("quotes", "create")),
) -> Quote:
    payload = payload or QuoteCalculateRequest()
    project = get_or_404(db, Project, project_id)
    ensure_same_company(current_user, project, db=db)
    quote = create_project_quote(
        db=db,
        project_id=project_id,
        created_by=current_user.id,
        notes=payload.notes,
        valid_until=payload.valid_until,
        profit_percent=payload.profit_percent,
    )
    record_create(db, current_user, module="cotizaciones", item=quote)
    db.commit()
    db.refresh(quote)
    return quote


@router.post("/{quote_id}/approve", response_model=QuoteRead)
def approve_quote(
    quote_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("quotes", "approve")),
) -> Quote:
    quote = get_or_404(db, Quote, quote_id)
    ensure_same_company(current_user, quote, db=db)
    if quote.status in {"cancelled", "rejected"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede aprobar una cotizacion cancelada o rechazada",
        )
    if not quote.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede aprobar una cotizacion sin partidas",
        )
    quote.status = "approved"
    quote.approved_by = current_user.id
    quote.approved_at = datetime.now(timezone.utc)
    if quote.project is not None:
        quote.project.status = "approved"
        quote.project.approved_at = datetime.now(timezone.utc).date()
    record_event(
        db,
        current_user,
        module="cotizaciones",
        action="approve",
        entity_type="Quote",
        entity_id=quote.id,
        company_id=quote.company_id,
        label=quote.quote_number,
        description=f"{current_user.full_name} aprobo la cotizacion {quote.quote_number}",
        metadata={"status": "approved", "project_id": quote.project_id},
    )
    db.commit()
    db.refresh(quote)
    return quote
