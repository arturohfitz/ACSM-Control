from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_permission
from app.db.session import get_db
from app.models import (
    Client,
    HouseModelDocument,
    HouseModelMaterialRequirement,
    Material,
    MaterialUnitConversion,
    Project,
    ProjectHouseModel,
    Supplier,
)
from app.models import User
from app.schemas.business import (
    MaterialCreate,
    MaterialModelCatalogCreate,
    MaterialModelCatalogRead,
    MaterialRead,
    MaterialUpdate,
    MaterialUnitConversionCreate,
    MaterialUnitConversionRead,
    MaterialUnitConversionUpdate,
)
from app.services.audit import record_create, record_delete, record_event, record_update, snapshot
from app.services.crud import get_or_404
from app.services.delete_guards import ensure_material_has_no_approved_quote
from app.services.tenancy import company_id_for_write, ensure_same_company, scoped_select


router = APIRouter()


def _normalize_unit(value: str) -> str:
    return value.strip().upper()


def _model_catalog_row(
    *,
    project: Project,
    client: Client,
    assignment: ProjectHouseModel,
    item: HouseModelMaterialRequirement,
) -> MaterialModelCatalogRead:
    return MaterialModelCatalogRead(
        id=item.id,
        project_id=project.id,
        project_name=project.name,
        client_id=client.id,
        client_name=client.name,
        house_model_id=assignment.house_model_id,
        house_model_name=assignment.house_model.name,
        material_id=item.material_id,
        material_name=item.material.name if item.material is not None else item.description,
        source_code=item.source_code,
        family=item.family,
        unit=item.material.unit if item.material is not None else item.unit,
        quantity_per_house=item.quantity_per_house,
        assigned_houses=assignment.quantity,
        total_required=item.quantity_per_house * assignment.quantity,
        unit_cost_reference=item.unit_cost_reference,
        total_cost_reference=item.total_cost_reference,
        catalog_unit_price=(
            item.material.current_unit_price if item.material is not None else None
        ),
        supplier_name=item.material.supplier_name if item.material is not None else None,
        validation_status=item.validation_status,
        is_linked=item.material_id is not None,
    )


def _project_model_assignment(
    db: Session,
    *,
    project_id: int,
    house_model_id: int,
) -> ProjectHouseModel:
    assignment = db.scalar(
        select(ProjectHouseModel)
        .where(
            ProjectHouseModel.project_id == project_id,
            ProjectHouseModel.house_model_id == house_model_id,
        )
        .options(selectinload(ProjectHouseModel.house_model))
    )
    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El modelo no esta asignado al desarrollo seleccionado",
        )
    return assignment


def _manual_material_document(
    db: Session,
    *,
    company_id: int,
    client_id: int,
    house_model_id: int,
) -> HouseModelDocument:
    file_hash = f"manual-materials:{company_id}:{client_id}:{house_model_id}"
    document = db.scalar(
        select(HouseModelDocument).where(
            HouseModelDocument.company_id == company_id,
            HouseModelDocument.house_model_id == house_model_id,
            HouseModelDocument.document_type == "explosion",
            HouseModelDocument.file_hash == file_hash,
        )
    )
    if document is not None:
        return document
    document = HouseModelDocument(
        company_id=company_id,
        client_id=client_id,
        house_model_id=house_model_id,
        document_type="explosion",
        version="manual",
        source_code="manual",
        source_date=date.today(),
        file_name="Alta manual de materiales",
        file_hash=file_hash,
        status="manual",
        total_items=0,
        total_amount=Decimal("0"),
        notes="Partidas agregadas manualmente al catalogo del modelo.",
    )
    db.add(document)
    db.flush()
    return document


@router.get("", response_model=list[MaterialRead])
def list_materials(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("materials", "view")),
) -> list[Material]:
    statement = scoped_select(select(Material), Material, current_user).offset(skip).limit(limit)
    return list(db.scalars(statement).all())


@router.get("/model-catalog", response_model=list[MaterialModelCatalogRead])
def list_model_material_catalog(
    project_id: int,
    house_model_id: int,
    q: str | None = None,
    limit: int = Query(default=500, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("materials", "view")),
) -> list[MaterialModelCatalogRead]:
    project = get_or_404(db, Project, project_id)
    ensure_same_company(current_user, project, db=db)
    client = get_or_404(db, Client, project.client_id)
    assignment = db.scalar(
        select(ProjectHouseModel)
        .where(
            ProjectHouseModel.project_id == project_id,
            ProjectHouseModel.house_model_id == house_model_id,
        )
        .options(selectinload(ProjectHouseModel.house_model))
    )
    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El modelo no esta asignado al desarrollo seleccionado",
        )

    statement = (
        select(HouseModelMaterialRequirement)
        .where(
            HouseModelMaterialRequirement.client_id == project.client_id,
            HouseModelMaterialRequirement.house_model_id == house_model_id,
            HouseModelMaterialRequirement.validation_status != "ignored",
        )
        .options(selectinload(HouseModelMaterialRequirement.material))
        .order_by(
            HouseModelMaterialRequirement.sort_order,
            HouseModelMaterialRequirement.id,
        )
        .limit(limit)
    )
    if q:
        needle = f"%{q.strip()}%"
        statement = statement.where(
            or_(
                HouseModelMaterialRequirement.description.ilike(needle),
                HouseModelMaterialRequirement.source_code.ilike(needle),
                HouseModelMaterialRequirement.family.ilike(needle),
            )
        )

    requirements = list(db.scalars(statement).all())
    return [
        _model_catalog_row(project=project, client=client, assignment=assignment, item=item)
        for item in requirements
    ]


@router.post("/model-catalog", response_model=MaterialModelCatalogRead, status_code=status.HTTP_201_CREATED)
def create_model_catalog_material(
    payload: MaterialModelCatalogCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("materials", "create")),
) -> MaterialModelCatalogRead:
    project = get_or_404(db, Project, payload.project_id)
    ensure_same_company(current_user, project, db=db)
    client = get_or_404(db, Client, project.client_id)
    ensure_same_company(current_user, client, db=db)
    assignment = _project_model_assignment(
        db,
        project_id=project.id,
        house_model_id=payload.house_model_id,
    )
    ensure_same_company(current_user, assignment.house_model, db=db)
    if assignment.house_model.client_id != project.client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El modelo de casa no pertenece a la inmobiliaria del desarrollo",
        )

    supplier = get_or_404(db, Supplier, payload.supplier_id)
    ensure_same_company(current_user, supplier, db=db)
    if supplier.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El proveedor seleccionado no esta activo",
        )

    name = payload.name.strip()
    unit = payload.unit.strip().upper()
    existing_requirement = db.scalar(
        select(HouseModelMaterialRequirement.id).where(
            HouseModelMaterialRequirement.company_id == project.company_id,
            HouseModelMaterialRequirement.client_id == project.client_id,
            HouseModelMaterialRequirement.house_model_id == assignment.house_model_id,
            HouseModelMaterialRequirement.validation_status != "ignored",
            func.lower(HouseModelMaterialRequirement.description) == name.lower(),
            func.lower(HouseModelMaterialRequirement.unit) == unit.lower(),
        )
    )
    if existing_requirement is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este material ya esta registrado para el modelo seleccionado",
        )

    material = db.scalar(
        select(Material).where(
            Material.company_id == project.company_id,
            func.lower(Material.name) == name.lower(),
            func.lower(Material.unit) == unit.lower(),
        )
    )
    if material is None:
        material = Material(
            company_id=project.company_id,
            supplier_id=supplier.id,
            name=name,
            unit=unit,
            current_unit_price=payload.current_unit_price,
            supplier_name=supplier.name,
            last_price_update=payload.last_price_update or date.today(),
            is_active=payload.is_active,
        )
        db.add(material)
        db.flush()
        material_action = "create"
    else:
        material.supplier_id = supplier.id
        material.supplier_name = supplier.name
        material.current_unit_price = payload.current_unit_price
        material.last_price_update = payload.last_price_update or date.today()
        material.is_active = payload.is_active
        material_action = "update"

    document = _manual_material_document(
        db,
        company_id=project.company_id,
        client_id=project.client_id,
        house_model_id=assignment.house_model_id,
    )
    next_sort_order = db.scalar(
        select(func.coalesce(func.max(HouseModelMaterialRequirement.sort_order), 0) + 1).where(
            HouseModelMaterialRequirement.house_model_id == assignment.house_model_id,
            HouseModelMaterialRequirement.client_id == project.client_id,
        )
    ) or 1
    total_cost = payload.current_unit_price * payload.quantity_per_house
    requirement = HouseModelMaterialRequirement(
        company_id=project.company_id,
        client_id=project.client_id,
        house_model_id=assignment.house_model_id,
        document_id=document.id,
        material_id=material.id,
        source_code=payload.source_code.strip() if payload.source_code else None,
        description=name,
        unit=unit,
        quantity_per_house=payload.quantity_per_house,
        unit_cost_reference=payload.current_unit_price,
        total_cost_reference=total_cost,
        family=payload.family.strip() if payload.family else None,
        validation_status="validated",
        sort_order=next_sort_order,
        notes=payload.notes,
    )
    db.add(requirement)
    db.flush()
    document.total_items = db.scalar(
        select(func.count(HouseModelMaterialRequirement.id)).where(
            HouseModelMaterialRequirement.document_id == document.id,
            HouseModelMaterialRequirement.validation_status != "ignored",
        )
    ) or 0
    document.total_amount = db.scalar(
        select(func.coalesce(func.sum(HouseModelMaterialRequirement.total_cost_reference), 0)).where(
            HouseModelMaterialRequirement.document_id == document.id,
            HouseModelMaterialRequirement.validation_status != "ignored",
        )
    )
    record_event(
        db,
        current_user,
        module="materiales",
        action="create",
        entity_type="HouseModelMaterialRequirement",
        entity_id=requirement.id,
        company_id=requirement.company_id,
        label=requirement.description,
        description=(
            f"{current_user.full_name} agrego material manual al modelo "
            f"{assignment.house_model.name}: {requirement.description}"
        ),
        metadata={
            "project_id": project.id,
            "house_model_id": assignment.house_model_id,
            "material_id": material.id,
            "supplier_id": supplier.id,
            "material_action": material_action,
        },
    )
    db.commit()
    item = db.scalar(
        select(HouseModelMaterialRequirement)
        .where(HouseModelMaterialRequirement.id == requirement.id)
        .options(selectinload(HouseModelMaterialRequirement.material))
    )
    return _model_catalog_row(project=project, client=client, assignment=assignment, item=item)


@router.post("", response_model=MaterialRead, status_code=status.HTTP_201_CREATED)
def create_material(
    payload: MaterialCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("materials", "create")),
) -> Material:
    data = payload.model_dump()
    data["company_id"] = company_id_for_write(current_user, data.get("company_id"))
    if data.get("supplier_id") is not None:
        supplier = get_or_404(db, Supplier, data["supplier_id"])
        ensure_same_company(current_user, supplier, db=db)
        if supplier.company_id != data["company_id"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El proveedor no pertenece a la constructora del material",
            )
        data["supplier_name"] = supplier.name
    item = Material(**data)
    db.add(item)
    db.flush()
    record_create(db, current_user, module="materiales", item=item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/{material_id}/unit-conversions", response_model=list[MaterialUnitConversionRead])
def list_material_unit_conversions(
    material_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("materials", "view")),
) -> list[MaterialUnitConversion]:
    material = get_or_404(db, Material, material_id)
    ensure_same_company(current_user, material)
    return list(
        db.scalars(
            select(MaterialUnitConversion)
            .where(MaterialUnitConversion.material_id == material.id)
            .order_by(MaterialUnitConversion.from_unit)
        ).all()
    )


@router.post(
    "/{material_id}/unit-conversions",
    response_model=MaterialUnitConversionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_material_unit_conversion(
    material_id: int,
    payload: MaterialUnitConversionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("materials", "edit")),
) -> MaterialUnitConversion:
    material = get_or_404(db, Material, material_id)
    ensure_same_company(current_user, material)
    from_unit = _normalize_unit(payload.from_unit)
    to_unit = _normalize_unit(payload.to_unit)
    if to_unit != _normalize_unit(material.unit):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La unidad base de conversion debe coincidir con la unidad del material",
        )
    if from_unit == to_unit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No necesitas equivalencia cuando la unidad solicitada es igual a la unidad base",
        )
    existing = db.scalar(
        select(MaterialUnitConversion).where(
            MaterialUnitConversion.company_id == material.company_id,
            MaterialUnitConversion.material_id == material.id,
            MaterialUnitConversion.from_unit == from_unit,
            MaterialUnitConversion.to_unit == to_unit,
        )
    )
    if existing is not None:
        before = snapshot(existing, ["factor_to_base", "notes", "is_active"])
        existing.factor_to_base = payload.factor_to_base
        existing.notes = payload.notes
        existing.is_active = payload.is_active
        record_update(db, current_user, module="materiales", item=existing, before=before)
        db.commit()
        db.refresh(existing)
        return existing
    item = MaterialUnitConversion(
        company_id=material.company_id,
        material_id=material.id,
        from_unit=from_unit,
        to_unit=to_unit,
        factor_to_base=payload.factor_to_base,
        notes=payload.notes,
        is_active=payload.is_active,
    )
    db.add(item)
    db.flush()
    record_create(db, current_user, module="materiales", item=item)
    db.commit()
    db.refresh(item)
    return item


@router.patch(
    "/{material_id}/unit-conversions/{conversion_id}",
    response_model=MaterialUnitConversionRead,
)
def update_material_unit_conversion(
    material_id: int,
    conversion_id: int,
    payload: MaterialUnitConversionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("materials", "edit")),
) -> MaterialUnitConversion:
    material = get_or_404(db, Material, material_id)
    ensure_same_company(current_user, material)
    item = get_or_404(db, MaterialUnitConversion, conversion_id)
    if item.material_id != material.id or item.company_id != material.company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversion no encontrada")
    data = payload.model_dump(exclude_unset=True)
    if "from_unit" in data and data["from_unit"] is not None:
        data["from_unit"] = _normalize_unit(data["from_unit"])
    if "to_unit" in data and data["to_unit"] is not None:
        data["to_unit"] = _normalize_unit(data["to_unit"])
    target_to_unit = data.get("to_unit", item.to_unit)
    if target_to_unit != _normalize_unit(material.unit):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La unidad base de conversion debe coincidir con la unidad del material",
        )
    target_from_unit = data.get("from_unit", item.from_unit)
    if target_from_unit == target_to_unit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La unidad origen debe ser distinta a la unidad base",
        )
    before = snapshot(item, list(data.keys()))
    for field, value in data.items():
        setattr(item, field, value)
    record_update(db, current_user, module="materiales", item=item, before=before)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{material_id}/unit-conversions/{conversion_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_material_unit_conversion(
    material_id: int,
    conversion_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("materials", "edit")),
) -> None:
    material = get_or_404(db, Material, material_id)
    ensure_same_company(current_user, material)
    item = get_or_404(db, MaterialUnitConversion, conversion_id)
    if item.material_id != material.id or item.company_id != material.company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversion no encontrada")
    record_delete(db, current_user, module="materiales", item=item)
    db.delete(item)
    db.commit()


@router.get("/{material_id}", response_model=MaterialRead)
def get_material(
    material_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("materials", "view")),
) -> Material:
    item = get_or_404(db, Material, material_id)
    ensure_same_company(current_user, item)
    return item


@router.patch("/{material_id}", response_model=MaterialRead)
def update_material(
    material_id: int,
    payload: MaterialUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("materials", "edit")),
) -> Material:
    item = get_or_404(db, Material, material_id)
    ensure_same_company(current_user, item)
    data = payload.model_dump(exclude_unset=True)
    if "company_id" in data:
        data["company_id"] = company_id_for_write(current_user, data.get("company_id"))
    if data.get("supplier_id") is not None:
        supplier = get_or_404(db, Supplier, data["supplier_id"])
        ensure_same_company(current_user, supplier, db=db)
        if supplier.company_id != item.company_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El proveedor no pertenece a la constructora del material",
            )
        data["supplier_name"] = supplier.name
    before = snapshot(item, list(data.keys()))
    for field, value in data.items():
        setattr(item, field, value)
    record_update(db, current_user, module="materiales", item=item, before=before)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_material(
    material_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("materials", "delete")),
) -> None:
    item = get_or_404(db, Material, material_id)
    ensure_same_company(current_user, item)
    ensure_material_has_no_approved_quote(db, material_id)
    record_delete(db, current_user, module="materiales", item=item)
    db.delete(item)
    db.commit()
