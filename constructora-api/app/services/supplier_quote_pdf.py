from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import unicodedata
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from pathlib import Path

from app.models import SupplierRFQSupplier
from app.schemas.purchasing import SupplierQuoteDraftInput
from app.services.pdf_text import PDFTextEmptyError, extract_pdf_text


PARSER_VERSION = "pdf-text-v1"
MONEY_TOLERANCE = Decimal("0.03")
QUANTITY_TOLERANCE = Decimal("0.001")
RFQ_PATTERN = re.compile(r"\bSC-[A-Z0-9]+(?:-[A-Z0-9]+)+\b", re.IGNORECASE)
EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
RFC_PATTERN = re.compile(r"\b[A-Z&Ñ]{3,4}\d{6}[A-Z0-9]{3}\b", re.IGNORECASE)
ROW_PATTERN = re.compile(
    r"^(?P<description>.+?)\s+"
    r"(?P<unit>[A-Z0-9./\"'-]+)\s+"
    r"(?P<quantity>\d[\d,]*(?:\.\d+)?)\s+"
    r"\$\s*(?P<unit_price>\d[\d,]*(?:\.\d+)?)\s+"
    r"\$\s*(?P<line_total>\d[\d,]*(?:\.\d+)?)\s*$",
    re.IGNORECASE,
)


class SupplierQuotePDFError(ValueError):
    pass


class SupplierQuotePDFRequiresOCRError(SupplierQuotePDFError):
    pass


class SupplierQuotePDFMismatchError(SupplierQuotePDFError):
    pass


@dataclass(frozen=True)
class ExtractedQuoteRow:
    description: str
    unit: str
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal


@dataclass
class SupplierQuotePDFAnalysis:
    payload: SupplierQuoteDraftInput
    confidence: Decimal
    validation_errors: list[str] = field(default_factory=list)
    detected_supplier_name: str | None = None
    detected_supplier_tax_id: str | None = None
    detected_supplier_email: str | None = None
    supplier_match_status: str = "not_detected"
    supplier_match_confidence: Decimal = Decimal("0")
    detected_rfq_number: str | None = None
    document_subtotal: Decimal | None = None
    document_tax_amount: Decimal | None = None
    document_total: Decimal | None = None
    item_metadata: dict[int, tuple[Decimal, str]] = field(default_factory=dict)
    extraction_metadata: dict = field(default_factory=dict)


def _normalized(value: str | None) -> str:
    if not value:
        return ""
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(character for character in decomposed if not unicodedata.combining(character))
    return " ".join(re.sub(r"[^A-Z0-9]+", " ", ascii_value.upper()).split())


def _decimal(raw: str) -> Decimal:
    try:
        return Decimal(raw.replace(",", "").strip())
    except (InvalidOperation, ValueError) as exc:
        raise SupplierQuotePDFError(f"Numero invalido en la cotizacion: {raw}") from exc


def _money_from_label(text: str, label: str) -> Decimal | None:
    match = re.search(
        rf"\b{label}[^\d$-]*\$?\s*(-?\d[\d,]*(?:\.\d{{2}})?)",
        text,
        re.IGNORECASE,
    )
    return _decimal(match.group(1)) if match else None


def _date_from_text(text: str, label: str) -> date | None:
    match = re.search(rf"\b{label}\s*:\s*(\d{{1,2}}/\d{{1,2}}/\d{{4}})", text, re.IGNORECASE)
    if not match:
        return None
    day, month, year = (int(part) for part in match.group(1).split("/"))
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _extract_issuer_name(text: str) -> str | None:
    parts: list[str] = []
    for raw_line in text.splitlines()[:12]:
        line = raw_line.strip()
        if not line:
            continue
        line = re.split(
            r"\b(?:COTIZACION|Folio\s*:|Fecha\s*:|Moneda\s*:)",
            line,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]
        line = line.strip(" |-")
        if not line:
            continue
        if re.search(r"\b(?:proveedor|tel\.?|correo|email|www\.|calle|carr\.|col\.)\b", line, re.IGNORECASE):
            break
        if len(line) >= 4:
            parts.append(line)
        if len(parts) == 2:
            break
    return " ".join(parts)[:255] or None


def _extract_rows(text: str) -> list[ExtractedQuoteRow]:
    rows: list[ExtractedQuoteRow] = []
    for line in text.splitlines():
        match = ROW_PATTERN.match(line.strip())
        if not match:
            continue
        rows.append(
            ExtractedQuoteRow(
                description=match.group("description").strip(),
                unit=match.group("unit").strip().upper(),
                quantity=_decimal(match.group("quantity")),
                unit_price=_decimal(match.group("unit_price")),
                line_total=_decimal(match.group("line_total")),
            )
        )
    return rows


def _ocr_pdf(file_bytes: bytes, file_name: str) -> str:
    if shutil.which("pdftoppm") is None or shutil.which("tesseract") is None:
        raise SupplierQuotePDFRequiresOCRError(
            "El PDF es una imagen y requiere OCR; no se capturaron precios automaticamente"
        )
    with tempfile.TemporaryDirectory(prefix="acsm-quote-ocr-") as directory:
        pdf_path = Path(directory) / (Path(file_name).name or "cotizacion.pdf")
        image_prefix = Path(directory) / "page"
        pdf_path.write_bytes(file_bytes)
        try:
            subprocess.run(
                [
                    "pdftoppm",
                    "-png",
                    "-r",
                    "220",
                    "-f",
                    "1",
                    "-l",
                    "10",
                    str(pdf_path),
                    str(image_prefix),
                ],
                check=True,
                capture_output=True,
                timeout=45,
            )
        except (subprocess.SubprocessError, OSError) as exc:
            raise SupplierQuotePDFRequiresOCRError("No fue posible preparar el PDF para OCR") from exc
        page_text: list[str] = []
        for image_path in sorted(Path(directory).glob("page-*.png")):
            try:
                completed = subprocess.run(
                    ["tesseract", str(image_path), "stdout", "-l", "spa+eng", "--psm", "6"],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            except subprocess.CalledProcessError:
                completed = subprocess.run(
                    ["tesseract", str(image_path), "stdout", "-l", "eng", "--psm", "6"],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            page_text.append(completed.stdout)
    text = "\n".join(page_text).strip()
    if not text:
        raise SupplierQuotePDFRequiresOCRError("El OCR no encontro texto util en el PDF")
    return text


def extract_supplier_quote_text(file_bytes: bytes, file_name: str) -> tuple[str, str]:
    try:
        return extract_pdf_text(file_bytes, file_name), "native_text"
    except PDFTextEmptyError:
        return _ocr_pdf(file_bytes, file_name), "ocr"


def _supplier_identity(
    link: SupplierRFQSupplier,
    detected_name: str | None,
    detected_tax_id: str | None,
    detected_email: str | None,
) -> tuple[str, Decimal]:
    supplier = link.supplier
    expected_tax_id = _normalized(getattr(supplier, "tax_id", None))
    expected_email = (getattr(supplier, "contact_email", None) or "").strip().lower()
    expected_names = {
        value
        for value in (
            _normalized(getattr(supplier, "name", None)),
            _normalized(getattr(supplier, "legal_name", None)),
        )
        if value
    }
    if expected_tax_id and expected_tax_id == _normalized(detected_tax_id):
        return "matched", Decimal("1")
    if expected_email and detected_email and expected_email == detected_email.strip().lower():
        return "matched", Decimal("0.98")
    normalized_detected_name = _normalized(detected_name)
    if normalized_detected_name and any(
        expected in normalized_detected_name or normalized_detected_name in expected
        for expected in expected_names
    ):
        return "matched", Decimal("0.92")
    if detected_name or detected_tax_id or detected_email:
        return "mismatch", Decimal("0")
    return "not_detected", Decimal("0")


def _match_rows(
    rows: list[ExtractedQuoteRow],
    link: SupplierRFQSupplier,
) -> tuple[list[dict], dict[int, tuple[Decimal, str]], list[str]]:
    unmatched_rows = list(rows)
    items: list[dict] = []
    metadata: dict[int, tuple[Decimal, str]] = {}
    errors: list[str] = []

    for rfq_item in link.rfq.items:
        expected_description = _normalized(rfq_item.description)
        best: tuple[float, ExtractedQuoteRow] | None = None
        for row in unmatched_rows:
            description_score = SequenceMatcher(
                None,
                expected_description,
                _normalized(row.description),
            ).ratio()
            unit_matches = _normalized(rfq_item.unit) == _normalized(row.unit)
            quantity_matches = abs(Decimal(rfq_item.quantity) - row.quantity) <= QUANTITY_TOLERANCE
            score = description_score + (0.08 if unit_matches else 0) + (0.06 if quantity_matches else 0)
            if best is None or score > best[0]:
                best = (score, row)
        if best is None:
            continue
        score, row = best
        description_score = SequenceMatcher(
            None,
            expected_description,
            _normalized(row.description),
        ).ratio()
        if description_score < 0.80:
            continue
        unmatched_rows.remove(row)
        unit_matches = _normalized(rfq_item.unit) == _normalized(row.unit)
        quantity_matches = abs(Decimal(rfq_item.quantity) - row.quantity) <= QUANTITY_TOLERANCE
        if not unit_matches:
            errors.append(
                f"Unidad distinta en {rfq_item.description}: solicitud {rfq_item.unit}, PDF {row.unit}"
            )
        if not quantity_matches:
            errors.append(
                f"Cantidad distinta en {rfq_item.description}: solicitud {rfq_item.quantity}, PDF {row.quantity}"
            )
        expected_line_total = (row.quantity * row.unit_price).quantize(Decimal("0.01"))
        if abs(expected_line_total - row.line_total) > MONEY_TOLERANCE:
            errors.append(f"Importe inconsistente en {rfq_item.description}")
        confidence = Decimal(str(min(0.99, description_score))).quantize(Decimal("0.0001"))
        method = "description_exact" if description_score == 1 else "description_fuzzy"
        if not unit_matches or not quantity_matches:
            confidence = min(confidence, Decimal("0.7000"))
            method = f"{method}_review"
        metadata[rfq_item.id] = (confidence, method)
        items.append(
            {
                "rfq_item_id": rfq_item.id,
                "unit_price": row.unit_price,
                "delivery_days": None,
                "notes": None,
            }
        )

    if unmatched_rows:
        errors.append(f"El PDF contiene {len(unmatched_rows)} renglon(es) sin relacionar")
    return items, metadata, errors


def parse_supplier_quote_text(text: str, link: SupplierRFQSupplier) -> SupplierQuotePDFAnalysis:
    detected_rfqs = list(dict.fromkeys(match.upper() for match in RFQ_PATTERN.findall(text)))
    detected_rfq = detected_rfqs[0] if detected_rfqs else None
    if detected_rfq and detected_rfq != link.rfq.rfq_number.upper():
        raise SupplierQuotePDFMismatchError(
            f"El PDF pertenece a {detected_rfq}, no a {link.rfq.rfq_number}"
        )

    quote_match = re.search(r"\bFolio\s*:\s*([A-Z0-9][A-Z0-9._/-]*)", text, re.IGNORECASE)
    quote_number = quote_match.group(1).strip() if quote_match else ""
    if not quote_number:
        raise SupplierQuotePDFError("No fue posible identificar el folio de la cotizacion")

    currency_match = re.search(r"\bMoneda\s*:\s*([A-Z]{3})\b", text, re.IGNORECASE)
    currency = currency_match.group(1).upper() if currency_match else "MXN"
    quote_date = _date_from_text(text, "Fecha")
    validity_match = re.search(r"\bValidez\s*:\s*(\d+)\s*dias", text, re.IGNORECASE)
    valid_until = (
        quote_date + timedelta(days=int(validity_match.group(1)))
        if quote_date and validity_match
        else None
    )
    delivery_match = re.search(
        r"\bEntrega\s+estimada\s*:\s*(\d+)(?:\s*(?:a|-)\s*(\d+))?\s*dias",
        text,
        re.IGNORECASE,
    )
    delivery_days = (
        int(delivery_match.group(2) or delivery_match.group(1)) if delivery_match else None
    )

    emails = EMAIL_PATTERN.findall(text)
    detected_email = emails[0].lower() if emails else None
    detected_tax_ids = RFC_PATTERN.findall(text)
    detected_tax_id = detected_tax_ids[0].upper() if detected_tax_ids else None
    detected_name = _extract_issuer_name(text)
    supplier_match_status, supplier_match_confidence = _supplier_identity(
        link,
        detected_name,
        detected_tax_id,
        detected_email,
    )

    rows = _extract_rows(text)
    if not rows:
        raise SupplierQuotePDFError("No fue posible identificar partidas con precios en el PDF")
    items, item_metadata, errors = _match_rows(rows, link)
    if not items:
        raise SupplierQuotePDFError("Ninguna partida del PDF coincide con la solicitud")

    document_subtotal = _money_from_label(text, "Subtotal")
    document_tax = _money_from_label(text, r"IVA(?:\s+\d+%)?")
    document_total = _money_from_label(text, "TOTAL")
    calculated_subtotal = sum(
        (
            Decimal(rfq_item.quantity)
            * next(
                item["unit_price"]
                for item in items
                if item["rfq_item_id"] == rfq_item.id
            )
            for rfq_item in link.rfq.items
            if any(item["rfq_item_id"] == rfq_item.id for item in items)
        ),
        Decimal("0"),
    ).quantize(Decimal("0.01"))
    if document_subtotal is not None and abs(calculated_subtotal - document_subtotal) > MONEY_TOLERANCE:
        errors.append(
            f"Subtotal del PDF {document_subtotal} no coincide con partidas {calculated_subtotal}"
        )
    calculated_total = (
        document_subtotal + (document_tax or Decimal("0"))
        if document_subtotal is not None
        else None
    )
    if (
        calculated_total is not None
        and document_total is not None
        and abs(calculated_total - document_total) > MONEY_TOLERANCE
    ):
        errors.append("El total del PDF no coincide con subtotal mas impuestos")
    if supplier_match_status == "mismatch":
        errors.insert(
            0,
            (
                f"El emisor detectado ({detected_name or detected_email or detected_tax_id}) "
                f"no coincide con el proveedor asociado ({link.supplier.name})"
            ),
        )
    elif supplier_match_status == "not_detected":
        errors.insert(0, "No fue posible comprobar la identidad del proveedor en el PDF")

    average_confidence = (
        sum((value[0] for value in item_metadata.values()), Decimal("0"))
        / Decimal(len(item_metadata))
    ).quantize(Decimal("0.0001"))
    notes_parts = []
    if delivery_match and delivery_match.group(2):
        notes_parts.append(
            f"Entrega indicada en PDF: {delivery_match.group(1)} a {delivery_match.group(2)} dias"
        )
    payment_match = re.search(r"\bForma de pago\s*:\s*(.+)", text, re.IGNORECASE)
    if payment_match:
        notes_parts.append(f"Forma de pago PDF: {payment_match.group(1).strip()}")

    payload = SupplierQuoteDraftInput.model_validate(
        {
            "quote_number": quote_number,
            "valid_until": valid_until,
            "currency": currency,
            "delivery_days": delivery_days,
            "payment_terms_days": getattr(link.supplier, "payment_terms_days", 30) or 30,
            "discount": Decimal("0"),
            "shipping_cost": Decimal("0"),
            "tax_amount": document_tax or Decimal("0"),
            "notes": ". ".join(notes_parts) or None,
            "items": items,
        }
    )
    return SupplierQuotePDFAnalysis(
        payload=payload,
        confidence=average_confidence,
        validation_errors=errors,
        detected_supplier_name=detected_name,
        detected_supplier_tax_id=detected_tax_id,
        detected_supplier_email=detected_email,
        supplier_match_status=supplier_match_status,
        supplier_match_confidence=supplier_match_confidence,
        detected_rfq_number=detected_rfq,
        document_subtotal=document_subtotal,
        document_tax_amount=document_tax,
        document_total=document_total,
        item_metadata=item_metadata,
        extraction_metadata={
            "row_count": len(rows),
            "matched_item_count": len(items),
            "rfq_item_count": len(link.rfq.items),
            "quote_date": quote_date.isoformat() if quote_date else None,
        },
    )


def parse_supplier_quote_pdf(
    file_bytes: bytes,
    file_name: str,
    link: SupplierRFQSupplier,
) -> SupplierQuotePDFAnalysis:
    text, extraction_method = extract_supplier_quote_text(file_bytes, file_name)
    analysis = parse_supplier_quote_text(text, link)
    analysis.extraction_metadata["extraction_method"] = extraction_method
    return analysis
