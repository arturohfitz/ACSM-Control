import hashlib
import re
import shutil
import subprocess
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import uuid4

from defusedxml import ElementTree

from app.core.config import settings


PDF_DANGEROUS_MARKERS = (b"/JavaScript", b"/JS", b"/Launch", b"/EmbeddedFile", b"/RichMedia")


class InvoiceDocumentError(ValueError):
    pass


@dataclass(frozen=True)
class ValidatedInvoiceFile:
    document_type: str
    original_file_name: str
    extension: str
    content_type: str
    content: bytes
    sha256: str
    validation_status: str
    validation_message: str
    parsed_data: dict[str, object] | None = None


def safe_filename(file_name: str | None, fallback: str) -> str:
    raw_name = Path(file_name or fallback).name.strip() or fallback
    safe_name = re.sub(r"[^A-Za-z0-9._ -]+", "_", raw_name).strip(" .")
    return safe_name[:180] or fallback


def normalize_tax_id(value: str | None) -> str | None:
    normalized = re.sub(r"[^A-Za-z0-9]", "", value or "").upper()
    return normalized or None


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _attribute(element, *names: str) -> str | None:
    lowered = {key.lower(): value for key, value in element.attrib.items()}
    for name in names:
        value = lowered.get(name.lower())
        if value not in {None, ""}:
            return value
    return None


def _decimal_text(value: str | None) -> str | None:
    if value in {None, ""}:
        return None
    try:
        return str(Decimal(value).quantize(Decimal("0.01")))
    except (InvalidOperation, ValueError) as exc:
        raise InvoiceDocumentError("El XML contiene importes fiscales no validos") from exc


def parse_cfdi_xml(content: bytes) -> dict[str, object]:
    try:
        root = ElementTree.fromstring(content)
    except Exception as exc:
        raise InvoiceDocumentError("El archivo XML no es valido o contiene estructuras no permitidas") from exc
    if _local_name(root.tag).lower() != "comprobante":
        raise InvoiceDocumentError("El XML no corresponde a un comprobante CFDI")

    parsed: dict[str, object] = {}
    concepts: list[dict[str, str]] = []
    root_fields = {
        "version": ("Version",),
        "series": ("Serie",),
        "folio": ("Folio",),
        "issue_datetime": ("Fecha",),
        "subtotal": ("SubTotal",),
        "discount": ("Descuento",),
        "currency": ("Moneda",),
        "exchange_rate": ("TipoCambio",),
        "total": ("Total",),
        "payment_method": ("MetodoPago",),
        "payment_form": ("FormaPago",),
    }
    for key, aliases in root_fields.items():
        value = _attribute(root, *aliases)
        if value is not None:
            parsed[key] = value

    for element in root.iter():
        local = _local_name(element.tag).lower()
        if local == "emisor":
            tax_id = normalize_tax_id(_attribute(element, "Rfc"))
            if tax_id:
                parsed["issuer_tax_id"] = tax_id
            name = _attribute(element, "Nombre")
            if name:
                parsed["issuer_name"] = name
        elif local == "receptor":
            tax_id = normalize_tax_id(_attribute(element, "Rfc"))
            if tax_id:
                parsed["receiver_tax_id"] = tax_id
            name = _attribute(element, "Nombre")
            if name:
                parsed["receiver_name"] = name
        elif local == "timbrefiscaldigital":
            fiscal_uuid = _attribute(element, "UUID")
            if fiscal_uuid:
                parsed["fiscal_uuid"] = fiscal_uuid.upper()
        elif local == "concepto":
            concept = {
                "description": _attribute(element, "Descripcion") or "",
                "product_code": _attribute(element, "ClaveProdServ") or "",
                "identification_number": _attribute(element, "NoIdentificacion") or "",
                "unit_code": _attribute(element, "ClaveUnidad") or "",
                "unit": _attribute(element, "Unidad") or _attribute(element, "ClaveUnidad") or "",
                "quantity": _attribute(element, "Cantidad") or "0",
                "unit_price": _attribute(element, "ValorUnitario") or "0",
                "line_total": _attribute(element, "Importe") or "0",
                "discount": _attribute(element, "Descuento") or "0",
            }
            for key in ("quantity", "unit_price", "line_total", "discount"):
                try:
                    concept[key] = str(Decimal(concept[key]))
                except (InvalidOperation, ValueError) as exc:
                    raise InvoiceDocumentError(
                        f"El concepto CFDI contiene un numero invalido: {key}"
                    ) from exc
            concepts.append(concept)
        elif local == "impuestos":
            transferred = _attribute(element, "TotalImpuestosTrasladados")
            withheld = _attribute(element, "TotalImpuestosRetenidos")
            if transferred is not None:
                parsed["transferred_taxes"] = transferred
            if withheld is not None:
                parsed["withheld_taxes"] = withheld

    for monetary in ("subtotal", "discount", "total", "transferred_taxes", "withheld_taxes"):
        value = parsed.get(monetary)
        normalized = _decimal_text(str(value) if value is not None else None)
        if normalized is not None:
            parsed[monetary] = normalized
    parsed["concepts"] = concepts
    if "fiscal_uuid" not in parsed:
        raise InvoiceDocumentError("El XML CFDI no contiene un UUID fiscal timbrado")
    for required in ("issuer_tax_id", "receiver_tax_id", "total"):
        if required not in parsed:
            raise InvoiceDocumentError(f"El XML CFDI no contiene el dato requerido: {required}")
    return parsed


def validate_invoice_file(
    *,
    file_name: str | None,
    content_type: str | None,
    content: bytes,
    expected_type: str,
) -> ValidatedInvoiceFile:
    if expected_type not in {"pdf", "xml"}:
        raise InvoiceDocumentError("Tipo de documento de factura no permitido")
    max_mb = (
        settings.supplier_invoice_pdf_max_mb
        if expected_type == "pdf"
        else settings.supplier_invoice_xml_max_mb
    )
    if not content:
        raise InvoiceDocumentError("El archivo esta vacio")
    if len(content) > max_mb * 1024 * 1024:
        raise InvoiceDocumentError(f"El archivo supera el limite de {max_mb} MB")

    extension = Path(file_name or "").suffix.lower()
    expected_extension = f".{expected_type}"
    if extension != expected_extension:
        raise InvoiceDocumentError(f"El archivo debe tener extension {expected_extension.upper()}")
    original_name = safe_filename(file_name, f"factura{expected_extension}")
    parsed_data: dict[str, object] | None = None
    if expected_type == "pdf":
        if not content.startswith(b"%PDF-"):
            raise InvoiceDocumentError("El archivo no parece ser un PDF valido")
        lowered = content[: min(len(content), 2_000_000)].lower()
        if any(marker.lower() in lowered for marker in PDF_DANGEROUS_MARKERS):
            raise InvoiceDocumentError("El PDF contiene elementos activos o embebidos no permitidos")
        message = "PDF validado por firma y sin elementos activos comunes"
    else:
        parsed_data = parse_cfdi_xml(content)
        message = "XML CFDI estructuralmente valido y con timbre fiscal"

    return ValidatedInvoiceFile(
        document_type=expected_type,
        original_file_name=original_name,
        extension=expected_extension,
        # Do not persist a client-provided MIME type; downloads must use the
        # canonical type established by signature/structure validation.
        content_type="application/pdf" if expected_type == "pdf" else "application/xml",
        content=content,
        sha256=hashlib.sha256(content).hexdigest(),
        validation_status="valid",
        validation_message=message,
        parsed_data=parsed_data,
    )


def invoice_upload_base_dir() -> Path:
    base_dir = Path(settings.supplier_invoice_upload_dir)
    if not base_dir.is_absolute():
        base_dir = Path.cwd() / base_dir
    base_dir.mkdir(parents=True, exist_ok=True)
    base_dir.chmod(0o700)
    return base_dir


def store_invoice_file(validated: ValidatedInvoiceFile, *, company_id: int, invoice_id: int) -> Path:
    upload_dir = invoice_upload_base_dir() / str(company_id) / str(invoice_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    upload_dir.chmod(0o700)
    stored_path = upload_dir / f"{uuid4().hex}{validated.extension}"
    stored_path.write_bytes(validated.content)
    stored_path.chmod(0o600)
    try:
        scan_with_clamav_if_available(stored_path)
    except Exception:
        stored_path.unlink(missing_ok=True)
        raise
    return stored_path


def scan_with_clamav_if_available(path: Path) -> None:
    scanner = shutil.which("clamscan")
    if scanner is None:
        return
    try:
        result = subprocess.run(
            [scanner, "--no-summary", "--infected", str(path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except subprocess.TimeoutExpired as exc:
        raise InvoiceDocumentError("No fue posible validar el archivo con antivirus") from exc
    if result.returncode == 1:
        raise InvoiceDocumentError("El antivirus detecto contenido malicioso en el archivo")
    if result.returncode not in {0, 1}:
        raise InvoiceDocumentError("El antivirus no pudo completar la revision del archivo")
