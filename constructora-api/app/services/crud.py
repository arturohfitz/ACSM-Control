from typing import Any, TypeVar

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import Base


ModelT = TypeVar("ModelT", bound=Base)


def get_or_404(db: Session, model: type[ModelT], item_id: int) -> ModelT:
    item = db.get(model, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro no encontrado")
    return item


def list_items(db: Session, model: type[ModelT], skip: int = 0, limit: int = 100) -> list[ModelT]:
    return list(db.scalars(select(model).offset(skip).limit(limit)).all())


def create_item(db: Session, model: type[ModelT], data: dict[str, Any]) -> ModelT:
    item = model(**data)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_item(db: Session, item: ModelT, data: dict[str, Any]) -> ModelT:
    for field, value in data.items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


def delete_item(db: Session, item: ModelT) -> None:
    db.delete(item)
    db.commit()

