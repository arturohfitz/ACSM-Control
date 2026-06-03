from datetime import date
from decimal import Decimal
import hashlib
import logging
from pathlib import Path
import re

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_permission
from app.db.session import get_db
from app.models import (
    ExpectedMaterialItem,
    ExpectedMaterialList,
    Material,
    MaterialReception,
    MaterialReceptionItem,
    Project,
    ProjectHouseModel,
    ProjectMaterialPrice,
    ProjectWarehouse,
    PurchaseOrder,
    PurchaseOrderItem,
    User,
    WarehouseStock,
)
from app.schemas.inventory import (
    ExpectedMaterialItemCreate,
    ExpectedMaterialItemRead,
    ExpectedMaterialItemUpdate,
    ExpectedMaterialListCreate,
    ExpectedMaterialListRead,
    InventoryStatusItem,
    MaterialReceptionCreate,
    MaterialReceptionRead,
    ProjectWarehouseCreate,
    ProjectWarehouseRead,
    ProjectWarehouseUpdate,
    QuickInventoryDocumentCreate,
    QuickInventoryDocumentRead,
    QuickInventoryLine,
    QuickInventoryMetadata,
    QuickInventoryParsedDocument,
    QuickInventoryParseTextRequest,
    WarehouseStockRead,
)
from app.services.crud import delete_item, get_or_404, update_item
from app.services.pdf_text import PDFTextEmptyError, PDFTextExtractionError, extract_pdf_text
from app.services.tenancy import ensure_same_company, scoped_select


router = APIRouter()
logger = logging.getLogger(__name__)


SPANISH_MONTHS = {
    "ene": 1,
    "feb": 2,
    "mar": 3,
    "abr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "ago": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dic": 12,
}

PDF_ROW_RE = re.compile(
    r"^\s*(?P<line>\d+)\s+"
    r"(?P<code>\d+)\s+"
    r"(?P<description>.+?)\s+"
    r"(?P<account>\d{3}-\d+)\s+"
    r"(?P<delivery>\d{1,2}/[A-Za-zÁÉÍÓÚáéíóú]+/\d{4})\s+"
    r"(?P<quantity>[\d,]+(?:\.\d+)?)\s+"
    r"(?P<unit>[A-Z0-9]+)\s+"
    r"\$?(?P<unit_price>[\d,]+(?:\.\d+)?)\s*MN\s+"
    r"\$?(?P<line_total>[\d,]+(?:\.\d+)?)",
)


def _project_for_user(db: Session, project_id: int, current_user: User) -> Project:
    project = get_or_404(db, Project, project_id)
    ensure_same_company(current_user, project)
    return project


def _decimal_from_text(value: str | Decimal | None) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    cleaned = value.replace("$", "").replace(",", "").replace("MN", "").strip()
    if not cleaned:
        return None
    return Decimal(cleaned)


def _date_from_text(value: str | None) -> date | None:
    if not value:
        return None
    parts = value.strip().split("/")
    if len(parts) != 3:
        return None
    day, month_text, year = parts
    month = SPANISH_MONTHS.get(month_text[:3].lower())
    if month is None:
        return None
    return date(int(year), month, int(day))


def _text_date(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _clean_identifier(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", value).strip()
    return cleaned or None


def _hash_text(source_text: str) -> str:
    normalized = re.sub(r"\s+", " ", source_text).strip().encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()


def _duplicate_document_label(expected_list: ExpectedMaterialList) -> str:
    return (
        expected_list.document_number
        or expected_list.source_document_name
        or expected_list.name
        or f"lista #{expected_list.id}"
    )


def _find_duplicate_expected_list(
    db: Session,
    project: Project,
    document_number: str | None,
    source_document_name: str | None,
    source_document_hash: str | None,
) -> ExpectedMaterialList | None:
    conditions = []
    clean_hash = _clean_identifier(source_document_hash)
    clean_number = _clean_identifier(document_number)
    clean_name = _clean_identifier(source_document_name)

    if clean_hash:
        conditions.append(ExpectedMaterialList.source_document_hash == clean_hash)
    if clean_number:
        conditions.append(func.lower(ExpectedMaterialList.document_number) == clean_number.lower())
    if clean_name:
        conditions.append(func.lower(ExpectedMaterialList.source_document_name) == clean_name.lower())
    if not conditions:
        return None

    return db.scalar(
        select(ExpectedMaterialList)
        .where(
            ExpectedMaterialList.company_id == project.company_id,
            ExpectedMaterialList.project_id == project.id,
            or_(*conditions),
        )
        .order_by(ExpectedMaterialList.created_at.desc())
        .limit(1)
    )


def _ensure_document_not_duplicated(
    db: Session,
    project: Project,
    document_number: str | None,
    source_document_name: str | None,
    source_document_hash: str | None,
) -> None:
    duplicate = _find_duplicate_expected_list(
        db,
        project,
        document_number,
        source_document_name,
        source_document_hash,
    )
    if duplicate is None:
        return
    label = _duplicate_document_label(duplicate)
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            f"Este documento ya fue registrado en este desarrollo: {label}. "
            "Revisa la seccion Documentos antes de cargarlo de nuevo."
        ),
    )


def _extract_metadata(
    source_text: str,
    source_document_name: str | None = None,
    source_document_hash: str | None = None,
) -> QuickInventoryMetadata:
    document_number = None
    document_match = re.search(
        r"(?:Orden de Compra|Requisici[oó]n OC Terceros)\s*:?\s*([A-Z0-9-]+)",
        source_text,
        flags=re.IGNORECASE,
    )
    if document_match:
        document_number = document_match.group(1).strip()
    if document_number is None:
        document_match = re.search(r"\bP\s*33\s*[-–]?\s*\d{3,8}\b", source_text, flags=re.IGNORECASE)
        if document_match:
            document_number = re.sub(r"\s+", "", document_match.group(0).upper()).replace("–", "-")

    document_date = None
    date_match = re.search(r"Fecha\s*:\s*(\d{1,2}/[A-Za-zÁÉÍÓÚáéíóú]+/\d{4})", source_text)
    if date_match:
        document_date = _date_from_text(date_match.group(1))

    supplier_name = None
    for line in source_text.splitlines():
        if "Proveedor" not in line:
            continue
        supplier_match = re.search(r"Proveedor\s*:?\s*(?:\d+\s*:?)?\s*(.+)", line)
        if supplier_match:
            supplier_name = supplier_match.group(1).split("Responsable")[0].strip()
            supplier_name = re.sub(r"\s{2,}.*$", "", supplier_name).strip()
            if supplier_name:
                break

    return QuickInventoryMetadata(
        document_number=document_number,
        supplier_name=supplier_name,
        document_date=document_date,
        source_document_name=source_document_name,
        source_document_hash=source_document_hash,
    )


def _parse_delimited_lines(source_text: str) -> list[QuickInventoryLine]:
    lines = [line.strip() for line in source_text.splitlines() if line.strip()]
    if not lines:
        return []

    first = lines[0]
    has_header = any(word in first.lower() for word in ("material", "descripcion", "descripción", "cantidad"))
    header = [cell.strip().lower() for cell in first.split("\t")] if has_header else []
    rows = lines[1:] if has_header else lines
    items: list[QuickInventoryLine] = []

    def cell(cells: list[str], *names: str, default: str = "") -> str:
        for name in names:
            if name in header:
                index = header.index(name)
                if index < len(cells):
                    return cells[index].strip()
        return default

    for row in rows:
        cells = [part.strip() for part in row.split("\t")]
        if len(cells) < 3:
            continue
        if header:
            description = cell(cells, "material", "descripcion", "descripción", "description")
            quantity_text = cell(cells, "cantidad", "expected_quantity", "esperado")
            unit = cell(cells, "unidad", "unit")
            code = cell(cells, "codigo", "código", "insumo")
            unit_price_text = cell(cells, "precio", "precio unitario", "unit_price")
            total_text = cell(cells, "importe", "total", "line_total")
        else:
            code = cells[0] if len(cells) >= 5 else None
            description = cells[1] if len(cells) >= 5 else cells[0]
            quantity_text = cells[2] if len(cells) >= 5 else cells[1]
            unit = cells[3] if len(cells) >= 5 else cells[2]
            unit_price_text = cells[4] if len(cells) >= 5 else (cells[3] if len(cells) > 3 else "")
            total_text = cells[5] if len(cells) > 5 else ""
        quantity = _decimal_from_text(quantity_text)
        if not description or not unit or quantity is None:
            continue
        items.append(
            QuickInventoryLine(
                source_code=code or None,
                description=description,
                unit=unit,
                expected_quantity=quantity,
                unit_price=_decimal_from_text(unit_price_text),
                line_total=_decimal_from_text(total_text),
            )
        )
    return items


def _decimal_from_ocr_number(value: str | None, decimal_places: int | None = None) -> Decimal | None:
    if value is None:
        return None
    cleaned = re.sub(r"[^\d.,]", "", value)
    if not cleaned:
        return None
    if decimal_places is not None and "." not in cleaned and "," not in cleaned:
        return Decimal(cleaned) / (Decimal(10) ** decimal_places)
    return _decimal_from_text(cleaned)


def _normalize_ocr_unit(value: str) -> str:
    unit = re.sub(r"[^A-Za-z0-9]", "", value).upper()
    return {"RZ": "PZ", "P2": "PZ"}.get(unit, unit)


def _parse_invoice_ocr_lines(source_text: str) -> list[QuickInventoryLine]:
    items: list[QuickInventoryLine] = []
    row_re = re.compile(
        r"^(?P<prefix>.+?)\s+"
        r"(?P<quantity>\d+(?:[\.,]\d+)?)\s+"
        r"(?P<unit>[A-Za-z0-9]{1,4})\s+"
        r"\(?(?P<unit_price>\d[\d\s.,]*)\)?\s+"
        r"(?P<line_total>\d[\d\s.,]*)$",
        flags=re.IGNORECASE,
    )
    for raw_line in source_text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line or any(header in line.upper() for header in ("DESCRIPCION", "DESCRIPCIÓN", "CANTIDAD")):
            continue
        match = row_re.match(line)
        if not match:
            continue

        prefix = re.sub(r"[—_]+", " ", match.group("prefix")).strip(" -")
        if len(prefix) < 4:
            continue
        parts = prefix.split(maxsplit=1)
        source_code = None
        description = prefix
        if len(parts) == 2 and re.search(r"\d", parts[0]) and len(parts[0]) <= 14:
            source_code = parts[0].strip(" .:-")
            description = parts[1].strip(" .:-")
        quantity = _decimal_from_ocr_number(match.group("quantity"))
        unit = _normalize_ocr_unit(match.group("unit"))
        if quantity is None or not description or not unit:
            continue
        items.append(
            QuickInventoryLine(
                source_code=source_code,
                description=description,
                unit=unit,
                expected_quantity=quantity,
                unit_price=_decimal_from_ocr_number(match.group("unit_price"), decimal_places=4),
                line_total=_decimal_from_ocr_number(match.group("line_total"), decimal_places=2),
            )
        )
    return items


def _parse_inventory_text(
    source_text: str,
    source_document_name: str | None = None,
    source_document_hash: str | None = None,
) -> QuickInventoryParsedDocument:
    metadata = _extract_metadata(source_text, source_document_name, source_document_hash)
    items: list[QuickInventoryLine] = []
    delivery_dates: list[date] = []

    for line in source_text.splitlines():
        match = PDF_ROW_RE.match(line)
        if not match:
            continue
        delivery_date = _date_from_text(match.group("delivery"))
        if delivery_date is not None:
            delivery_dates.append(delivery_date)
        items.append(
            QuickInventoryLine(
                source_code=match.group("code"),
                description=re.sub(r"\s+", " ", match.group("description")).strip(),
                unit=match.group("unit"),
                expected_quantity=_decimal_from_text(match.group("quantity")) or Decimal("0"),
                unit_price=_decimal_from_text(match.group("unit_price")),
                line_total=_decimal_from_text(match.group("line_total")),
                delivery_date=delivery_date,
            )
        )

    if not items:
        items = _parse_delimited_lines(source_text)
    if not items:
        items = _parse_invoice_ocr_lines(source_text)
    if metadata.delivery_date is None and delivery_dates:
        metadata.delivery_date = min(delivery_dates)
    return QuickInventoryParsedDocument(metadata=metadata, items=items)


def _extract_pdf_text(file_bytes: bytes, file_name: str) -> str:
    try:
        return extract_pdf_text(file_bytes, file_name, timeout_seconds=10)
    except PDFTextEmptyError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El PDF no contiene texto extraible",
        ) from exc
    except PDFTextExtractionError as exc:
        logger.exception("No fue posible extraer texto del PDF de inventario %s", file_name)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fue posible extraer texto del PDF",
        ) from exc


def _warehouse_for_project(
    db: Session,
    warehouse_id: int,
    project: Project,
    current_user: User,
) -> ProjectWarehouse:
    warehouse = get_or_404(db, ProjectWarehouse, warehouse_id)
    ensure_same_company(current_user, warehouse)
    if warehouse.project_id != project.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La bodega no pertenece al proyecto",
        )
    return warehouse


def _expected_list_for_project(
    db: Session,
    expected_list_id: int,
    project: Project,
    current_user: User,
) -> ExpectedMaterialList:
    expected_list = get_or_404(db, ExpectedMaterialList, expected_list_id)
    ensure_same_company(current_user, expected_list)
    if expected_list.project_id != project.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La lista esperada no pertenece al proyecto",
        )
    return expected_list


def _fill_expected_item_data(
    db: Session,
    payload: ExpectedMaterialItemCreate | ExpectedMaterialItemUpdate,
    company_id: int,
    current_user: User,
    existing: ExpectedMaterialItem | None = None,
) -> dict:
    data = payload.model_dump(exclude_unset=True)
    material_id = data.get("material_id", existing.material_id if existing else None)
    material = None
    if material_id is not None:
        material = get_or_404(db, Material, material_id)
        ensure_same_company(current_user, material)
        if material.company_id != company_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El material no pertenece a la empresa del proyecto",
            )
        data["description"] = data.get("description") or material.name
        data["unit"] = data.get("unit") or material.unit

    description = data.get("description", existing.description if existing else None)
    unit = data.get("unit", existing.unit if existing else None)
    if not description or not unit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Descripcion y unidad son requeridas",
        )
    data["description"] = description
    data["unit"] = unit
    return data


def _status_for_item(item: ExpectedMaterialItem, has_issue: bool = False) -> str:
    if has_issue:
        return "with_issue"
    if item.received_quantity <= 0:
        return "pending"
    if item.received_quantity < item.expected_quantity:
        return "partial"
    if item.received_quantity == item.expected_quantity:
        return "complete"
    return "over_received"


def _upsert_stock(
    db: Session,
    warehouse: ProjectWarehouse,
    expected_item: ExpectedMaterialItem,
    received_quantity: Decimal,
) -> None:
    stock_item = db.scalar(
        select(WarehouseStock).where(
            WarehouseStock.warehouse_id == warehouse.id,
            WarehouseStock.expected_item_id == expected_item.id,
        )
    )
    if stock_item is None:
        stock_item = WarehouseStock(
            company_id=warehouse.company_id,
            warehouse_id=warehouse.id,
            expected_item_id=expected_item.id,
            material_id=expected_item.material_id,
            description=expected_item.description,
            unit=expected_item.unit,
            quantity_on_hand=Decimal("0"),
        )
        db.add(stock_item)
    stock_item.quantity_on_hand += received_quantity


def _sync_purchase_order_item(
    db: Session,
    expected_item: ExpectedMaterialItem,
    received_quantity: Decimal,
) -> None:
    if expected_item.purchase_order_item_id is None:
        return
    po_item = db.get(PurchaseOrderItem, expected_item.purchase_order_item_id)
    if po_item is None:
        return
    po_item.received_quantity += received_quantity
    if po_item.received_quantity <= 0:
        po_item.status = "pending"
    elif po_item.received_quantity < po_item.quantity_ordered:
        po_item.status = "partial"
    else:
        po_item.status = "complete"
    purchase_order = db.get(PurchaseOrder, po_item.purchase_order_id)
    if purchase_order is None:
        return
    if all(item.received_quantity >= item.quantity_ordered for item in purchase_order.items):
        purchase_order.status = "received"
    elif any(item.received_quantity > 0 for item in purchase_order.items):
        purchase_order.status = "partially_received"


def _default_warehouse_for_project(db: Session, project: Project) -> ProjectWarehouse:
    warehouse = db.scalar(
        select(ProjectWarehouse)
        .where(ProjectWarehouse.project_id == project.id, ProjectWarehouse.is_active.is_(True))
        .order_by(ProjectWarehouse.id)
    )
    if warehouse is not None:
        return warehouse
    warehouse = ProjectWarehouse(
        company_id=project.company_id,
        project_id=project.id,
        name=f"Bodega {project.name}",
        location=project.location,
        is_active=True,
    )
    db.add(warehouse)
    db.flush()
    return warehouse


def _single_project_house_model_id(db: Session, project: Project) -> int | None:
    ids = list(
        db.scalars(
            select(ProjectHouseModel.house_model_id).where(ProjectHouseModel.project_id == project.id)
        ).all()
    )
    return ids[0] if len(ids) == 1 else None


def _material_for_quick_line(
    db: Session,
    project: Project,
    line: QuickInventoryLine,
    supplier_name: str | None,
    auto_create: bool,
) -> Material | None:
    if line.material_id is not None:
        material = get_or_404(db, Material, line.material_id)
        if material.company_id != project.company_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Una partida usa un material de otra constructora",
            )
        return material

    material = db.scalar(
        select(Material).where(
            Material.company_id == project.company_id,
            func.lower(Material.name) == line.description.strip().lower(),
            func.lower(Material.unit) == line.unit.strip().lower(),
        )
    )
    if material is not None or not auto_create:
        return material

    material = Material(
        company_id=project.company_id,
        name=line.description.strip(),
        unit=line.unit.strip(),
        current_unit_price=line.unit_price or Decimal("0"),
        supplier_name=supplier_name,
        last_price_update=line.delivery_date,
        is_active=True,
    )
    db.add(material)
    db.flush()
    return material


def _upsert_project_price_from_quick_line(
    db: Session,
    project: Project,
    material: Material | None,
    house_model_id: int | None,
    line: QuickInventoryLine,
    supplier_name: str | None,
    supply_source: str,
    include_in_quote: bool,
    document_name: str | None,
) -> None:
    if material is None or line.unit_price is None:
        return
    statement = select(ProjectMaterialPrice).where(
        ProjectMaterialPrice.project_id == project.id,
        ProjectMaterialPrice.material_id == material.id,
    )
    if house_model_id is None:
        statement = statement.where(ProjectMaterialPrice.house_model_id.is_(None))
    else:
        statement = statement.where(ProjectMaterialPrice.house_model_id == house_model_id)
    project_price = db.scalar(statement)
    if project_price is None:
        project_price = ProjectMaterialPrice(
            company_id=project.company_id,
            project_id=project.id,
            house_model_id=house_model_id,
            material_id=material.id,
            unit=line.unit,
        )
        db.add(project_price)
    project_price.unit = line.unit
    project_price.unit_price = line.unit_price
    project_price.supply_source = supply_source
    project_price.supplier_name = supplier_name
    project_price.include_in_quote = include_in_quote
    project_price.source_document_name = document_name
    project_price.effective_date = line.delivery_date
    project_price.notes = line.notes
    project_price.is_active = True


def _status_response(items: list[ExpectedMaterialItem]) -> list[dict]:
    response = []
    for item in items:
        pending = max(item.expected_quantity - item.received_quantity, Decimal("0"))
        over_received = max(item.received_quantity - item.expected_quantity, Decimal("0"))
        response.append(
            {
                "expected_item_id": item.id,
                "expected_list_id": item.expected_list_id,
                "material_id": item.material_id,
                "source_code": item.source_code,
                "description": item.description,
                "unit": item.unit,
                "expected_quantity": item.expected_quantity,
                "unit_price": item.unit_price,
                "line_total": item.line_total,
                "received_quantity": item.received_quantity,
                "pending_quantity": pending,
                "over_received_quantity": over_received,
                "status": item.status,
                "notes": item.notes,
            }
        )
    return response


@router.get("/warehouses", response_model=list[ProjectWarehouseRead])
def list_warehouses(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory", "view")),
) -> list[ProjectWarehouse]:
    statement = scoped_select(select(ProjectWarehouse), ProjectWarehouse, current_user)
    return list(db.scalars(statement.offset(skip).limit(limit)).all())


@router.post("/warehouses", response_model=ProjectWarehouseRead, status_code=status.HTTP_201_CREATED)
def create_warehouse(
    payload: ProjectWarehouseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory", "create")),
) -> ProjectWarehouse:
    project = _project_for_user(db, payload.project_id, current_user)
    warehouse = ProjectWarehouse(
        company_id=project.company_id,
        **payload.model_dump(),
    )
    db.add(warehouse)
    db.commit()
    db.refresh(warehouse)
    return warehouse


@router.patch("/warehouses/{warehouse_id}", response_model=ProjectWarehouseRead)
def update_warehouse(
    warehouse_id: int,
    payload: ProjectWarehouseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory", "edit")),
) -> ProjectWarehouse:
    warehouse = get_or_404(db, ProjectWarehouse, warehouse_id)
    ensure_same_company(current_user, warehouse)
    return update_item(db, warehouse, payload.model_dump(exclude_unset=True))


@router.delete("/warehouses/{warehouse_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_warehouse(
    warehouse_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory", "delete")),
) -> None:
    warehouse = get_or_404(db, ProjectWarehouse, warehouse_id)
    ensure_same_company(current_user, warehouse)
    delete_item(db, warehouse)


@router.get("/projects/{project_id}/warehouses", response_model=list[ProjectWarehouseRead])
def list_project_warehouses(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory", "view")),
) -> list[ProjectWarehouse]:
    project = _project_for_user(db, project_id, current_user)
    return list(
        db.scalars(
            select(ProjectWarehouse)
            .where(ProjectWarehouse.project_id == project.id)
            .order_by(ProjectWarehouse.name)
        ).all()
    )


@router.get("/projects/{project_id}/expected-materials", response_model=list[ExpectedMaterialListRead])
def list_expected_materials(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory", "view")),
) -> list[ExpectedMaterialList]:
    project = _project_for_user(db, project_id, current_user)
    return list(
        db.scalars(
            select(ExpectedMaterialList)
            .where(ExpectedMaterialList.project_id == project.id)
            .options(selectinload(ExpectedMaterialList.items))
            .order_by(ExpectedMaterialList.created_at.desc())
        ).all()
    )


@router.post(
    "/projects/{project_id}/expected-materials",
    response_model=ExpectedMaterialListRead,
    status_code=status.HTTP_201_CREATED,
)
def create_expected_material_list(
    project_id: int,
    payload: ExpectedMaterialListCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory", "create")),
) -> ExpectedMaterialList:
    project = _project_for_user(db, project_id, current_user)
    if payload.warehouse_id is not None:
        _warehouse_for_project(db, payload.warehouse_id, project, current_user)
    if payload.purchase_order_id is not None:
        purchase_order = get_or_404(db, PurchaseOrder, payload.purchase_order_id)
        ensure_same_company(current_user, purchase_order)
        if purchase_order.project_id != project.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La orden de compra no pertenece al desarrollo",
            )
    _ensure_document_not_duplicated(
        db,
        project,
        payload.document_number,
        payload.source_document_name,
        payload.source_document_hash,
    )

    expected_list = ExpectedMaterialList(
        company_id=project.company_id,
        project_id=project.id,
        warehouse_id=payload.warehouse_id,
        purchase_order_id=payload.purchase_order_id,
        name=payload.name,
        document_number=payload.document_number,
        supplier_name=payload.supplier_name,
        document_date=payload.document_date,
        delivery_date=payload.delivery_date,
        source_document_name=payload.source_document_name,
        source_document_hash=payload.source_document_hash,
        source_notes=payload.source_notes,
    )
    db.add(expected_list)
    db.flush()

    for item_payload in payload.items:
        data = _fill_expected_item_data(db, item_payload, project.company_id, current_user)
        db.add(
            ExpectedMaterialItem(
                company_id=project.company_id,
                expected_list_id=expected_list.id,
                status="pending",
                received_quantity=Decimal("0"),
                **data,
            )
        )
    db.commit()
    db.refresh(expected_list)
    return expected_list


@router.post(
    "/projects/{project_id}/quick-documents/parse-text",
    response_model=QuickInventoryParsedDocument,
)
def parse_quick_inventory_text(
    project_id: int,
    payload: QuickInventoryParseTextRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory", "create")),
) -> QuickInventoryParsedDocument:
    _project_for_user(db, project_id, current_user)
    return _parse_inventory_text(
        payload.source_text,
        payload.source_document_name,
        _hash_text(payload.source_text),
    )


@router.post(
    "/projects/{project_id}/quick-documents/parse-pdf",
    response_model=QuickInventoryParsedDocument,
)
async def parse_quick_inventory_pdf(
    project_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory", "create")),
) -> QuickInventoryParsedDocument:
    _project_for_user(db, project_id, current_user)
    file_bytes = await file.read()
    suffix = Path(file.filename or "").suffix.lower()
    content_type = (file.content_type or "").lower()
    if content_type.startswith("image/") or suffix in {".jpg", ".jpeg", ".png", ".webp"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Las imagenes se analizan con OCR desde la pantalla de inventario. Selecciona la imagen y presiona Analizar.",
        )
    source_text = _extract_pdf_text(file_bytes, file.filename or "documento.pdf")
    source_document_hash = hashlib.sha256(file_bytes).hexdigest()
    return _parse_inventory_text(source_text, file.filename, source_document_hash)


@router.post(
    "/projects/{project_id}/quick-documents",
    response_model=QuickInventoryDocumentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_quick_inventory_document(
    project_id: int,
    payload: QuickInventoryDocumentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory", "create")),
) -> dict:
    project = _project_for_user(db, project_id, current_user)
    warehouse = (
        _warehouse_for_project(db, payload.warehouse_id, project, current_user)
        if payload.warehouse_id is not None
        else _default_warehouse_for_project(db, project)
    )
    house_model_id = _single_project_house_model_id(db, project)
    source_document_name = payload.source_document_name or payload.document_number
    list_name = payload.name or payload.document_number or f"Documento material {date.today().isoformat()}"
    _ensure_document_not_duplicated(
        db,
        project,
        payload.document_number,
        source_document_name,
        payload.source_document_hash,
    )

    expected_list = ExpectedMaterialList(
        company_id=project.company_id,
        project_id=project.id,
        warehouse_id=warehouse.id,
        name=list_name,
        document_number=payload.document_number,
        supplier_name=payload.supplier_name,
        document_date=payload.document_date,
        delivery_date=payload.delivery_date,
        source_document_name=source_document_name,
        source_document_hash=payload.source_document_hash,
        source_notes=payload.source_notes,
    )
    db.add(expected_list)
    db.flush()

    expected_items: list[tuple[ExpectedMaterialItem, QuickInventoryLine]] = []
    for line in payload.items:
        material = _material_for_quick_line(
            db,
            project,
            line,
            payload.supplier_name,
            payload.auto_create_materials,
        )
        if payload.update_project_prices:
            _upsert_project_price_from_quick_line(
                db,
                project,
                material,
                house_model_id,
                line,
                payload.supplier_name,
                payload.supply_source,
                payload.include_in_quote,
                source_document_name,
            )
        expected_item = ExpectedMaterialItem(
            company_id=project.company_id,
            expected_list_id=expected_list.id,
            material_id=material.id if material else line.material_id,
            source_code=line.source_code,
            description=line.description,
            unit=line.unit,
            expected_quantity=line.expected_quantity,
            unit_price=line.unit_price,
            line_total=line.line_total,
            delivery_date=line.delivery_date or payload.delivery_date,
            received_quantity=Decimal("0"),
            status="pending",
            notes=line.notes,
        )
        db.add(expected_item)
        expected_items.append((expected_item, line))

    reception = None
    received_lines = [
        (expected_item, line)
        for expected_item, line in expected_items
        if line.received_quantity is not None and line.received_quantity > 0
    ]
    if received_lines:
        reception = MaterialReception(
            company_id=project.company_id,
            project_id=project.id,
            warehouse_id=warehouse.id,
            expected_list_id=expected_list.id,
            received_at=payload.received_at or date.today(),
            delivery_reference=payload.delivery_reference or payload.document_number,
            received_by=payload.received_by,
            notes=payload.source_notes,
        )
        db.add(reception)
        db.flush()
        for expected_item, line in received_lines:
            db.add(
                MaterialReceptionItem(
                    reception_id=reception.id,
                    expected_item_id=expected_item.id,
                    material_id=expected_item.material_id,
                    description=expected_item.description,
                    unit=expected_item.unit,
                    received_quantity=line.received_quantity or Decimal("0"),
                    condition_status=line.condition_status,
                    notes=line.notes,
                )
            )
            expected_item.received_quantity += line.received_quantity or Decimal("0")
            expected_item.status = _status_for_item(
                expected_item,
                has_issue=line.condition_status != "ok",
            )
            _sync_purchase_order_item(db, expected_item, line.received_quantity or Decimal("0"))
            _upsert_stock(db, warehouse, expected_item, line.received_quantity or Decimal("0"))

    db.commit()
    db.refresh(expected_list)
    if reception is not None:
        db.refresh(reception)
    return {"expected_list": expected_list, "reception": reception}


@router.post(
    "/expected-lists/{expected_list_id}/items",
    response_model=ExpectedMaterialItemRead,
    status_code=status.HTTP_201_CREATED,
)
def add_expected_material_item(
    expected_list_id: int,
    payload: ExpectedMaterialItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory", "edit")),
) -> ExpectedMaterialItem:
    expected_list = get_or_404(db, ExpectedMaterialList, expected_list_id)
    ensure_same_company(current_user, expected_list)
    data = _fill_expected_item_data(db, payload, expected_list.company_id, current_user)
    item = ExpectedMaterialItem(
        company_id=expected_list.company_id,
        expected_list_id=expected_list.id,
        received_quantity=Decimal("0"),
        status="pending",
        **data,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/expected-items/{item_id}", response_model=ExpectedMaterialItemRead)
def update_expected_material_item(
    item_id: int,
    payload: ExpectedMaterialItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory", "edit")),
) -> ExpectedMaterialItem:
    item = get_or_404(db, ExpectedMaterialItem, item_id)
    ensure_same_company(current_user, item)
    if item.received_quantity > 0 and payload.expected_quantity is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede cambiar la cantidad esperada si ya hay recepciones",
        )
    data = _fill_expected_item_data(db, payload, item.company_id, current_user, existing=item)
    for field, value in data.items():
        setattr(item, field, value)
    item.status = _status_for_item(item)
    db.commit()
    db.refresh(item)
    return item


@router.post(
    "/projects/{project_id}/receptions",
    response_model=MaterialReceptionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_reception(
    project_id: int,
    payload: MaterialReceptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory", "receive")),
) -> MaterialReception:
    project = _project_for_user(db, project_id, current_user)
    warehouse = _warehouse_for_project(db, payload.warehouse_id, project, current_user)
    expected_list = _expected_list_for_project(
        db, payload.expected_list_id, project, current_user
    )
    if expected_list.warehouse_id is not None and expected_list.warehouse_id != warehouse.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La recepcion debe registrarse en la bodega de la lista esperada",
        )

    reception = MaterialReception(
        company_id=project.company_id,
        project_id=project.id,
        warehouse_id=warehouse.id,
        expected_list_id=expected_list.id,
        received_at=payload.received_at or date.today(),
        delivery_reference=payload.delivery_reference,
        delivered_by=payload.delivered_by,
        received_by=payload.received_by,
        notes=payload.notes,
    )
    db.add(reception)
    db.flush()

    for item_payload in payload.items:
        expected_item = get_or_404(db, ExpectedMaterialItem, item_payload.expected_item_id)
        ensure_same_company(current_user, expected_item)
        if expected_item.expected_list_id != expected_list.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Una partida recibida no pertenece a la lista esperada",
            )
        db.add(
            MaterialReceptionItem(
                reception_id=reception.id,
                expected_item_id=expected_item.id,
                material_id=expected_item.material_id,
                description=expected_item.description,
                unit=expected_item.unit,
                received_quantity=item_payload.received_quantity,
                condition_status=item_payload.condition_status,
                notes=item_payload.notes,
            )
        )
        expected_item.received_quantity += item_payload.received_quantity
        expected_item.status = _status_for_item(
            expected_item,
            has_issue=item_payload.condition_status != "ok",
        )
        _sync_purchase_order_item(db, expected_item, item_payload.received_quantity)
        _upsert_stock(db, warehouse, expected_item, item_payload.received_quantity)

    db.commit()
    db.refresh(reception)
    return reception


@router.get("/projects/{project_id}/receptions", response_model=list[MaterialReceptionRead])
def list_project_receptions(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory", "view")),
) -> list[MaterialReception]:
    project = _project_for_user(db, project_id, current_user)
    return list(
        db.scalars(
            select(MaterialReception)
            .where(MaterialReception.project_id == project.id)
            .options(selectinload(MaterialReception.items))
            .order_by(MaterialReception.received_at.desc(), MaterialReception.id.desc())
        ).all()
    )


@router.get("/projects/{project_id}/status", response_model=list[InventoryStatusItem])
def project_inventory_status(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory", "view")),
) -> list[dict]:
    project = _project_for_user(db, project_id, current_user)
    items = list(
        db.scalars(
            select(ExpectedMaterialItem)
            .join(ExpectedMaterialList)
            .where(ExpectedMaterialList.project_id == project.id)
            .order_by(ExpectedMaterialItem.description)
        ).all()
    )
    return _status_response(items)


@router.get("/projects/{project_id}/missing-materials", response_model=list[InventoryStatusItem])
def project_missing_materials(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory", "view")),
) -> list[dict]:
    project = _project_for_user(db, project_id, current_user)
    items = list(
        db.scalars(
            select(ExpectedMaterialItem)
            .join(ExpectedMaterialList)
            .where(
                ExpectedMaterialList.project_id == project.id,
                ExpectedMaterialItem.received_quantity < ExpectedMaterialItem.expected_quantity,
            )
            .order_by(ExpectedMaterialItem.description)
        ).all()
    )
    return _status_response(items)


@router.get("/warehouses/{warehouse_id}/stock", response_model=list[WarehouseStockRead])
def warehouse_stock(
    warehouse_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory", "view")),
) -> list[WarehouseStock]:
    warehouse = get_or_404(db, ProjectWarehouse, warehouse_id)
    ensure_same_company(current_user, warehouse)
    return list(
        db.scalars(
            select(WarehouseStock)
            .where(WarehouseStock.warehouse_id == warehouse.id)
            .order_by(WarehouseStock.description)
        ).all()
    )
