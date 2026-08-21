import hashlib
import re
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models import (
    PurchaseOrder,
    SupplierInvoice,
    SupplierInvoiceItem,
    SupplierInvoiceSubmission,
    SupplierInvoiceSubmissionDocument,
)
from app.services.audit import record_external_event
from app.services.invoice_documents import (
    InvoiceDocumentError,
    ValidatedInvoiceFile,
    store_invoice_submission_file,
    validate_invoice_file,
)
from app.services.notifications import notify_permission


router = APIRouter()
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{32,256}$")
ACTIVE_INVOICE_STATUSES = {
    "document_pending",
    "fiscal_review",
    "received",
    "blocked",
    "approved_for_payment",
    "scheduled",
    "paid",
}


class PortalDocumentRead(BaseModel):
    id: int
    document_type: str
    original_file_name: str
    file_size: int


class PortalSubmissionRead(BaseModel):
    id: int
    invoice_number: str | None
    submitted_at: datetime
    status: str
    total: Decimal | None
    validation_message: str | None
    documents: list[PortalDocumentRead]


class PortalItemRead(BaseModel):
    id: int
    description: str
    unit: str
    ordered: Decimal
    received: Decimal
    invoiced: Decimal
    available: Decimal
    unit_price: Decimal


class PortalOrderRead(BaseModel):
    purchase_order_id: int
    po_number: str
    status: str
    supplier_name: str
    project_name: str
    issued_at: date
    subtotal: Decimal
    currency: str = "MXN"
    items: list[PortalItemRead]
    submissions: list[PortalSubmissionRead]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _token_hash(token: str) -> str:
    if not TOKEN_RE.fullmatch(token):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Liga no valida")
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _load_order(db: Session, token: str) -> PurchaseOrder:
    order = db.scalar(
        select(PurchaseOrder)
        .where(PurchaseOrder.invoice_portal_token_hash == _token_hash(token))
        .options(
            selectinload(PurchaseOrder.project),
            selectinload(PurchaseOrder.supplier),
            selectinload(PurchaseOrder.items),
            selectinload(PurchaseOrder.invoice_submissions).selectinload(
                SupplierInvoiceSubmission.documents
            ),
        )
    )
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Liga no valida")
    expires_at = order.invoice_portal_token_expires_at
    if expires_at is None or expires_at < _now():
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="La liga ha expirado")
    if order.status in {"cancelled", "closed"}:
        detail = "La orden fue cancelada" if order.status == "cancelled" else "La orden ya fue cerrada"
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=detail)
    order.invoice_portal_last_accessed_at = _now()
    return order


def _invoiced_by_item(db: Session, order: PurchaseOrder) -> dict[int, Decimal]:
    rows = db.execute(
        select(SupplierInvoiceItem.purchase_order_item_id, SupplierInvoiceItem.quantity)
        .join(SupplierInvoice, SupplierInvoice.id == SupplierInvoiceItem.supplier_invoice_id)
        .where(
            SupplierInvoiceItem.purchase_order_item_id.in_([item.id for item in order.items]),
            SupplierInvoice.status.in_(ACTIVE_INVOICE_STATUSES),
        )
    ).all()
    totals: dict[int, Decimal] = {}
    for item_id, quantity in rows:
        totals[item_id] = totals.get(item_id, Decimal("0")) + Decimal(quantity)
    return totals


def _read_order(db: Session, order: PurchaseOrder) -> PortalOrderRead:
    invoiced = _invoiced_by_item(db, order)
    items = []
    for item in order.items:
        billed = invoiced.get(item.id, Decimal("0"))
        available = max(min(item.received_quantity, item.quantity_ordered) - billed, Decimal("0"))
        items.append(
            PortalItemRead(
                id=item.id,
                description=item.description,
                unit=item.unit,
                ordered=item.quantity_ordered,
                received=item.received_quantity,
                invoiced=billed,
                available=available,
                unit_price=item.unit_price,
            )
        )
    submissions = [
        PortalSubmissionRead(
            id=submission.id,
            invoice_number=submission.invoice_number,
            submitted_at=submission.submitted_at,
            status=submission.status,
            total=submission.total,
            validation_message=submission.validation_message,
            documents=[
                PortalDocumentRead(
                    id=document.id,
                    document_type=document.document_type,
                    original_file_name=document.original_file_name,
                    file_size=document.file_size,
                )
                for document in submission.documents
            ],
        )
        for submission in sorted(
            order.invoice_submissions,
            key=lambda row: row.submitted_at,
            reverse=True,
        )
    ]
    return PortalOrderRead(
        purchase_order_id=order.id,
        po_number=order.po_number,
        status=order.status,
        supplier_name=order.supplier.name,
        project_name=order.project.name,
        issued_at=order.issued_at,
        subtotal=order.subtotal,
        items=items,
        submissions=submissions,
    )


async def _validated(file: UploadFile, document_type: str) -> ValidatedInvoiceFile:
    content = await file.read(16 * 1024 * 1024)
    try:
        return validate_invoice_file(
            file_name=file.filename,
            content_type=file.content_type,
            content=content,
            expected_type=document_type,
        )
    except InvoiceDocumentError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{token}", response_model=PortalOrderRead)
def get_invoice_portal(token: str, db: Session = Depends(get_db)) -> PortalOrderRead:
    order = _load_order(db, token)
    result = _read_order(db, order)
    db.commit()
    return result


@router.post("/{token}/submissions", response_model=PortalSubmissionRead, status_code=201)
async def submit_invoice(
    token: str,
    invoice_number: str | None = Form(default=None),
    invoice_date: date | None = Form(default=None),
    currency: str = Form(default="MXN"),
    subtotal: Decimal | None = Form(default=None),
    total: Decimal | None = Form(default=None),
    notes: str | None = Form(default=None),
    pdf_file: UploadFile | None = File(default=None),
    xml_file: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
) -> PortalSubmissionRead:
    if pdf_file is None and xml_file is None:
        raise HTTPException(status_code=400, detail="Adjunta al menos el PDF o XML de la factura")
    order = _load_order(db, token)
    portal_order = _read_order(db, order)
    if not any(item.available > 0 for item in portal_order.items):
        raise HTTPException(
            status_code=400,
            detail="La orden no tiene material recibido pendiente de facturar.",
        )
    validated_pdf = await _validated(pdf_file, "pdf") if pdf_file else None
    validated_xml = await _validated(xml_file, "xml") if xml_file else None
    parsed = (validated_xml.parsed_data if validated_xml else None) or {}
    issue_text = str(parsed.get("issue_datetime") or "")[:10]
    try:
        parsed_date = date.fromisoformat(issue_text) if issue_text else None
    except ValueError:
        parsed_date = None
    normalized_invoice_number = str(parsed.get("folio") or invoice_number or "").strip() or None
    fiscal_uuid = str(parsed.get("fiscal_uuid") or "").strip().upper() or None
    if fiscal_uuid:
        existing_invoice = db.scalar(
            select(SupplierInvoice.id).where(
                SupplierInvoice.company_id == order.company_id,
                SupplierInvoice.fiscal_uuid == fiscal_uuid,
                SupplierInvoice.status.notin_(("rejected", "cancelled")),
            )
        )
        existing_submission = db.scalar(
            select(SupplierInvoiceSubmission.id).where(
                SupplierInvoiceSubmission.company_id == order.company_id,
                SupplierInvoiceSubmission.fiscal_uuid == fiscal_uuid,
                SupplierInvoiceSubmission.status.in_(("review_required", "registered")),
            )
        )
        if existing_invoice or existing_submission:
            raise HTTPException(status_code=409, detail="El UUID fiscal ya fue recibido.")
    if normalized_invoice_number:
        existing_invoice = db.scalar(
            select(SupplierInvoice.id).where(
                SupplierInvoice.company_id == order.company_id,
                SupplierInvoice.supplier_id == order.supplier_id,
                SupplierInvoice.invoice_number == normalized_invoice_number,
                SupplierInvoice.status.notin_(("rejected", "cancelled")),
            )
        )
        existing_submission = db.scalar(
            select(SupplierInvoiceSubmission.id).where(
                SupplierInvoiceSubmission.company_id == order.company_id,
                SupplierInvoiceSubmission.supplier_id == order.supplier_id,
                SupplierInvoiceSubmission.invoice_number == normalized_invoice_number,
                SupplierInvoiceSubmission.status.in_(("review_required", "registered")),
            )
        )
        if existing_invoice or existing_submission:
            raise HTTPException(
                status_code=409,
                detail="Ese folio de factura ya fue recibido para el proveedor.",
            )
    hashes = [item.sha256 for item in (validated_pdf, validated_xml) if item is not None]
    if hashes:
        duplicate_document = db.scalar(
            select(SupplierInvoiceSubmissionDocument.id)
            .join(
                SupplierInvoiceSubmission,
                SupplierInvoiceSubmission.id
                == SupplierInvoiceSubmissionDocument.submission_id,
            )
            .where(
                SupplierInvoiceSubmission.purchase_order_id == order.id,
                SupplierInvoiceSubmission.status.in_(("review_required", "registered")),
                SupplierInvoiceSubmissionDocument.sha256.in_(hashes),
            )
        )
        if duplicate_document:
            raise HTTPException(
                status_code=409,
                detail="El mismo archivo ya fue recibido para esta orden de compra.",
            )
    submission = SupplierInvoiceSubmission(
        company_id=order.company_id,
        purchase_order_id=order.id,
        supplier_id=order.supplier_id,
        invoice_number=normalized_invoice_number,
        invoice_date=parsed_date or invoice_date,
        currency=str(parsed.get("currency") or currency).upper(),
        subtotal=Decimal(str(parsed["subtotal"])) if parsed.get("subtotal") else subtotal,
        total=Decimal(str(parsed["total"])) if parsed.get("total") else total,
        fiscal_uuid=fiscal_uuid,
        notes=notes,
        status="review_required",
        validation_message="Documento recibido; Compras debe revisar y registrar la factura.",
        parsed_data=parsed or None,
        submitted_at=_now(),
    )
    db.add(submission)
    db.flush()
    stored_paths: list[Path] = []
    try:
        for validated in (validated_pdf, validated_xml):
            if validated is None:
                continue
            path = store_invoice_submission_file(
                validated,
                company_id=order.company_id,
                submission_id=submission.id,
            )
            stored_paths.append(path)
            db.add(
                SupplierInvoiceSubmissionDocument(
                    submission_id=submission.id,
                    document_type=validated.document_type,
                    original_file_name=validated.original_file_name,
                    stored_file_name=path.name,
                    storage_path=str(path),
                    content_type=validated.content_type,
                    extension=validated.extension,
                    file_size=len(validated.content),
                    sha256=validated.sha256,
                    validation_status=validated.validation_status,
                    validation_message=validated.validation_message,
                    parsed_data=validated.parsed_data,
                    uploaded_at=_now(),
                )
            )
        notify_permission(
            db,
            company_id=order.company_id,
            module="supplier_invoices",
            action="upload",
            notification_type="supplier_invoice_received",
            title="Factura recibida del proveedor",
            body=f"{order.supplier.name} cargo documentos para {order.po_number}.",
            category="task",
            priority="high",
            source_module="pagos_proveedores",
            entity_type="SupplierInvoiceSubmission",
            entity_id=submission.id,
            entity_label=submission.invoice_number or order.po_number,
            action_url=(
                f"/supplier-payments?view=invoices&project_id={order.project_id}"
                f"&purchase_order_id={order.id}&submission_id={submission.id}"
                "&focus=invoice-submissions"
            ),
            project_id=order.project_id,
            metadata={"purchase_order_id": order.id, "submission_id": submission.id},
        )
        record_external_event(
            db,
            module="pagos_proveedores",
            action="upload",
            entity_type="SupplierInvoiceSubmission",
            entity_id=submission.id,
            company_id=order.company_id,
            actor_name=order.supplier.name,
            actor_email=order.supplier.contact_email,
            label=submission.invoice_number or order.po_number,
            description=(
                f"{order.supplier.name} cargo documentos de factura para {order.po_number}"
            ),
            metadata={
                "purchase_order_id": order.id,
                "supplier_id": order.supplier_id,
                "document_types": [
                    item.document_type
                    for item in (validated_pdf, validated_xml)
                    if item is not None
                ],
                "source": "supplier_invoice_portal",
            },
        )
        db.commit()
    except Exception:
        db.rollback()
        for path in stored_paths:
            path.unlink(missing_ok=True)
        raise
    submission = db.scalar(
        select(SupplierInvoiceSubmission)
        .where(SupplierInvoiceSubmission.id == submission.id)
        .options(selectinload(SupplierInvoiceSubmission.documents))
    )
    if submission is None:
        raise HTTPException(status_code=404, detail="No fue posible recuperar la entrega")
    return PortalSubmissionRead(
        id=submission.id,
        invoice_number=submission.invoice_number,
        submitted_at=submission.submitted_at,
        status=submission.status,
        total=submission.total,
        validation_message=submission.validation_message,
        documents=[
            PortalDocumentRead(
                id=document.id,
                document_type=document.document_type,
                original_file_name=document.original_file_name,
                file_size=document.file_size,
            )
            for document in submission.documents
        ],
    )
