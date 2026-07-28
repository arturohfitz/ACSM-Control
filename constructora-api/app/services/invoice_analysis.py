from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher

from app.services.invoice_documents import InvoiceDocumentError, ValidatedInvoiceFile
from app.services.supplier_quote_pdf import (
    SupplierQuotePDFError,
    extract_supplier_quote_text,
)


PDF_ROW_PATTERN = re.compile(
    r"^(?P<description>.+?)\s{2,}"
    r"(?P<unit>[A-Z0-9./\"'-]+)\s+"
    r"(?P<quantity>\d[\d,]*(?:\.\d+)?)\s+"
    r"\$\s*(?P<unit_price>\d[\d,]*(?:\.\d+)?)\s+"
    r"\$\s*(?P<line_total>\d[\d,]*(?:\.\d+)?)\s*$",
    re.IGNORECASE,
)
RFC_PATTERN = re.compile(r"\b[A-Z&Ñ]{3,4}\d{6}[A-Z0-9]{3}\b", re.IGNORECASE)


@dataclass(frozen=True)
class InvoiceSourceItem:
    description: str
    unit: str
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal
    identification_number: str | None = None


def _decimal(raw: str | int | float | Decimal | None) -> Decimal:
    try:
        return Decimal(str(raw or "0").replace(",", "").strip())
    except (InvalidOperation, ValueError) as exc:
        raise InvoiceDocumentError(f"Numero invalido en la factura: {raw}") from exc


def _normalized(value: str | None) -> str:
    decomposed = unicodedata.normalize("NFKD", value or "")
    ascii_value = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return " ".join(re.sub(r"[^A-Z0-9]+", " ", ascii_value.upper()).split())


def _money_from_label(text: str, label: str) -> Decimal | None:
    matches = list(
        re.finditer(
            rf"(?:^|\n)\s*{label}[^\d$-]*\$?\s*(-?\d[\d,]*(?:\.\d{{1,6}})?)",
            text,
            re.IGNORECASE,
        )
    )
    return _decimal(matches[-1].group(1)) if matches else None


def _date_from_text(text: str) -> date | None:
    match = re.search(
        r"\bFecha(?:\s+de\s+emision)?\s*:\s*(\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2})",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    raw = match.group(1)
    try:
        if "-" in raw:
            return date.fromisoformat(raw)
        day, month, year = (int(part) for part in raw.split("/"))
        return date(year, month, day)
    except ValueError:
        return None


def parse_invoice_pdf_text(text: str) -> tuple[dict[str, object], list[InvoiceSourceItem]]:
    rows: list[InvoiceSourceItem] = []
    for line in text.splitlines():
        match = PDF_ROW_PATTERN.match(line.rstrip())
        if not match:
            continue
        rows.append(
            InvoiceSourceItem(
                description=match.group("description").strip(),
                unit=match.group("unit").strip().upper(),
                quantity=_decimal(match.group("quantity")),
                unit_price=_decimal(match.group("unit_price")),
                line_total=_decimal(match.group("line_total")),
            )
        )

    folio_match = re.search(
        r"\b(?:Folio|Factura|No\.\s*factura)\s*:\s*([A-Z0-9][A-Z0-9./_-]*)",
        text,
        re.IGNORECASE,
    )
    currency_match = re.search(r"\bMoneda\s*:\s*([A-Z]{3})\b", text, re.IGNORECASE)
    tax_ids = [match.group(0).upper() for match in RFC_PATTERN.finditer(text)]
    invoice_date = _date_from_text(text)
    parsed: dict[str, object] = {
        "folio": folio_match.group(1).strip() if folio_match else "",
        "issue_datetime": invoice_date.isoformat() if invoice_date else "",
        "currency": currency_match.group(1).upper() if currency_match else "MXN",
        "subtotal": str(_money_from_label(text, "Subtotal") or ""),
        "transferred_taxes": str(
            _money_from_label(text, r"(?:IVA(?:\s+\d+(?:\.\d+)?%)?|Impuestos)") or ""
        ),
        "total": str(_money_from_label(text, "TOTAL") or ""),
        "issuer_tax_id": tax_ids[0] if tax_ids else "",
        "receiver_tax_id": tax_ids[1] if len(tax_ids) > 1 else "",
        "concepts": [
            {
                "description": row.description,
                "identification_number": row.identification_number or "",
                "unit": row.unit,
                "quantity": str(row.quantity),
                "unit_price": str(row.unit_price),
                "line_total": str(row.line_total),
            }
            for row in rows
        ],
    }
    return parsed, rows


def _source_items_from_xml(parsed_data: dict[str, object]) -> list[InvoiceSourceItem]:
    items: list[InvoiceSourceItem] = []
    concepts = parsed_data.get("concepts")
    if not isinstance(concepts, list):
        return items
    for raw in concepts:
        if not isinstance(raw, dict):
            continue
        items.append(
            InvoiceSourceItem(
                description=str(raw.get("description") or ""),
                identification_number=str(raw.get("identification_number") or "") or None,
                unit=str(raw.get("unit") or raw.get("unit_code") or "").upper(),
                quantity=_decimal(raw.get("quantity")),
                unit_price=_decimal(raw.get("unit_price")),
                line_total=_decimal(raw.get("line_total")),
            )
        )
    return items


def _description_score(source: InvoiceSourceItem, target) -> Decimal:
    source_description = _normalized(source.description)
    target_description = _normalized(target.description)
    if not source_description or not target_description:
        return Decimal("0")
    score = Decimal(str(SequenceMatcher(None, source_description, target_description).ratio()))
    if source_description in target_description or target_description in source_description:
        score = max(score, Decimal("0.92"))
    source_unit = _normalized(source.unit)
    target_unit = _normalized(target.unit)
    if source_unit and target_unit:
        score += Decimal("0.06") if source_unit == target_unit else Decimal("-0.04")
    return max(Decimal("0"), min(score, Decimal("1")))


def reconcile_invoice_items(
    source_items: list[InvoiceSourceItem],
    purchase_order_items: list,
    already_invoiced: dict[int, Decimal],
) -> tuple[list[dict[str, object]], list[str]]:
    analyses: list[dict[str, object]] = []
    warnings: list[str] = []
    matches: dict[int, tuple[object, Decimal]] = {}
    used_sources: set[int] = set()
    used_targets: set[int] = set()
    scored_pairs = sorted(
        (
            (_description_score(source, target), source_index, target)
            for source_index, source in enumerate(source_items)
            for target in purchase_order_items
        ),
        key=lambda candidate: candidate[0],
        reverse=True,
    )
    for confidence, source_index, target in scored_pairs:
        if confidence < Decimal("0.64"):
            break
        if source_index in used_sources or target.id in used_targets:
            continue
        matches[source_index] = (target, confidence)
        used_sources.add(source_index)
        used_targets.add(target.id)

    for source_index, source in enumerate(source_items):
        target, confidence = matches.get(source_index, (None, Decimal("0")))
        matched = target is not None
        if not matched:
            warnings.append(f"No se identifico la partida: {source.description}")
            analyses.append(
                {
                    "purchase_order_item_id": None,
                    "source_description": source.description,
                    "matched_description": None,
                    "source_unit": source.unit,
                    "source_quantity": source.quantity,
                    "billable_quantity": Decimal("0"),
                    "unit_price": source.unit_price,
                    "line_total": source.line_total,
                    "match_status": "unmatched",
                    "confidence": confidence,
                }
            )
            continue

        available = max(
            Decimal(target.received_quantity or 0)
            - already_invoiced.get(target.id, Decimal("0")),
            Decimal("0"),
        )
        billable = min(source.quantity, available)
        status = "matched"
        if source.quantity > available:
            status = "limited"
            warnings.append(
                f"{source.description}: la factura indica {source.quantity} {source.unit}, "
                f"pero solo hay {available} {target.unit} disponibles para facturar."
            )
        elif confidence < Decimal("0.82"):
            status = "review"
            warnings.append(f"Revisa la coincidencia de la partida: {source.description}")
        analyses.append(
            {
                "purchase_order_item_id": target.id,
                "source_description": source.description,
                "matched_description": target.description,
                "source_unit": source.unit,
                "source_quantity": source.quantity,
                "billable_quantity": billable,
                "unit_price": source.unit_price,
                "line_total": source.line_total,
                "match_status": status,
                "confidence": confidence,
            }
        )
    return analyses, warnings


def analyze_invoice_document(
    validated: ValidatedInvoiceFile,
    *,
    file_name: str,
    purchase_order_items: list,
    already_invoiced: dict[int, Decimal],
) -> dict[str, object]:
    extraction_method = "structured_xml"
    if validated.document_type == "xml":
        parsed_data = validated.parsed_data or {}
        source_items = _source_items_from_xml(parsed_data)
    else:
        try:
            text, extraction_method = extract_supplier_quote_text(validated.content, file_name)
        except SupplierQuotePDFError as exc:
            raise InvoiceDocumentError(str(exc)) from exc
        parsed_data, source_items = parse_invoice_pdf_text(text)

    items, warnings = reconcile_invoice_items(
        source_items,
        purchase_order_items,
        already_invoiced,
    )
    matched_items = sum(1 for item in items if item["purchase_order_item_id"] is not None)
    if not source_items:
        warnings.append(
            "No se detectaron conceptos en el documento; completa las partidas manualmente."
        )
    requires_review = (
        validated.document_type == "pdf"
        or bool(warnings)
        or matched_items != len(source_items)
    )
    return {
        "document_type": validated.document_type,
        "extraction_method": extraction_method,
        "validation_status": validated.validation_status,
        "validation_message": validated.validation_message,
        "parsed_data": parsed_data,
        "items": items,
        "matched_items": matched_items,
        "source_items": len(source_items),
        "warnings": warnings,
        "requires_review": requires_review,
    }
