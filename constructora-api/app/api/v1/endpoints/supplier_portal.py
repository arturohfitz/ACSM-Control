import hashlib
import json
import re
import shutil
import subprocess
import uuid
import zipfile
from datetime import datetime, timezone
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.session import get_db
from app.models import SupplierQuoteUpload, SupplierRFQ, SupplierRFQSupplier
from app.schemas.purchasing import SupplierPortalRFQRead, SupplierQuoteDraftInput, SupplierQuoteUploadRead
from app.services.notifications import notify_permission
from app.services.supplier_quote_drafts import (
    build_quote_template,
    create_quote_draft,
    parse_quote_template,
)
from app.services.supplier_quote_pdf import (
    PARSER_VERSION as PDF_PARSER_VERSION,
    SupplierQuotePDFError,
    SupplierQuotePDFMismatchError,
    SupplierQuotePDFRequiresOCRError,
    parse_supplier_quote_pdf,
)


router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".xlsx", ".xls"}
PDF_DANGEROUS_MARKERS = (b"/JavaScript", b"/JS", b"<script", b"/Launch", b"/EmbeddedFile")
OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
ZIP_MAGICS = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{32,256}$")
ZIP_DANGEROUS_PARTS = (
    "vbaproject.bin",
    "activex/",
    "embeddings/",
    "externalLinks/".lower(),
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _token_hash(token: str) -> str:
    if not TOKEN_RE.fullmatch(token):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Liga no valida")
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _safe_filename(file_name: str | None) -> str:
    raw_name = Path(file_name or "cotizacion").name.strip() or "cotizacion"
    safe_name = re.sub(r"[^A-Za-z0-9._ -]+", "_", raw_name).strip(" .")
    return safe_name[:180] or "cotizacion"


def _upload_base_dir() -> Path:
    base_dir = Path(settings.supplier_quote_upload_dir)
    if not base_dir.is_absolute():
        base_dir = Path.cwd() / base_dir
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


def _validate_file(file_name: str, content: bytes) -> tuple[str, str | None]:
    extension = Path(file_name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato no permitido. Solo se aceptan PDF, XLSX o XLS.",
        )
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El archivo esta vacio")

    header = content[:8]
    lowered = content[: min(len(content), 2_000_000)].lower()
    security_notes: list[str] = []
    if extension == ".pdf":
        if not content.startswith(b"%PDF-"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El archivo no parece ser un PDF valido")
        if any(marker.lower() in lowered for marker in PDF_DANGEROUS_MARKERS):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El PDF contiene elementos activos o embebidos no permitidos",
            )
        return extension, "PDF validado por firma y sin elementos activos comunes"

    if extension == ".xlsx":
        if not any(header.startswith(magic) for magic in ZIP_MAGICS):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El archivo no parece ser un XLSX valido")
        try:
            with zipfile.ZipFile(BytesIO(content)) as archive:
                names = [name.lower() for name in archive.namelist()]
                total_uncompressed = sum(item.file_size for item in archive.infolist())
        except zipfile.BadZipFile as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El XLSX no es valido") from exc
        if total_uncompressed > settings.supplier_quote_upload_max_mb * 1024 * 1024 * 4:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El XLSX esta comprimido de forma insegura",
            )
        if any(any(danger in name for danger in ZIP_DANGEROUS_PARTS) for name in names):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se aceptan archivos Excel con macros, objetos embebidos o vinculos externos",
            )
        return extension, "XLSX validado sin macros ni vinculos externos"

    if extension == ".xls":
        if header != OLE_MAGIC:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El archivo no parece ser un XLS valido")
        if b"vba" in lowered or b"macros" in lowered:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se aceptan archivos con macros")
        return extension, "XLS validado por firma OLE"

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Formato no permitido")


def _scan_with_clamav_if_available(path: Path) -> str | None:
    scanner = shutil.which("clamscan")
    if scanner is None:
        return None
    try:
        result = subprocess.run(
            [scanner, "--no-summary", "--infected", str(path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fue posible validar el archivo con antivirus",
        ) from exc
    if result.returncode == 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El antivirus detecto contenido malicioso en el archivo",
        )
    if result.returncode not in {0, 1}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fue posible validar el archivo con antivirus",
        )
    return "Antivirus local ejecutado sin detecciones"


def _link_from_token(db: Session, token: str) -> SupplierRFQSupplier:
    link = db.scalar(
        select(SupplierRFQSupplier)
        .where(SupplierRFQSupplier.portal_token_hash == _token_hash(token))
        .options(
            selectinload(SupplierRFQSupplier.supplier),
            selectinload(SupplierRFQSupplier.quote_uploads).selectinload(SupplierQuoteUpload.supplier),
            selectinload(SupplierRFQSupplier.rfq).selectinload(SupplierRFQ.items),
        )
    )
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Liga no valida")
    if link.portal_token_expires_at and link.portal_token_expires_at < _now():
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="La liga expiro")
    return link


@router.get("/quotes/{token}", response_model=SupplierPortalRFQRead)
def get_supplier_quote_request(
    token: str,
    db: Session = Depends(get_db),
) -> SupplierPortalRFQRead:
    link = _link_from_token(db, token)
    link.portal_last_accessed_at = _now()
    db.commit()
    return SupplierPortalRFQRead(
        rfq_number=link.rfq.rfq_number,
        title=link.rfq.title,
        required_by=link.rfq.required_by,
        response_deadline=link.rfq.response_deadline,
        supplier_name=link.supplier.name if link.supplier else "Proveedor",
        items=link.rfq.items,
        previous_uploads=link.quote_uploads,
    )


@router.get("/quotes/{token}/template")
def download_supplier_quote_template(
    token: str,
    db: Session = Depends(get_db),
) -> Response:
    link = _link_from_token(db, token)
    content = build_quote_template(link)
    filename = f"Cotizacion-{link.rfq.rfq_number}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/quotes/{token}/uploads", response_model=SupplierQuoteUploadRead, status_code=status.HTTP_201_CREATED)
async def upload_supplier_quote_document(
    token: str,
    quote_number: str | None = Form(default=None),
    notes: str | None = Form(default=None),
    quote_payload: str | None = Form(default=None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> SupplierQuoteUpload:
    link = _link_from_token(db, token)
    if link.quote_uploads:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Esta cotizacion ya fue cargada. Solicita a ACSM habilitar una actualizacion "
                "si necesitas reemplazar el archivo."
            ),
        )
    if link.rfq.status in {"awarded", "cancelled"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La solicitud ya no recibe cotizaciones")

    max_bytes = settings.supplier_quote_upload_max_mb * 1024 * 1024
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"El archivo supera {settings.supplier_quote_upload_max_mb} MB",
        )

    safe_name = _safe_filename(file.filename)
    extension, security_note = _validate_file(safe_name, content)
    file_hash = hashlib.sha256(content).hexdigest()

    upload_dir = _upload_base_dir() / str(link.rfq.company_id) / link.rfq.rfq_number
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_file_name = f"{uuid.uuid4().hex}{extension}"
    stored_path = upload_dir / stored_file_name
    stored_path.write_bytes(content)
    try:
        scan_note = _scan_with_clamav_if_available(stored_path)
        security_notes = "; ".join(note for note in (security_note, scan_note) if note) or None
        upload = SupplierQuoteUpload(
            company_id=link.rfq.company_id,
            rfq_id=link.rfq_id,
            rfq_supplier_id=link.id,
            supplier_id=link.supplier_id,
            quote_number=(quote_number or "").strip() or None,
            original_file_name=safe_name,
            stored_file_name=stored_file_name,
            stored_file_path=str(stored_path),
            content_type=file.content_type,
            file_extension=extension,
            file_size_bytes=len(content),
            file_sha256=file_hash,
            uploaded_at=_now(),
            notes=(notes or "").strip() or None,
            security_notes=security_notes,
        )
        db.add(upload)
        db.flush()

        draft = None
        draft_payload = None
        draft_source = "portal"
        draft_confidence = Decimal("1")
        draft_analysis = None
        processing_note = None
        if quote_payload:
            try:
                draft_payload = SupplierQuoteDraftInput.model_validate(json.loads(quote_payload))
            except (json.JSONDecodeError, ValidationError) as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Los datos estructurados de la cotizacion no son validos: {exc}",
                ) from exc
        elif extension == ".xlsx":
            try:
                draft_payload = parse_quote_template(content, link)
                draft_source = "xlsx_template"
            except (ValueError, ValidationError):
                upload.status = "manual_capture_required"
                processing_note = "La plantilla Excel no pudo interpretarse; requiere captura manual."
        elif extension == ".pdf":
            try:
                draft_analysis = parse_supplier_quote_pdf(content, safe_name, link)
                draft_payload = draft_analysis.payload
                draft_source = "pdf_text"
                draft_confidence = draft_analysis.confidence
            except SupplierQuotePDFRequiresOCRError as exc:
                upload.status = "requires_ocr"
                processing_note = str(exc)
            except SupplierQuotePDFMismatchError as exc:
                upload.status = "rfq_mismatch"
                processing_note = str(exc)
            except SupplierQuotePDFError as exc:
                upload.status = "manual_capture_required"
                processing_note = str(exc)

        if draft_payload is not None:
            upload.quote_number = draft_payload.quote_number
            draft = create_quote_draft(
                db,
                link=link,
                upload=upload,
                payload=draft_payload,
                source_type=draft_source,
                confidence=draft_confidence,
                parser_version=PDF_PARSER_VERSION if draft_analysis else "structured-v1",
                initial_errors=draft_analysis.validation_errors if draft_analysis else None,
                item_metadata=draft_analysis.item_metadata if draft_analysis else None,
                detected_supplier_name=(
                    draft_analysis.detected_supplier_name if draft_analysis else None
                ),
                detected_supplier_tax_id=(
                    draft_analysis.detected_supplier_tax_id if draft_analysis else None
                ),
                detected_supplier_email=(
                    draft_analysis.detected_supplier_email if draft_analysis else None
                ),
                supplier_match_status=(
                    draft_analysis.supplier_match_status if draft_analysis else "not_detected"
                ),
                supplier_match_confidence=(
                    draft_analysis.supplier_match_confidence
                    if draft_analysis
                    else Decimal("0")
                ),
                detected_rfq_number=(
                    draft_analysis.detected_rfq_number if draft_analysis else None
                ),
                document_subtotal=(
                    draft_analysis.document_subtotal if draft_analysis else None
                ),
                document_tax_amount=(
                    draft_analysis.document_tax_amount if draft_analysis else None
                ),
                document_total=draft_analysis.document_total if draft_analysis else None,
                extraction_metadata=(
                    draft_analysis.extraction_metadata if draft_analysis else None
                ),
            )
        if processing_note:
            upload.security_notes = "; ".join(
                note for note in (upload.security_notes, processing_note) if note
            )

        link.status = "responded"
        if link.rfq.status == "sent":
            link.rfq.status = "partially_quoted"
        notify_permission(
            db,
            company_id=link.rfq.company_id,
            module="supplier_quotes",
            action="create",
            notification_type="supplier_quote_document_uploaded",
            title=(
                "Cotizacion con identidad por validar"
                if draft and draft.supplier_match_status == "mismatch"
                else "Cotizacion lista para revisar"
                if draft
                else "Cotizacion cargada por proveedor"
            ),
            body=(
                (
                    f"El PDF indica {draft.detected_supplier_name}, pero el enlace pertenece a "
                    f"{link.supplier.name}. Compras debe validar la identidad."
                    if draft and draft.supplier_match_status == "mismatch"
                    else (
                        f"{link.supplier.name if link.supplier else 'Proveedor'} envio datos "
                        f"interpretados para {link.rfq.rfq_number}; requieren revision."
                    )
                )
                if draft
                else (
                    f"{link.supplier.name if link.supplier else 'Proveedor'} cargo un archivo "
                    f"para {link.rfq.rfq_number}; {processing_note or 'requiere captura manual'}"
                )
            ),
            category=(
                "warning"
                if (draft and draft.supplier_match_status == "mismatch") or processing_note
                else "info"
            ),
            priority=(
                "high" if draft and draft.supplier_match_status == "mismatch" else "normal"
            ),
            source_module="compras",
            entity_type="SupplierQuoteUpload",
            entity_id=upload.id,
            entity_label=link.rfq.rfq_number,
            action_url=(
                f"/purchasing/operations?rfq_id={link.rfq_id}"
                f"&focus=quote-review&draft_id={draft.id}"
                if draft
                else f"/purchasing/operations?rfq_id={link.rfq_id}&focus=uploads"
            ),
            project_id=link.rfq.project_id,
            metadata={
                "rfq_id": link.rfq_id,
                "supplier_id": link.supplier_id,
                "draft_id": draft.id if draft else None,
                "structured": draft is not None,
                "supplier_match_status": (
                    draft.supplier_match_status if draft else None
                ),
                "processing_note": processing_note,
            },
        )
        db.commit()
        db.refresh(upload)
        return upload
    except Exception:
        stored_path.unlink(missing_ok=True)
        raise


@router.post("/quotes/{token}/request-update", status_code=status.HTTP_202_ACCEPTED)
def request_supplier_quote_update(
    token: str,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    link = _link_from_token(db, token)
    if not link.quote_uploads:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aun no existe una cotizacion cargada para solicitar actualizacion",
        )
    if link.rfq.status in {"awarded", "cancelled"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La solicitud ya no recibe actualizaciones")

    notify_permission(
        db,
        company_id=link.rfq.company_id,
        module="supplier_quotes",
        action="approve",
        notification_type="supplier_quote_update_requested",
        title="Proveedor solicita actualizar cotizacion",
        body=(
            f"{link.supplier.name if link.supplier else 'Proveedor'} solicita reemplazar la cotizacion "
            f"cargada para {link.rfq.rfq_number}."
        ),
        category="warning",
        priority="high",
        source_module="compras",
        entity_type="SupplierRFQSupplier",
        entity_id=link.id,
        entity_label=link.rfq.rfq_number,
        action_url=f"/purchasing?rfq_id={link.rfq_id}&focus=uploads",
        project_id=link.rfq.project_id,
        metadata={
            "rfq_id": link.rfq_id,
            "supplier_id": link.supplier_id,
            "uploads": len(link.quote_uploads),
        },
    )
    db.commit()
    return {"message": "Solicitud de actualizacion enviada a ACSM."}
