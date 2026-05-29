from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models import (
    ConceptLabor,
    ConceptMaterial,
    ConstructionConcept,
    HouseModel,
    HouseModelConcept,
    Project,
    ProjectHouseModel,
    ProjectMaterialPrice,
    Quote,
    QuoteItem,
)


MONEY_QUANT = Decimal("0.01")
QUANTITY_QUANT = Decimal("0.0001")


@dataclass
class CalculatedItem:
    project_house_model_id: int
    house_model_id: int
    construction_concept_id: int
    description: str
    unit: str
    quantity: Decimal
    material_cost: Decimal
    labor_cost: Decimal
    equipment_cost: Decimal
    waste_amount: Decimal
    indirect_amount: Decimal
    profit_amount: Decimal
    total_cost: Decimal
    total_price: Decimal


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def quantity(value: Decimal) -> Decimal:
    return value.quantize(QUANTITY_QUANT, rounding=ROUND_HALF_UP)


def _concept_quantity(model: HouseModel, model_concept: HouseModelConcept) -> Decimal:
    if model_concept.quantity_formula_type == "per_m2":
        return quantity(model_concept.quantity_value * model.construction_m2)
    return quantity(model_concept.quantity_value)


def _material_unit_price(
    project_house_model: ProjectHouseModel,
    concept_material: ConceptMaterial,
    specific_prices: dict[tuple[int, int], ProjectMaterialPrice],
    general_prices: dict[int, ProjectMaterialPrice],
) -> Decimal:
    material = concept_material.material
    project_price = specific_prices.get(
        (project_house_model.house_model_id, material.id),
    ) or general_prices.get(material.id)
    if project_price is None:
        return material.current_unit_price
    if not project_price.include_in_quote:
        return Decimal("0")
    return project_price.unit_price


def _calculate_model_items(
    project_house_model: ProjectHouseModel,
    profit_percent: Decimal,
    specific_prices: dict[tuple[int, int], ProjectMaterialPrice],
    general_prices: dict[int, ProjectMaterialPrice],
) -> list[CalculatedItem]:
    model = project_house_model.house_model
    house_count = project_house_model.quantity
    items: list[CalculatedItem] = []

    for model_concept in sorted(model.model_concepts, key=lambda item: item.sort_order):
        concept = model_concept.construction_concept
        concept_quantity = _concept_quantity(model, model_concept) * house_count

        material_cost = sum(
            concept_quantity
            * concept_material.quantity_per_unit
            * _material_unit_price(
                project_house_model,
                concept_material,
                specific_prices,
                general_prices,
            )
            for concept_material in concept.concept_materials
            if concept_material.material.is_active
        )
        labor_cost = sum(
            concept_quantity
            * concept_labor.quantity_per_unit
            * concept_labor.labor_rate.unit_cost
            for concept_labor in concept.concept_labor
            if concept_labor.labor_rate.is_active
        )
        equipment_cost = Decimal("0")
        direct_cost = material_cost + labor_cost + equipment_cost
        waste_amount = direct_cost * concept.default_waste_percent
        indirect_amount = direct_cost * concept.default_indirect_percent
        subtotal = direct_cost + waste_amount + indirect_amount
        profit_amount = subtotal * profit_percent
        total_price = subtotal + profit_amount

        items.append(
            CalculatedItem(
                project_house_model_id=project_house_model.id,
                house_model_id=model.id,
                construction_concept_id=concept.id,
                description=f"{model.name} - {concept.code} {concept.name}",
                unit=concept.unit,
                quantity=quantity(concept_quantity),
                material_cost=money(material_cost),
                labor_cost=money(labor_cost),
                equipment_cost=money(equipment_cost),
                waste_amount=money(waste_amount),
                indirect_amount=money(indirect_amount),
                profit_amount=money(profit_amount),
                total_cost=money(direct_cost + waste_amount + indirect_amount),
                total_price=money(total_price),
            )
        )

    return items


def calculate_project_items(
    db: Session,
    project_id: int,
    profit_percent: Decimal | None = None,
) -> list[CalculatedItem]:
    project = db.scalar(select(Project).where(Project.id == project_id))
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado")

    assignments = db.scalars(
        select(ProjectHouseModel)
        .where(ProjectHouseModel.project_id == project_id)
        .options(
            selectinload(ProjectHouseModel.house_model)
            .selectinload(HouseModel.model_concepts)
            .selectinload(HouseModelConcept.construction_concept),
            selectinload(ProjectHouseModel.house_model)
            .selectinload(HouseModel.model_concepts)
            .selectinload(HouseModelConcept.construction_concept)
            .selectinload(ConstructionConcept.concept_materials)
            .selectinload(ConceptMaterial.material),
            selectinload(ProjectHouseModel.house_model)
            .selectinload(HouseModel.model_concepts)
            .selectinload(HouseModelConcept.construction_concept)
            .selectinload(ConstructionConcept.concept_labor)
            .selectinload(ConceptLabor.labor_rate),
        )
    ).all()
    if not assignments:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El proyecto no tiene modelos de casa asignados",
        )

    project_material_prices = list(
        db.scalars(
            select(ProjectMaterialPrice).where(
                ProjectMaterialPrice.project_id == project.id,
                ProjectMaterialPrice.is_active.is_(True),
            )
        ).all()
    )
    specific_prices = {
        (price.house_model_id, price.material_id): price
        for price in project_material_prices
        if price.house_model_id is not None
    }
    general_prices = {
        price.material_id: price
        for price in project_material_prices
        if price.house_model_id is None
    }

    percent = profit_percent if profit_percent is not None else Decimal(str(settings.default_profit_percent))
    items: list[CalculatedItem] = []
    for assignment in assignments:
        items.extend(_calculate_model_items(assignment, percent, specific_prices, general_prices))
    return items


def quote_totals(items: list[CalculatedItem]) -> dict[str, Decimal]:
    subtotal_direct_cost = sum(
        item.material_cost + item.labor_cost + item.equipment_cost for item in items
    )
    total_waste = sum(item.waste_amount for item in items)
    total_indirects = sum(item.indirect_amount for item in items)
    total_profit = sum(item.profit_amount for item in items)
    total_price = sum(item.total_price for item in items)
    return {
        "subtotal_direct_cost": money(subtotal_direct_cost),
        "total_waste": money(total_waste),
        "total_indirects": money(total_indirects),
        "total_profit": money(total_profit),
        "total_price": money(total_price),
    }


def next_quote_version(db: Session, project_id: int) -> int:
    current = db.scalar(select(func.max(Quote.version)).where(Quote.project_id == project_id))
    return (current or 0) + 1


def create_project_quote(
    db: Session,
    project_id: int,
    created_by: int | None,
    notes: str | None = None,
    valid_until=None,
    profit_percent: Decimal | None = None,
) -> Quote:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proyecto no encontrado",
        )

    items = calculate_project_items(db, project_id, profit_percent)
    totals = quote_totals(items)
    version = next_quote_version(db, project_id)
    quote = Quote(
        company_id=project.company_id,
        project_id=project_id,
        quote_number=f"COT-{project_id:04d}-V{version}",
        version=version,
        status="draft",
        notes=notes,
        valid_until=valid_until,
        created_by=created_by,
        **totals,
    )
    db.add(quote)
    db.flush()

    for item in items:
        db.add(QuoteItem(quote_id=quote.id, **item.__dict__))

    if project.status == "draft":
        project.status = "quoted"

    db.commit()
    db.refresh(quote)
    return quote
