from fastapi import APIRouter, Depends
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models import AuditEvent, User
from app.schemas.audit import AuditEventList, AuditEventRead
from app.services.tenancy import scoped_select


router = APIRouter()

PURCHASING_AUDIT_MODULES = (
    "compras",
    "proveedores",
    "convenios_proveedor",
    "ordenes_compra",
    "presupuesto_materiales",
    "facturas_proveedor",
    "pagos_proveedores",
    "conciliaciones_financieras",
)


def _list_audit_events(
    *,
    skip: int,
    limit: int,
    module: str | None,
    modules: tuple[str, ...] | None,
    action: str | None,
    search: str | None,
    db: Session,
    current_user: User,
) -> AuditEventList:
    statement = scoped_select(select(AuditEvent), AuditEvent, current_user)
    count_statement = scoped_select(select(func.count(AuditEvent.id)), AuditEvent, current_user)

    filters = []
    if modules:
        filters.append(AuditEvent.module.in_(modules))
    elif module:
        filters.append(AuditEvent.module == module)
    if action:
        filters.append(AuditEvent.action == action)
    if search:
        like = f"%{search.strip()}%"
        filters.append(
            or_(
                AuditEvent.description.ilike(like),
                AuditEvent.entity_label.ilike(like),
                AuditEvent.user_email.ilike(like),
                AuditEvent.user_name.ilike(like),
            )
        )
    if filters:
        statement = statement.where(*filters)
        count_statement = count_statement.where(*filters)

    total = db.scalar(count_statement) or 0
    items = list(
        db.scalars(
            statement.order_by(AuditEvent.created_at.desc()).offset(skip).limit(limit)
        ).all()
    )
    return AuditEventList(total=total, items=[AuditEventRead.model_validate(item) for item in items])


@router.get("", response_model=AuditEventList)
def list_audit_events(
    skip: int = 0,
    limit: int = 100,
    module: str | None = None,
    action: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("events", "view")),
) -> AuditEventList:
    return _list_audit_events(
        skip=skip,
        limit=limit,
        module=module,
        modules=None,
        action=action,
        search=search,
        db=db,
        current_user=current_user,
    )


@router.get("/purchasing", response_model=AuditEventList)
def list_purchasing_audit_events(
    skip: int = 0,
    limit: int = 100,
    action: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("purchasing_audit", "view")),
) -> AuditEventList:
    return _list_audit_events(
        skip=skip,
        limit=limit,
        module=None,
        modules=PURCHASING_AUDIT_MODULES,
        action=action,
        search=search,
        db=db,
        current_user=current_user,
    )
