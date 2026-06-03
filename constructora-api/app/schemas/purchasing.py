from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import NonNegativeDecimal, ORMModel, PositiveDecimal, TimestampRead
from app.schemas.inventory import ExpectedMaterialListRead


SupplierStatus = Literal["active", "suspended", "blocked"]
RFQStatus = Literal[
    "draft",
    "sent",
    "email_error",
    "partially_quoted",
    "quoted",
    "approval_pending",
    "awarded",
    "cancelled",
]
RFQSupplierStatus = Literal[
    "invited",
    "sent",
    "missing_email",
    "email_error",
    "responded",
    "declined",
    "awarded",
]
SupplierQuoteStatus = Literal["received", "approval_requested", "rejected", "discarded", "approved"]
SupplierQuoteApprovalStatus = Literal["requested", "approved", "rejected", "cancelled"]
SupplierRFQExceptionStatus = Literal["requested", "approved", "rejected", "used", "cancelled"]
PurchaseOrderStatus = Literal[
    "issued",
    "sent",
    "partially_received",
    "received",
    "factured",
    "closed",
    "cancelled",
]
SupplierInvoiceStatus = Literal[
    "received",
    "blocked",
    "approved_for_payment",
    "scheduled",
    "paid",
    "rejected",
]
SupplierPaymentStatus = Literal["scheduled", "paid", "cancelled"]


class SupplierBase(BaseModel):
    company_id: int | None = None
    name: str = Field(min_length=1, max_length=200)
    legal_name: str | None = Field(default=None, max_length=255)
    tax_id: str | None = Field(default=None, max_length=80)
    contact_name: str | None = Field(default=None, max_length=200)
    contact_email: str | None = Field(default=None, max_length=255)
    contact_phone: str | None = Field(default=None, max_length=80)
    address: str | None = None
    payment_terms_days: int = Field(default=30, ge=0)
    average_delivery_days: int | None = Field(default=None, ge=0)
    material_categories: str | None = None
    status: SupplierStatus = "active"
    notes: str | None = None


class SupplierCreate(SupplierBase):
    pass


class SupplierUpdate(BaseModel):
    company_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    legal_name: str | None = Field(default=None, max_length=255)
    tax_id: str | None = Field(default=None, max_length=80)
    contact_name: str | None = Field(default=None, max_length=200)
    contact_email: str | None = Field(default=None, max_length=255)
    contact_phone: str | None = Field(default=None, max_length=80)
    address: str | None = None
    payment_terms_days: int | None = Field(default=None, ge=0)
    average_delivery_days: int | None = Field(default=None, ge=0)
    material_categories: str | None = None
    status: SupplierStatus | None = None
    notes: str | None = None


class SupplierRead(SupplierBase, TimestampRead):
    id: int
    company_id: int


class SupplierRFQItemCreate(BaseModel):
    material_id: int | None = None
    source_code: str | None = Field(default=None, max_length=80)
    description: str = Field(min_length=1, max_length=255)
    unit: str = Field(min_length=1, max_length=40)
    quantity: PositiveDecimal
    notes: str | None = None


class SupplierRFQItemRead(SupplierRFQItemCreate, ORMModel):
    id: int
    rfq_id: int


class SupplierRFQSupplierRead(ORMModel):
    id: int
    rfq_id: int
    supplier_id: int
    status: RFQSupplierStatus
    sent_at: datetime | None = None
    notes: str | None = None
    supplier: SupplierRead | None = None


class UserSummaryRead(ORMModel):
    id: int
    full_name: str
    email: str


class SupplierRFQCreate(BaseModel):
    project_id: int
    warehouse_id: int | None = None
    rfq_number: str | None = Field(default=None, max_length=80)
    title: str = Field(min_length=1, max_length=200)
    required_by: date | None = None
    response_deadline: date | None = None
    notes: str | None = None
    supplier_ids: list[int] = Field(min_length=1)
    items: list[SupplierRFQItemCreate] = Field(min_length=1)
    exception_request_id: int | None = None


class SupplierRFQUpdate(BaseModel):
    warehouse_id: int | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    status: RFQStatus | None = None
    required_by: date | None = None
    response_deadline: date | None = None
    notes: str | None = None


class SupplierRFQRead(TimestampRead):
    id: int
    company_id: int
    project_id: int
    warehouse_id: int | None = None
    rfq_number: str
    title: str
    status: RFQStatus
    required_by: date | None = None
    response_deadline: date | None = None
    sent_at: datetime | None = None
    notes: str | None = None
    created_by: int | None = None
    creator: UserSummaryRead | None = None
    items: list[SupplierRFQItemRead] = Field(default_factory=list)
    supplier_links: list[SupplierRFQSupplierRead] = Field(default_factory=list)


class SupplierQuoteItemCreate(BaseModel):
    rfq_item_id: int
    unit_price: NonNegativeDecimal
    quantity: PositiveDecimal | None = None
    delivery_days: int | None = Field(default=None, ge=0)
    notes: str | None = None


class SupplierQuoteItemRead(ORMModel):
    id: int
    supplier_quote_id: int
    rfq_item_id: int
    material_id: int | None = None
    description: str
    unit: str
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal
    delivery_days: int | None = None
    notes: str | None = None


class SupplierQuoteCreate(BaseModel):
    supplier_id: int
    quote_number: str | None = Field(default=None, max_length=80)
    received_at: date | None = None
    valid_until: date | None = None
    delivery_days: int | None = Field(default=None, ge=0)
    payment_terms_days: int = Field(default=30, ge=0)
    notes: str | None = None
    attachment_name: str | None = Field(default=None, max_length=255)
    items: list[SupplierQuoteItemCreate] = Field(min_length=1)


class SupplierQuoteRead(TimestampRead):
    id: int
    company_id: int
    rfq_id: int
    supplier_id: int
    quote_number: str | None = None
    status: SupplierQuoteStatus
    received_at: date | None = None
    valid_until: date | None = None
    delivery_days: int | None = None
    payment_terms_days: int
    subtotal: Decimal
    notes: str | None = None
    attachment_name: str | None = None
    supplier: SupplierRead | None = None
    items: list[SupplierQuoteItemRead] = Field(default_factory=list)


class SupplierQuoteApprovalRequest(BaseModel):
    request_notes: str | None = None


class SupplierRFQApprovalRequest(BaseModel):
    is_exception: bool = False
    request_notes: str | None = None


class SupplierRFQExceptionCreate(BaseModel):
    project_id: int
    title: str = Field(min_length=1, max_length=200)
    required_by: date | None = None
    response_deadline: date | None = None
    supplier_ids: list[int] = Field(min_length=1)
    items: list[SupplierRFQItemCreate] = Field(min_length=1)
    request_notes: str = Field(min_length=1)


class SupplierRFQExceptionDecision(BaseModel):
    decision_notes: str | None = None


class SupplierRFQExceptionRead(TimestampRead):
    id: int
    company_id: int
    project_id: int
    rfq_id: int | None = None
    title: str
    status: SupplierRFQExceptionStatus
    required_by: date | None = None
    response_deadline: date | None = None
    supplier_count: int
    item_count: int
    payload_snapshot: dict
    payload_fingerprint: str | None = None
    request_notes: str
    decision_notes: str | None = None
    requested_by: int | None = None
    requested_at: datetime
    decided_by: int | None = None
    decided_at: datetime | None = None
    used_at: datetime | None = None
    requester: UserSummaryRead | None = None
    decider: UserSummaryRead | None = None


class SupplierQuoteApprovalDecision(BaseModel):
    decision_notes: str | None = None


class SupplierQuoteApprovalRead(TimestampRead):
    id: int
    company_id: int
    rfq_id: int
    supplier_quote_id: int
    status: SupplierQuoteApprovalStatus
    request_notes: str | None = None
    decision_notes: str | None = None
    requested_by: int | None = None
    requested_at: datetime
    decided_by: int | None = None
    decided_at: datetime | None = None
    requester: UserSummaryRead | None = None
    decider: UserSummaryRead | None = None
    supplier_quote: SupplierQuoteRead
    rfq: SupplierRFQRead


class SupplierRFQComparisonRow(BaseModel):
    supplier_quote_id: int
    supplier_id: int
    supplier_name: str
    subtotal: Decimal
    delivery_days: int | None = None
    payment_terms_days: int
    status: str
    complete_items: int
    total_items: int


class PurchaseOrderItemRead(ORMModel):
    id: int
    purchase_order_id: int
    rfq_item_id: int | None = None
    material_id: int | None = None
    description: str
    unit: str
    quantity_ordered: Decimal
    unit_price: Decimal
    line_total: Decimal
    received_quantity: Decimal
    status: str
    notes: str | None = None


class PurchaseOrderRead(TimestampRead):
    id: int
    company_id: int
    project_id: int
    warehouse_id: int | None = None
    supplier_id: int
    supplier_quote_id: int | None = None
    po_number: str
    status: PurchaseOrderStatus
    issued_at: date
    expected_delivery_date: date | None = None
    payment_terms_days: int
    subtotal: Decimal
    notes: str | None = None
    approved_by: int | None = None
    approved_at: datetime | None = None
    supplier: SupplierRead | None = None
    items: list[PurchaseOrderItemRead] = Field(default_factory=list)


class SupplierInvoiceCreate(BaseModel):
    purchase_order_id: int
    invoice_number: str = Field(min_length=1, max_length=100)
    invoice_date: date
    due_date: date | None = None
    subtotal: NonNegativeDecimal | None = None
    total: PositiveDecimal
    document_name: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class SupplierInvoiceRead(TimestampRead):
    id: int
    company_id: int
    supplier_id: int
    purchase_order_id: int
    invoice_number: str
    invoice_date: date
    due_date: date
    subtotal: Decimal | None = None
    total: Decimal
    status: SupplierInvoiceStatus
    document_name: str | None = None
    notes: str | None = None
    validated_at: datetime | None = None
    validated_by: int | None = None
    supplier: SupplierRead | None = None
    purchase_order: PurchaseOrderRead | None = None


class SupplierPaymentCreate(BaseModel):
    supplier_invoice_id: int
    amount: PositiveDecimal
    scheduled_date: date | None = None
    paid_at: date | None = None
    status: SupplierPaymentStatus = "scheduled"
    reference: str | None = Field(default=None, max_length=160)
    proof_document_name: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class SupplierPaymentUpdate(BaseModel):
    amount: PositiveDecimal | None = None
    scheduled_date: date | None = None
    paid_at: date | None = None
    status: SupplierPaymentStatus | None = None
    reference: str | None = Field(default=None, max_length=160)
    proof_document_name: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class SupplierPaymentRead(TimestampRead):
    id: int
    company_id: int
    supplier_invoice_id: int
    amount: Decimal
    scheduled_date: date | None = None
    paid_at: date | None = None
    status: SupplierPaymentStatus
    reference: str | None = None
    proof_document_name: str | None = None
    notes: str | None = None
    approved_by: int | None = None


class SupplierInvoiceValidation(BaseModel):
    invoice_id: int
    status: SupplierInvoiceStatus
    pending_items: int
    message: str


class PurchaseOrderApprovalRead(BaseModel):
    purchase_order: PurchaseOrderRead
    expected_list: ExpectedMaterialListRead


def invoice_due_date(invoice_date: date, payment_terms_days: int) -> date:
    return invoice_date + timedelta(days=payment_terms_days)
