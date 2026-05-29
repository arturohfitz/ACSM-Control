from fastapi import HTTPException, status
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.models import (
    Client,
    ConceptLabor,
    ConceptMaterial,
    ConstructionConcept,
    HouseModel,
    LaborRate,
    Material,
    Project,
    ProjectMaterialPrice,
    Quote,
    QuoteItem,
)


def ensure_can_delete_client(db: Session, client_id: int) -> None:
    linked_project = db.scalar(select(exists().where(Project.client_id == client_id)))
    if linked_project:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede eliminar un cliente con proyectos ligados",
        )


def ensure_project_has_no_approved_quote(db: Session, project_id: int) -> None:
    has_quote = db.scalar(
        select(exists().where(Quote.project_id == project_id, Quote.status == "approved"))
    )
    if has_quote:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede eliminar un proyecto ligado a una cotizacion aprobada",
        )


def ensure_house_model_has_no_approved_quote(db: Session, house_model_id: int) -> None:
    has_quote_item = db.scalar(
        select(
            exists()
            .where(QuoteItem.house_model_id == house_model_id)
            .where(QuoteItem.quote_id == Quote.id)
            .where(Quote.status == "approved")
        )
    )
    if has_quote_item:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede eliminar un modelo ligado a una cotizacion aprobada",
        )


def ensure_concept_has_no_approved_quote(db: Session, concept_id: int) -> None:
    has_quote_item = db.scalar(
        select(
            exists()
            .where(QuoteItem.construction_concept_id == concept_id)
            .where(QuoteItem.quote_id == Quote.id)
            .where(Quote.status == "approved")
        )
    )
    if has_quote_item:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede eliminar un concepto ligado a una cotizacion aprobada",
        )


def ensure_material_has_no_approved_quote(db: Session, material_id: int) -> None:
    linked_project_price = db.scalar(
        select(exists().where(ProjectMaterialPrice.material_id == material_id))
    )
    if linked_project_price:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede eliminar un material usado en tabuladores de desarrollo",
        )

    concept_ids = select(ConceptMaterial.construction_concept_id).where(
        ConceptMaterial.material_id == material_id
    )
    has_quote_item = db.scalar(
        select(
            exists()
            .where(QuoteItem.construction_concept_id.in_(concept_ids))
            .where(QuoteItem.quote_id == Quote.id)
            .where(Quote.status == "approved")
        )
    )
    if has_quote_item:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede eliminar un material ligado a una cotizacion aprobada",
        )


def ensure_labor_has_no_approved_quote(db: Session, labor_rate_id: int) -> None:
    concept_ids = select(ConceptLabor.construction_concept_id).where(
        ConceptLabor.labor_rate_id == labor_rate_id
    )
    has_quote_item = db.scalar(
        select(
            exists()
            .where(QuoteItem.construction_concept_id.in_(concept_ids))
            .where(QuoteItem.quote_id == Quote.id)
            .where(Quote.status == "approved")
        )
    )
    if has_quote_item:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede eliminar una mano de obra ligada a una cotizacion aprobada",
        )
