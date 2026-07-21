from __future__ import annotations

import secrets
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    FinancialReconciliationCase,
    PurchaseOrder,
    PurchaseOrderAmendment,
    SupplierInvoice,
    SupplierInvoiceCorrection,
    SupplierPayment,
    SupplierPaymentReversal,
    User,
)
from app.schemas.purchasing import FinancialReconciliationCreate
from app.services.audit import snapshot


CENT = Decimal("0.01")
INACTIVE_INVOICE_STATUSES = {"rejected", "cancelled"}
ACTIVE_PAYMENT_STATUSES = {"scheduled", "paid"}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _money(value: Decimal | str | int | None) -> Decimal:
    return Decimal(value or 0).quantize(CENT)


def _invoice_net(invoice: SupplierInvoice) -> Decimal:
    if invoice.subtotal is not None:
        value = Decimal(invoice.subtotal)
    elif invoice.items:
        value = sum((Decimal(item.line_total) for item in invoice.items), Decimal("0"))
    else:
        value = Decimal(invoice.total)
    if invoice.currency.upper() != "MXN":
        if invoice.exchange_rate is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"La factura {invoice.invoice_number} no tiene tipo de cambio para conciliarla.",
            )
        value *= Decimal(invoice.exchange_rate)
    return _money(value)


def _case_statement():
    return select(FinancialReconciliationCase).options(
        selectinload(FinancialReconciliationCase.project),
        selectinload(FinancialReconciliationCase.purchase_order),
        selectinload(FinancialReconciliationCase.supplier_invoice).selectinload(
            SupplierInvoice.payments
        ),
        selectinload(FinancialReconciliationCase.supplier_invoice).selectinload(
            SupplierInvoice.items
        ),
        selectinload(FinancialReconciliationCase.supplier_payment),
        selectinload(FinancialReconciliationCase.requester),
        selectinload(FinancialReconciliationCase.decider),
    )


def reconciliation_case_read(case: FinancialReconciliationCase) -> dict:
    return {
        "id": case.id,
        "company_id": case.company_id,
        "project_id": case.project_id,
        "project_name": case.project.name,
        "purchase_order_id": case.purchase_order_id,
        "purchase_order_number": case.purchase_order.po_number,
        "supplier_invoice_id": case.supplier_invoice_id,
        "invoice_number": case.supplier_invoice.invoice_number,
        "supplier_payment_id": case.supplier_payment_id,
        "payment_reference": case.supplier_payment.reference if case.supplier_payment else None,
        "case_number": case.case_number,
        "issue_type": case.issue_type,
        "resolution_type": case.resolution_type,
        "status": case.status,
        "reason": case.reason,
        "proposed_data": case.proposed_data,
        "original_snapshot": case.original_snapshot,
        "decision_notes": case.decision_notes,
        "requested_by": case.requested_by,
        "requester_name": case.requester.full_name if case.requester else None,
        "requested_at": case.requested_at,
        "decided_by": case.decided_by,
        "decider_name": case.decider.full_name if case.decider else None,
        "decided_at": case.decided_at,
        "applied_by": case.applied_by,
        "applied_at": case.applied_at,
        "created_at": case.created_at,
        "updated_at": case.updated_at,
    }


def get_reconciliation_case(db: Session, case_id: int) -> FinancialReconciliationCase:
    case = db.scalar(_case_statement().where(FinancialReconciliationCase.id == case_id))
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conciliacion no encontrada")
    return case


def create_reconciliation_case(
    db: Session,
    *,
    payload: FinancialReconciliationCreate,
    invoice: SupplierInvoice,
    requested_by: User,
) -> FinancialReconciliationCase:
    purchase_order = invoice.purchase_order
    if purchase_order is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La factura no tiene orden")
    existing = db.scalar(
        select(FinancialReconciliationCase.id).where(
            FinancialReconciliationCase.supplier_invoice_id == invoice.id,
            FinancialReconciliationCase.status == "requested",
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La factura ya tiene una conciliacion pendiente de decision.",
        )

    payment = None
    if payload.supplier_payment_id is not None:
        payment = db.scalar(
            select(SupplierPayment).where(
                SupplierPayment.id == payload.supplier_payment_id,
                SupplierPayment.supplier_invoice_id == invoice.id,
            )
        )
        if payment is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El pago no pertenece a la factura")

    proposed = {
        key: str(value) if isinstance(value, Decimal) else value
        for key, value in payload.model_dump(
            exclude={"supplier_invoice_id", "supplier_payment_id", "issue_type", "resolution_type", "reason"},
            exclude_none=True,
        ).items()
    }
    resolution = payload.resolution_type
    if resolution == "correct_invoice" and not {"corrected_subtotal", "corrected_total"} <= proposed.keys():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Captura subtotal y total corregidos.",
        )
    if resolution == "amend_purchase_order" and "amended_purchase_order_subtotal" not in proposed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Captura el nuevo subtotal de la OC.")
    if resolution == "reverse_payment" and (payment is None or payment.status != "paid"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selecciona un pago realizado.")
    if resolution in {"correct_invoice", "cancel_invoice"}:
        active = [item for item in invoice.payments if item.status in ACTIVE_PAYMENT_STATUSES]
        if active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Primero solicita la reversion o cancelacion de los pagos activos de la factura.",
            )

    original = {
        "invoice": snapshot(invoice),
        "purchase_order": snapshot(purchase_order),
        "payment": snapshot(payment) if payment else None,
    }
    case = FinancialReconciliationCase(
        company_id=invoice.company_id,
        project_id=purchase_order.project_id,
        purchase_order_id=purchase_order.id,
        supplier_invoice_id=invoice.id,
        supplier_payment_id=payment.id if payment else None,
        case_number=f"TMP-{secrets.token_hex(8)}",
        issue_type=payload.issue_type,
        resolution_type=resolution,
        status="requested",
        reason=payload.reason.strip(),
        proposed_data=proposed,
        original_snapshot=original,
        requested_by=requested_by.id,
        requested_at=now_utc(),
    )
    db.add(case)
    db.flush()
    case.case_number = f"CF-{case.requested_at:%Y%m}-{case.id:05d}"
    db.flush()
    return get_reconciliation_case(db, case.id)


def _active_invoice_total(db: Session, purchase_order_id: int, *, exclude_id: int | None = None) -> Decimal:
    statement = (
        select(SupplierInvoice)
        .where(
            SupplierInvoice.purchase_order_id == purchase_order_id,
            SupplierInvoice.status.notin_(INACTIVE_INVOICE_STATUSES),
        )
        .options(selectinload(SupplierInvoice.items))
    )
    if exclude_id is not None:
        statement = statement.where(SupplierInvoice.id != exclude_id)
    return _money(sum((_invoice_net(invoice) for invoice in db.scalars(statement).all()), Decimal("0")))


def _apply_invoice_correction(db: Session, case: FinancialReconciliationCase, user: User) -> None:
    invoice = case.supplier_invoice
    if any(payment.status in ACTIVE_PAYMENT_STATUSES for payment in invoice.payments):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La factura tiene pagos activos.")
    proposed = case.proposed_data
    subtotal = _money(proposed["corrected_subtotal"])
    total = _money(proposed["corrected_total"])
    discount = _money(proposed.get("corrected_discount", invoice.discount))
    transferred = _money(proposed.get("corrected_transferred_taxes", invoice.transferred_taxes))
    withheld = _money(proposed.get("corrected_withheld_taxes", invoice.withheld_taxes))
    expected_total = _money(subtotal - discount + transferred - withheld)
    if abs(expected_total - total) > CENT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El total fiscal no cuadra con subtotal, descuentos e impuestos ({expected_total:.2f}).",
        )
    other_total = _active_invoice_total(db, case.purchase_order_id, exclude_id=invoice.id)
    if other_total + subtotal > _money(case.purchase_order.subtotal) + CENT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La correccion todavia supera el subtotal disponible de la orden de compra.",
        )
    before = snapshot(invoice)
    invoice.subtotal = subtotal
    invoice.discount = discount
    invoice.transferred_taxes = transferred
    invoice.withheld_taxes = withheld
    invoice.total = total
    invoice.status = "fiscal_review"
    invoice.fiscal_status = "pending_manual"
    invoice.fiscal_validation_message = "Importes corregidos mediante conciliacion; requiere nueva validacion fiscal."
    invoice.validated_at = None
    invoice.validated_by = None
    db.flush()
    db.add(
        SupplierInvoiceCorrection(
            company_id=case.company_id,
            supplier_invoice_id=invoice.id,
            reconciliation_case_id=case.id,
            before_snapshot=before,
            after_snapshot=snapshot(invoice),
            reason=case.reason,
            applied_by=user.id,
            applied_at=now_utc(),
        )
    )


def _apply_order_amendment(db: Session, case: FinancialReconciliationCase, user: User) -> None:
    order = case.purchase_order
    previous = _money(order.subtotal)
    new = _money(case.proposed_data["amended_purchase_order_subtotal"])
    invoiced = _active_invoice_total(db, order.id)
    if new <= previous:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La adenda debe aumentar el subtotal de la OC.")
    if new + CENT < invoiced:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La adenda no cubre las facturas activas.")
    order.subtotal = new
    db.add(
        PurchaseOrderAmendment(
            company_id=case.company_id,
            purchase_order_id=order.id,
            reconciliation_case_id=case.id,
            previous_subtotal=previous,
            new_subtotal=new,
            difference=new - previous,
            reason=case.reason,
            applied_by=user.id,
            applied_at=now_utc(),
        )
    )


def _sync_invoice_payment_status(db: Session, invoice: SupplierInvoice) -> None:
    active = [payment for payment in invoice.payments if payment.status in ACTIVE_PAYMENT_STATUSES]
    paid = sum((Decimal(payment.amount) for payment in active if payment.status == "paid"), Decimal("0"))
    scheduled = sum(
        (Decimal(payment.amount) for payment in active if payment.status == "scheduled"), Decimal("0")
    )
    if paid >= Decimal(invoice.total):
        invoice.status = "paid"
    elif paid + scheduled > 0:
        invoice.status = "scheduled"
    else:
        invoice.status = "approved_for_payment"


def _apply_payment_reversal(db: Session, case: FinancialReconciliationCase, user: User) -> None:
    payment = case.supplier_payment
    if payment is None or payment.status != "paid":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El pago ya no esta disponible para revertir.")
    payment.status = "reversed"
    db.add(
        SupplierPaymentReversal(
            company_id=case.company_id,
            supplier_payment_id=payment.id,
            reconciliation_case_id=case.id,
            amount=payment.amount,
            reason=case.reason,
            applied_by=user.id,
            applied_at=now_utc(),
        )
    )
    _sync_invoice_payment_status(db, case.supplier_invoice)
    if case.purchase_order.status == "closed":
        complete = all(item.received_quantity >= item.quantity_ordered for item in case.purchase_order.items)
        case.purchase_order.status = "received" if complete else "partially_received"


def _apply_invoice_cancellation(db: Session, case: FinancialReconciliationCase) -> None:
    invoice = case.supplier_invoice
    if any(payment.status in ACTIVE_PAYMENT_STATUSES for payment in invoice.payments):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La factura tiene pagos activos.")
    invoice.status = "cancelled"
    invoice.fiscal_status = "cancelled"
    invoice.fiscal_validation_message = f"Cancelada mediante {case.case_number}: {case.reason}"
    invoice.validated_at = None
    invoice.validated_by = None


def apply_reconciliation_case(
    db: Session,
    *,
    case: FinancialReconciliationCase,
    decided_by: User,
    approved: bool,
    notes: str,
) -> FinancialReconciliationCase:
    if case.status != "requested":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La conciliacion ya fue resuelta.")
    case.decided_by = decided_by.id
    case.decided_at = now_utc()
    case.decision_notes = notes.strip()
    if not approved:
        case.status = "rejected"
        db.flush()
        return get_reconciliation_case(db, case.id)

    handlers = {
        "correct_invoice": lambda: _apply_invoice_correction(db, case, decided_by),
        "amend_purchase_order": lambda: _apply_order_amendment(db, case, decided_by),
        "reverse_payment": lambda: _apply_payment_reversal(db, case, decided_by),
        "cancel_invoice": lambda: _apply_invoice_cancellation(db, case),
    }
    handler = handlers.get(case.resolution_type)
    if handler is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Resolucion no soportada")
    handler()
    case.status = "applied"
    case.applied_by = decided_by.id
    case.applied_at = now_utc()
    db.flush()
    return get_reconciliation_case(db, case.id)
