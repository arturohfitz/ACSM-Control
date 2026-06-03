from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.models import AuditEvent, User


ACTION_LABELS = {
    "create": "creo",
    "update": "edito",
    "delete": "elimino",
    "approve": "aprobo",
    "send": "envio",
    "validate": "valido",
    "link": "vinculo",
    "ignore": "ignoro",
    "schedule": "programo",
    "pay": "pago",
    "upload": "cargo",
    "test_email": "probo correo",
}


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def entity_label(item: Any) -> str:
    for field in (
        "name",
        "title",
        "quote_number",
        "rfq_number",
        "po_number",
        "invoice_number",
        "document_number",
        "email",
    ):
        value = getattr(item, field, None)
        if value:
            return str(value)
    item_id = getattr(item, "id", None)
    return f"Registro {item_id}" if item_id is not None else "Registro"


def snapshot(item: Any, fields: list[str] | None = None) -> dict[str, Any]:
    mapper = inspect(item).mapper
    column_names = [column.key for column in mapper.column_attrs]
    selected = fields or column_names
    return {
        field: _json_value(getattr(item, field))
        for field in selected
        if field in column_names and hasattr(item, field)
    }


def changed_fields(before: dict[str, Any], after: dict[str, Any]) -> dict[str, dict[str, Any]]:
    changes: dict[str, dict[str, Any]] = {}
    for field in sorted(set(before) | set(after)):
        if before.get(field) != after.get(field):
            changes[field] = {"antes": before.get(field), "despues": after.get(field)}
    return changes


def record_event(
    db: Session,
    current_user: User,
    *,
    module: str,
    action: str,
    entity_type: str,
    entity_id: int | str | None,
    company_id: int | None,
    label: str | None = None,
    description: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    action_label = ACTION_LABELS.get(action, action)
    final_label = label or (str(entity_id) if entity_id is not None else entity_type)
    event = AuditEvent(
        company_id=company_id,
        user_id=current_user.id,
        user_name=current_user.full_name,
        user_email=current_user.email,
        module=module,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        entity_label=final_label,
        description=description
        or f"{current_user.full_name} {action_label} {entity_type}: {final_label}",
        event_metadata=metadata,
    )
    db.add(event)
    return event


def record_create(db: Session, current_user: User, *, module: str, item: Any) -> AuditEvent:
    return record_event(
        db,
        current_user,
        module=module,
        action="create",
        entity_type=item.__class__.__name__,
        entity_id=getattr(item, "id", None),
        company_id=getattr(item, "company_id", None),
        label=entity_label(item),
        metadata={"registro": snapshot(item)},
    )


def record_update(
    db: Session,
    current_user: User,
    *,
    module: str,
    item: Any,
    before: dict[str, Any],
) -> AuditEvent:
    after = snapshot(item, list(before.keys()))
    return record_event(
        db,
        current_user,
        module=module,
        action="update",
        entity_type=item.__class__.__name__,
        entity_id=getattr(item, "id", None),
        company_id=getattr(item, "company_id", None),
        label=entity_label(item),
        metadata={"cambios": changed_fields(before, after)},
    )


def record_delete(db: Session, current_user: User, *, module: str, item: Any) -> AuditEvent:
    return record_event(
        db,
        current_user,
        module=module,
        action="delete",
        entity_type=item.__class__.__name__,
        entity_id=getattr(item, "id", None),
        company_id=getattr(item, "company_id", None),
        label=entity_label(item),
        metadata={"registro_eliminado": snapshot(item)},
    )
