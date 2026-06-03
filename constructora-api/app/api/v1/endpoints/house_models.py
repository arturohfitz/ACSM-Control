from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4
import hashlib
import re
import subprocess
import tempfile

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pypdf import PdfReader
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_permission
from app.db.session import get_db
from app.models import (
    Client,
    ConstructionConcept,
    HouseModel,
    HouseModelBudgetActivity,
    HouseModelConcept,
    HouseModelDocument,
    HouseModelMaterialRequirement,
    Material,
    Project,
    ProjectHouseModel,
    User,
)
from app.schemas.business import (
    HouseModelBudgetActivityRead,
    HouseModelBudgetActivityUpdate,
    HouseModelConceptCreate,
    HouseModelConceptRead,
    HouseModelCreate,
    HouseModelDocumentDetail,
    HouseModelDocumentRead,
    HouseModelDocumentType,
    HouseModelMaterialRequirementRead,
    HouseModelMaterialRequirementUpdate,
    HouseModelRead,
    HouseModelUpdate,
)
from app.services.crud import delete_item, get_or_404, update_item
from app.services.audit import record_create, record_delete, record_event, record_update, snapshot
from app.services.delete_guards import ensure_house_model_has_no_approved_quote
from app.services.tenancy import company_id_for_write, ensure_same_company, scoped_select


router = APIRouter()

DOCUMENT_STORAGE = Path(__file__).resolve().parents[4] / "storage" / "house_model_documents"
EXPLOSION_ROW_RE = re.compile(
    r"^(?P<code>\d+-\d+-\d+)\s+"
    r"(?P<description>.+?)\s{2,}"
    r"(?P<unit>[A-Z0-9ÁÉÍÓÚÑÜ./\"-]{1,12})\s+"
    r"(?P<quantity>-?[\d,]+(?:\.\d+)?)\s+"
    r"\$?(?P<unit_cost>-?[\d,]+(?:\.\d+)?)\s+"
    r"\$?(?P<total>-?[\d,]+(?:\.\d+)?)"
    r"(?:\s+(?P<family>\S+))?\s*$"
)
BUDGET_ROW_RE = re.compile(
    r"^(?P<code>\d{3}-\d{2}-\d{3})\s+"
    r"(?P<description>.+?)\s{2,}"
    r"(?P<unit>[A-Z0-9ÁÉÍÓÚÑÜ./\"-]{1,12})\s+"
    r"(?P<quantity>-?[\d,]+(?:\.\d+)?)\s+"
    r"\$?(?P<unit_price>-?[\d,]+(?:\.\d+)?)\s+"
    r"\$?(?P<total>-?[\d,]+(?:\.\d+)?)\s*$"
)
CHAPTER_ROW_RE = re.compile(
    r"^(?P<code>\d{3})\s+(?P<name>[A-ZÁÉÍÓÚÑÜ0-9 ,()./-]+?)\s+"
    r"1\.00\s+\$?(?P<total>-?[\d,]+(?:\.\d+)?)\s+\$?(?P<total2>-?[\d,]+(?:\.\d+)?)\s*$"
)
SOURCE_CODE_RE = re.compile(r"\bP-\d{2}-[A-Z]-[A-Z]+-[A-Z]+-\d{2}\b")
DATE_RE = re.compile(r"\b(?P<day>\d{2})/(?P<month>\d{2})/(?P<year>\d{4})\b")


def _apply_client_company(
    db: Session,
    current_user: User,
    data: dict,
    fallback_company_id: int | None = None,
) -> None:
    if data.get("client_id") is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Selecciona la desarrolladora del modelo de casa",
        )

    client = get_or_404(db, Client, data["client_id"])
    ensure_same_company(current_user, client)
    requested_company_id = data.get("company_id") or fallback_company_id or client.company_id
    company_id = company_id_for_write(current_user, requested_company_id)
    if company_id != client.company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La desarrolladora no pertenece a la empresa indicada",
        )
    data["company_id"] = client.company_id


def _decimal_from_text(value: str | None) -> Decimal | None:
    if value is None:
        return None
    cleaned = value.replace("$", "").replace(",", "").strip()
    if cleaned == "":
        return None
    return Decimal(cleaned)


def _date_from_text(value: str | None) -> date | None:
    if value is None:
        return None
    match = DATE_RE.search(value)
    if not match:
        return None
    return date(int(match.group("year")), int(match.group("month")), int(match.group("day")))


def _extract_pdf_text(file_bytes: bytes, file_name: str) -> str:
    with tempfile.NamedTemporaryFile(suffix=Path(file_name).suffix or ".pdf") as tmp:
        tmp.write(file_bytes)
        tmp.flush()
        try:
            completed = subprocess.run(
                ["pdftotext", "-layout", tmp.name, "-"],
                check=True,
                capture_output=True,
                text=True,
                timeout=15,
            )
            if completed.stdout.strip():
                return completed.stdout
        except (FileNotFoundError, subprocess.SubprocessError):
            pass

    try:
        from io import BytesIO

        reader = PdfReader(BytesIO(file_bytes))
        text = "\n".join(page.extract_text(extraction_mode="layout") or "" for page in reader.pages)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fue posible extraer texto del PDF",
        ) from exc
    if not text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El PDF no contiene texto extraible",
        )
    return text


def _extract_document_metadata(source_text: str) -> tuple[str | None, date | None]:
    source_code_match = SOURCE_CODE_RE.search(source_text)
    source_code = source_code_match.group(0) if source_code_match else None
    source_date = _date_from_text(source_text[:1000])
    return source_code, source_date


def _material_id_for_description(db: Session, company_id: int, description: str) -> int | None:
    normalized = re.sub(r"\s+", " ", description).strip().lower()
    if not normalized:
        return None
    return db.scalar(
        select(Material.id)
        .where(Material.company_id == company_id, func.lower(Material.name) == normalized)
        .limit(1)
    )


def _concept_id_for_code(db: Session, company_id: int, code: str | None) -> int | None:
    if not code:
        return None
    return db.scalar(
        select(ConstructionConcept.id)
        .where(ConstructionConcept.company_id == company_id, ConstructionConcept.code == code)
        .limit(1)
    )


def _parse_explosion_items(
    db: Session,
    model: HouseModel,
    document: HouseModelDocument,
    source_text: str,
) -> list[HouseModelMaterialRequirement]:
    items: list[HouseModelMaterialRequirement] = []
    for line in source_text.splitlines():
        match = EXPLOSION_ROW_RE.match(line.strip())
        if not match:
            continue
        description = re.sub(r"\s+", " ", match.group("description")).strip()
        material_id = _material_id_for_description(db, model.company_id, description)
        items.append(
            HouseModelMaterialRequirement(
                company_id=model.company_id,
                client_id=model.client_id,
                house_model_id=model.id,
                document_id=document.id,
                material_id=material_id,
                source_code=match.group("code"),
                description=description[:255],
                unit=match.group("unit"),
                quantity_per_house=_decimal_from_text(match.group("quantity")) or Decimal("0"),
                unit_cost_reference=_decimal_from_text(match.group("unit_cost")),
                total_cost_reference=_decimal_from_text(match.group("total")),
                family=match.group("family"),
                validation_status="validated" if material_id is not None else "pending",
                sort_order=len(items) + 1,
            )
        )
    return items


def _parse_budget_activities(
    db: Session,
    model: HouseModel,
    document: HouseModelDocument,
    source_text: str,
) -> list[HouseModelBudgetActivity]:
    activities: list[HouseModelBudgetActivity] = []
    current_chapter_code: str | None = None
    current_chapter_name: str | None = None
    for line in source_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        chapter_match = CHAPTER_ROW_RE.match(stripped)
        if chapter_match:
            current_chapter_code = chapter_match.group("code")
            current_chapter_name = re.sub(r"\s+", " ", chapter_match.group("name")).strip().title()
            continue

        match = BUDGET_ROW_RE.match(stripped)
        if not match:
            if activities and _is_budget_description_continuation(stripped):
                continuation = re.sub(r"\s+", " ", stripped).strip()
                activities[-1].description = f"{activities[-1].description} {continuation}"
            continue
        description = re.sub(r"\s+", " ", match.group("description")).strip()
        source_code = match.group("code")
        concept_id = _concept_id_for_code(db, model.company_id, source_code)
        activities.append(
            HouseModelBudgetActivity(
                company_id=model.company_id,
                client_id=model.client_id,
                house_model_id=model.id,
                document_id=document.id,
                construction_concept_id=concept_id,
                chapter_code=current_chapter_code,
                chapter_name=current_chapter_name,
                source_code=source_code,
                description=description,
                unit=match.group("unit"),
                quantity_per_house=_decimal_from_text(match.group("quantity")) or Decimal("0"),
                unit_price_reference=_decimal_from_text(match.group("unit_price")),
                total_price_reference=_decimal_from_text(match.group("total")),
                validation_status="validated" if concept_id is not None else "pending",
                sort_order=len(activities) + 1,
            )
        )
    return activities


def _is_budget_description_continuation(line: str) -> bool:
    ignored_prefixes = (
        "ACSM,",
        "Clave",
        "Presupuesto",
        "Fraccionamiento:",
        "Prototipo:",
        "Condominio:",
        "Importe total",
    )
    if line.startswith(ignored_prefixes):
        return False
    if SOURCE_CODE_RE.search(line) or DATE_RE.search(line):
        return False
    if BUDGET_ROW_RE.match(line) or CHAPTER_ROW_RE.match(line):
        return False
    return bool(re.search(r"[A-Za-zÁÉÍÓÚÑÜáéíóúñü]", line))


def _store_document_file(company_id: int, file_bytes: bytes, file_name: str) -> str:
    suffix = Path(file_name).suffix.lower() or ".pdf"
    target_dir = DOCUMENT_STORAGE / str(company_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{uuid4().hex}{suffix}"
    target.write_bytes(file_bytes)
    return str(target.relative_to(Path(__file__).resolve().parents[4]))


def _require_model_child(
    db: Session,
    current_user: User,
    house_model_id: int,
    child: HouseModelMaterialRequirement | HouseModelBudgetActivity,
) -> None:
    model = get_or_404(db, HouseModel, house_model_id)
    ensure_same_company(current_user, model)
    ensure_same_company(current_user, child)
    if child.house_model_id != house_model_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La partida no pertenece al modelo indicado",
        )


def _recalculate_document_totals(db: Session, document_id: int) -> None:
    document = get_or_404(db, HouseModelDocument, document_id)
    if document.document_type == "explosion":
        items = list(
            db.scalars(
                select(HouseModelMaterialRequirement).where(
                    HouseModelMaterialRequirement.document_id == document_id,
                    HouseModelMaterialRequirement.validation_status != "ignored",
                )
            ).all()
        )
        document.total_items = len(items)
        document.total_amount = sum(
            (item.total_cost_reference or Decimal("0")) for item in items
        )
    else:
        activities = list(
            db.scalars(
                select(HouseModelBudgetActivity).where(
                    HouseModelBudgetActivity.document_id == document_id,
                    HouseModelBudgetActivity.validation_status != "ignored",
                )
            ).all()
        )
        document.total_items = len(activities)
        document.total_amount = sum(
            (activity.total_price_reference or Decimal("0")) for activity in activities
        )


@router.get("", response_model=list[HouseModelRead])
def list_house_models(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("house_models", "view")),
) -> list[HouseModel]:
    statement = scoped_select(select(HouseModel), HouseModel, current_user).offset(skip).limit(limit)
    return list(db.scalars(statement).all())


@router.post("", response_model=HouseModelRead, status_code=status.HTTP_201_CREATED)
def create_house_model(
    payload: HouseModelCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("house_models", "create")),
) -> HouseModel:
    data = payload.model_dump()
    _apply_client_company(db, current_user, data)
    item = HouseModel(**data)
    db.add(item)
    db.flush()
    record_create(db, current_user, module="modelos", item=item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/{house_model_id}", response_model=HouseModelRead)
def get_house_model(
    house_model_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("house_models", "view")),
) -> HouseModel:
    item = get_or_404(db, HouseModel, house_model_id)
    ensure_same_company(current_user, item)
    return item


@router.get("/{house_model_id}/documents", response_model=list[HouseModelDocumentDetail])
def list_house_model_documents(
    house_model_id: int,
    document_type: HouseModelDocumentType | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("house_models", "view")),
) -> list[HouseModelDocument]:
    model = get_or_404(db, HouseModel, house_model_id)
    ensure_same_company(current_user, model)
    statement = (
        select(HouseModelDocument)
        .where(HouseModelDocument.house_model_id == house_model_id)
        .options(
            selectinload(HouseModelDocument.material_requirements),
            selectinload(HouseModelDocument.budget_activities),
        )
        .order_by(HouseModelDocument.created_at.desc())
    )
    if document_type is not None:
        statement = statement.where(HouseModelDocument.document_type == document_type)
    return list(db.scalars(statement).all())


@router.post(
    "/{house_model_id}/documents",
    response_model=HouseModelDocumentDetail,
    status_code=status.HTTP_201_CREATED,
)
async def upload_house_model_document(
    house_model_id: int,
    document_type: HouseModelDocumentType = Query(...),
    version: str | None = Query(default=None, max_length=80),
    notes: str | None = Query(default=None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("house_models", "edit")),
) -> HouseModelDocument:
    model = get_or_404(db, HouseModel, house_model_id)
    ensure_same_company(current_user, model)
    if model.client_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El modelo debe pertenecer a una desarrolladora",
        )

    file_name = file.filename or "documento.pdf"
    suffix = Path(file_name).suffix.lower()
    if suffix != ".pdf" and (file.content_type or "").lower() != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Por ahora carga archivos PDF para explosion y presupuesto",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo esta vacio",
        )

    file_hash = hashlib.sha256(file_bytes).hexdigest()
    duplicated = db.scalar(
        select(HouseModelDocument).where(
            HouseModelDocument.company_id == model.company_id,
            HouseModelDocument.house_model_id == model.id,
            HouseModelDocument.document_type == document_type,
            HouseModelDocument.file_hash == file_hash,
        )
    )
    if duplicated is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este documento ya fue cargado para este modelo",
        )

    source_text = _extract_pdf_text(file_bytes, file_name)
    source_code, source_date = _extract_document_metadata(source_text)
    file_path = _store_document_file(model.company_id, file_bytes, file_name)
    document = HouseModelDocument(
        company_id=model.company_id,
        client_id=model.client_id,
        house_model_id=model.id,
        document_type=document_type,
        version=version,
        source_code=source_code,
        source_date=source_date,
        file_name=file_name,
        file_path=file_path,
        file_hash=file_hash,
        status="interpreted",
        notes=notes,
    )
    db.add(document)
    db.flush()

    if document_type == "explosion":
        parsed_items = _parse_explosion_items(db, model, document, source_text)
        if not parsed_items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se detectaron materiales en la explosion",
            )
        document.total_items = len(parsed_items)
        document.total_amount = sum(
            (item.total_cost_reference or Decimal("0")) for item in parsed_items
        )
        db.add_all(parsed_items)
    else:
        parsed_activities = _parse_budget_activities(db, model, document, source_text)
        if not parsed_activities:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se detectaron actividades en el presupuesto",
            )
        document.total_items = len(parsed_activities)
        document.total_amount = sum(
            (activity.total_price_reference or Decimal("0")) for activity in parsed_activities
        )
        db.add_all(parsed_activities)

    record_event(
        db,
        current_user,
        module="modelos",
        action="upload",
        entity_type="HouseModelDocument",
        entity_id=document.id,
        company_id=document.company_id,
        label=document.file_name,
        description=(
            f"{current_user.full_name} cargo {document.document_type} "
            f"para el modelo {model.name}"
        ),
        metadata={
            "modelo_id": model.id,
            "modelo": model.name,
            "tipo_documento": document.document_type,
            "partidas": document.total_items,
            "importe": str(document.total_amount or 0),
        },
    )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este documento ya fue cargado para este modelo",
        ) from exc
    db.refresh(document)
    return db.scalar(
        select(HouseModelDocument)
        .where(HouseModelDocument.id == document.id)
        .options(
            selectinload(HouseModelDocument.material_requirements),
            selectinload(HouseModelDocument.budget_activities),
        )
    )


@router.delete("/{house_model_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_house_model_document(
    house_model_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("house_models", "edit")),
) -> None:
    model = get_or_404(db, HouseModel, house_model_id)
    ensure_same_company(current_user, model)
    document = get_or_404(db, HouseModelDocument, document_id)
    ensure_same_company(current_user, document)
    if document.house_model_id != house_model_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El documento no pertenece al modelo indicado",
        )
    record_delete(db, current_user, module="modelos", item=document)
    db.delete(document)
    db.commit()


@router.patch(
    "/{house_model_id}/material-requirements/{item_id}",
    response_model=HouseModelMaterialRequirementRead,
)
def update_material_requirement(
    house_model_id: int,
    item_id: int,
    payload: HouseModelMaterialRequirementUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("house_models", "edit")),
) -> HouseModelMaterialRequirement:
    item = get_or_404(db, HouseModelMaterialRequirement, item_id)
    _require_model_child(db, current_user, house_model_id, item)
    data = payload.model_dump(exclude_unset=True)
    if data.get("validation_status") == "ignored":
        data["material_id"] = None
    if "material_id" in data and data["material_id"] is not None:
        material = get_or_404(db, Material, data["material_id"])
        ensure_same_company(current_user, material)
        if material.company_id != item.company_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El material no pertenece a la misma constructora",
            )
        data.setdefault("validation_status", "validated")
    elif "material_id" in data and data["material_id"] is None:
        data.setdefault("validation_status", "pending")
    if (
        data.get("validation_status") == "validated"
        and data.get("material_id", item.material_id) is None
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Para integrar la partida primero vincula o crea un material de catalogo",
        )
    for field, value in data.items():
        setattr(item, field, value)
    _recalculate_document_totals(db, item.document_id)
    if data:
        if data.get("validation_status") == "ignored":
            action = "ignore"
        elif "material_id" in data:
            action = "link"
        else:
            action = "update"
        record_event(
            db,
            current_user,
            module="modelos",
            action=action,
            entity_type="HouseModelMaterialRequirement",
            entity_id=item.id,
            company_id=item.company_id,
            label=item.description,
            description=f"{current_user.full_name} actualizo la integracion de material {item.description}",
            metadata={
                "modelo_id": house_model_id,
                "material_id": item.material_id,
                "estado": item.validation_status,
            },
        )
    db.commit()
    db.refresh(item)
    return item


@router.post(
    "/{house_model_id}/material-requirements/{item_id}/create-material",
    response_model=HouseModelMaterialRequirementRead,
    status_code=status.HTTP_201_CREATED,
)
def create_material_from_requirement(
    house_model_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("materials", "create")),
) -> HouseModelMaterialRequirement:
    item = get_or_404(db, HouseModelMaterialRequirement, item_id)
    _require_model_child(db, current_user, house_model_id, item)
    existing_id = _material_id_for_description(db, item.company_id, item.description)
    if existing_id is not None:
        item.material_id = existing_id
        item.validation_status = "validated"
        record_event(
            db,
            current_user,
            module="modelos",
            action="link",
            entity_type="HouseModelMaterialRequirement",
            entity_id=item.id,
            company_id=item.company_id,
            label=item.description,
            description=f"{current_user.full_name} vinculo material existente desde explosion {item.description}",
            metadata={"modelo_id": house_model_id, "material_id": existing_id},
        )
        db.commit()
        db.refresh(item)
        return item

    material = Material(
        company_id=item.company_id,
        name=item.description,
        unit=item.unit,
        current_unit_price=item.unit_cost_reference or Decimal("0"),
        supplier_name=None,
        last_price_update=date.today(),
        is_active=True,
    )
    db.add(material)
    db.flush()
    item.material_id = material.id
    item.validation_status = "validated"
    record_event(
        db,
        current_user,
        module="modelos",
        action="create",
        entity_type="Material",
        entity_id=material.id,
        company_id=material.company_id,
        label=material.name,
        description=f"{current_user.full_name} creo material desde explosion {material.name}",
        metadata={"modelo_id": house_model_id, "partida_id": item.id},
    )
    db.commit()
    db.refresh(item)
    return item


@router.post(
    "/{house_model_id}/documents/{document_id}/integrate-materials",
    response_model=HouseModelDocumentDetail,
)
def integrate_document_materials(
    house_model_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("materials", "create")),
) -> HouseModelDocument:
    document = get_or_404(db, HouseModelDocument, document_id)
    ensure_same_company(current_user, document)
    if document.house_model_id != house_model_id or document.document_type != "explosion":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El documento no corresponde a la explosion del modelo indicado",
        )
    pending_items = list(
        db.scalars(
            select(HouseModelMaterialRequirement)
            .where(
                HouseModelMaterialRequirement.document_id == document_id,
                HouseModelMaterialRequirement.validation_status != "ignored",
                HouseModelMaterialRequirement.material_id.is_(None),
            )
            .order_by(HouseModelMaterialRequirement.sort_order)
        ).all()
    )
    created = 0
    linked = 0
    for item in pending_items:
        existing_id = _material_id_for_description(db, item.company_id, item.description)
        if existing_id is not None:
            item.material_id = existing_id
            linked += 1
        else:
            material = Material(
                company_id=item.company_id,
                name=item.description,
                unit=item.unit,
                current_unit_price=item.unit_cost_reference or Decimal("0"),
                supplier_name=None,
                last_price_update=date.today(),
                is_active=True,
            )
            db.add(material)
            db.flush()
            item.material_id = material.id
            created += 1
        item.validation_status = "validated"
    if pending_items:
        record_event(
            db,
            current_user,
            module="modelos",
            action="link",
            entity_type="HouseModelDocument",
            entity_id=document.id,
            company_id=document.company_id,
            label=document.file_name,
            description=(
                f"{current_user.full_name} integro masivamente materiales "
                f"de la explosion {document.file_name}"
            ),
            metadata={
                "modelo_id": house_model_id,
                "documento_id": document.id,
                "partidas_integradas": len(pending_items),
                "materiales_creados": created,
                "materiales_vinculados": linked,
            },
        )
    _recalculate_document_totals(db, document.id)
    db.commit()
    return db.scalar(
        select(HouseModelDocument)
        .where(HouseModelDocument.id == document.id)
        .options(
            selectinload(HouseModelDocument.material_requirements),
            selectinload(HouseModelDocument.budget_activities),
        )
    )


@router.patch(
    "/{house_model_id}/budget-activities/{activity_id}",
    response_model=HouseModelBudgetActivityRead,
)
def update_budget_activity(
    house_model_id: int,
    activity_id: int,
    payload: HouseModelBudgetActivityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("house_models", "edit")),
) -> HouseModelBudgetActivity:
    activity = get_or_404(db, HouseModelBudgetActivity, activity_id)
    _require_model_child(db, current_user, house_model_id, activity)
    data = payload.model_dump(exclude_unset=True)
    if data.get("validation_status") == "ignored":
        data["construction_concept_id"] = None
    if "construction_concept_id" in data and data["construction_concept_id"] is not None:
        concept = get_or_404(db, ConstructionConcept, data["construction_concept_id"])
        ensure_same_company(current_user, concept)
        if concept.company_id != activity.company_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El concepto no pertenece a la misma constructora",
            )
        data.setdefault("validation_status", "validated")
    elif "construction_concept_id" in data and data["construction_concept_id"] is None:
        data.setdefault("validation_status", "pending")
    if (
        data.get("validation_status") == "validated"
        and data.get("construction_concept_id", activity.construction_concept_id) is None
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Para integrar la actividad primero vincula o crea un concepto de catalogo",
        )
    for field, value in data.items():
        setattr(activity, field, value)
    _recalculate_document_totals(db, activity.document_id)
    if data:
        action = (
            "ignore"
            if data.get("validation_status") == "ignored"
            else "link"
            if "construction_concept_id" in data
            else "update"
        )
        record_event(
            db,
            current_user,
            module="modelos",
            action=action,
            entity_type="HouseModelBudgetActivity",
            entity_id=activity.id,
            company_id=activity.company_id,
            label=activity.description[:255],
            description=f"{current_user.full_name} actualizo la integracion de actividad {activity.source_code or activity.id}",
            metadata={
                "modelo_id": house_model_id,
                "construction_concept_id": activity.construction_concept_id,
                "estado": activity.validation_status,
            },
        )
    db.commit()
    db.refresh(activity)
    return activity


@router.post(
    "/{house_model_id}/budget-activities/{activity_id}/create-concept",
    response_model=HouseModelBudgetActivityRead,
    status_code=status.HTTP_201_CREATED,
)
def create_concept_from_activity(
    house_model_id: int,
    activity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("construction_concepts", "create")),
) -> HouseModelBudgetActivity:
    activity = get_or_404(db, HouseModelBudgetActivity, activity_id)
    _require_model_child(db, current_user, house_model_id, activity)
    existing_id = _concept_id_for_code(db, activity.company_id, activity.source_code)
    if existing_id is not None:
        activity.construction_concept_id = existing_id
        activity.validation_status = "validated"
        record_event(
            db,
            current_user,
            module="modelos",
            action="link",
            entity_type="HouseModelBudgetActivity",
            entity_id=activity.id,
            company_id=activity.company_id,
            label=activity.description[:255],
            description=f"{current_user.full_name} vinculo concepto existente desde presupuesto {activity.source_code or activity.id}",
            metadata={"modelo_id": house_model_id, "construction_concept_id": existing_id},
        )
        db.commit()
        db.refresh(activity)
        return activity

    concept = ConstructionConcept(
        company_id=activity.company_id,
        code=activity.source_code or f"HM-{activity.id}",
        name=activity.description[:200],
        unit=activity.unit,
        description=activity.description,
        default_waste_percent=Decimal("0"),
        default_indirect_percent=Decimal("0"),
    )
    db.add(concept)
    db.flush()
    activity.construction_concept_id = concept.id
    activity.validation_status = "validated"
    record_event(
        db,
        current_user,
        module="modelos",
        action="create",
        entity_type="ConstructionConcept",
        entity_id=concept.id,
        company_id=concept.company_id,
        label=concept.name,
        description=f"{current_user.full_name} creo concepto desde presupuesto {concept.code}",
        metadata={"modelo_id": house_model_id, "actividad_id": activity.id},
    )
    db.commit()
    db.refresh(activity)
    return activity


@router.post(
    "/{house_model_id}/documents/{document_id}/integrate-concepts",
    response_model=HouseModelDocumentDetail,
)
def integrate_document_concepts(
    house_model_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("construction_concepts", "create")),
) -> HouseModelDocument:
    document = get_or_404(db, HouseModelDocument, document_id)
    ensure_same_company(current_user, document)
    if document.house_model_id != house_model_id or document.document_type != "budget":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El documento no corresponde al presupuesto del modelo indicado",
        )
    pending_activities = list(
        db.scalars(
            select(HouseModelBudgetActivity)
            .where(
                HouseModelBudgetActivity.document_id == document_id,
                HouseModelBudgetActivity.validation_status != "ignored",
                HouseModelBudgetActivity.construction_concept_id.is_(None),
            )
            .order_by(HouseModelBudgetActivity.sort_order)
        ).all()
    )
    created = 0
    linked = 0
    for activity in pending_activities:
        existing_id = _concept_id_for_code(db, activity.company_id, activity.source_code)
        if existing_id is not None:
            activity.construction_concept_id = existing_id
            linked += 1
        else:
            concept = ConstructionConcept(
                company_id=activity.company_id,
                code=activity.source_code or f"HM-{activity.id}",
                name=activity.description[:200],
                unit=activity.unit,
                description=activity.description,
                default_waste_percent=Decimal("0"),
                default_indirect_percent=Decimal("0"),
            )
            db.add(concept)
            db.flush()
            activity.construction_concept_id = concept.id
            created += 1
        activity.validation_status = "validated"
    if pending_activities:
        record_event(
            db,
            current_user,
            module="modelos",
            action="link",
            entity_type="HouseModelDocument",
            entity_id=document.id,
            company_id=document.company_id,
            label=document.file_name,
            description=(
                f"{current_user.full_name} integro masivamente conceptos "
                f"del presupuesto {document.file_name}"
            ),
            metadata={
                "modelo_id": house_model_id,
                "documento_id": document.id,
                "partidas_integradas": len(pending_activities),
                "conceptos_creados": created,
                "conceptos_vinculados": linked,
            },
        )
    _recalculate_document_totals(db, document.id)
    db.commit()
    return db.scalar(
        select(HouseModelDocument)
        .where(HouseModelDocument.id == document.id)
        .options(
            selectinload(HouseModelDocument.material_requirements),
            selectinload(HouseModelDocument.budget_activities),
        )
    )


@router.patch("/{house_model_id}", response_model=HouseModelRead)
def update_house_model(
    house_model_id: int,
    payload: HouseModelUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("house_models", "edit")),
) -> HouseModel:
    item = get_or_404(db, HouseModel, house_model_id)
    ensure_same_company(current_user, item)
    data = payload.model_dump(exclude_unset=True, exclude={"company_id"})
    if "client_id" in data:
        _apply_client_company(db, current_user, data, fallback_company_id=item.company_id)
        mismatched_project = db.scalar(
            select(Project)
            .join(ProjectHouseModel, ProjectHouseModel.project_id == Project.id)
            .where(
                ProjectHouseModel.house_model_id == house_model_id,
                Project.client_id != data["client_id"],
            )
            .limit(1)
        )
        if mismatched_project is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "No se puede cambiar la desarrolladora porque el modelo "
                    "ya esta asignado a un proyecto de otra desarrolladora"
                ),
            )
    before = snapshot(item, list(data.keys()))
    for field, value in data.items():
        setattr(item, field, value)
    record_update(db, current_user, module="modelos", item=item, before=before)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{house_model_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_house_model(
    house_model_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("house_models", "delete")),
) -> None:
    item = get_or_404(db, HouseModel, house_model_id)
    ensure_same_company(current_user, item)
    ensure_house_model_has_no_approved_quote(db, house_model_id)
    record_delete(db, current_user, module="modelos", item=item)
    db.delete(item)
    db.commit()


@router.post(
    "/{house_model_id}/concepts",
    response_model=HouseModelConceptRead,
    status_code=status.HTTP_201_CREATED,
)
def add_concept_to_house_model(
    house_model_id: int,
    payload: HouseModelConceptCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("house_models", "edit")),
) -> HouseModelConcept:
    model = get_or_404(db, HouseModel, house_model_id)
    ensure_same_company(current_user, model)
    concept = get_or_404(db, ConstructionConcept, payload.construction_concept_id)
    ensure_same_company(current_user, concept)
    concept = HouseModelConcept(house_model_id=house_model_id, **payload.model_dump())
    db.add(concept)
    db.commit()
    db.refresh(concept)
    return concept
