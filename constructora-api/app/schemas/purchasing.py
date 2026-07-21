from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import NonNegativeDecimal, ORMModel, PositiveDecimal, TimestampRead


SupplierStatus = Literal["active", "suspended", "blocked"]
SupplierAgreementStatus = Literal["active", "suspended", "expired"]
SupplierAgreementApprovalStatus = Literal["requested", "approved", "rejected", "cancelled"]
SupplierAgreementItemStatus = Literal["active", "inactive"]
RFQStatus = Literal[
    "draft",
    "sent",
    "email_error",
    "partially_quoted",
    "quoted",
    "approval_pending",
    "approved_for_order",
    "purchase_order_ready",
    "awarded",
    "cancelled",
]
RFQSupplierStatus = Literal[
    "invited",
    "queued",
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
PurchaseOrderBillingMode = Literal["single", "partial"]
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
    "document_pending",
    "fiscal_review",
    "received",
    "blocked",
    "approved_for_payment",
    "scheduled",
    "paid",
    "rejected",
    "cancelled",
]
SupplierPaymentStatus = Literal["scheduled", "paid", "cancelled", "reversed"]
FinancialReconciliationResolution = Literal[
    "correct_invoice",
    "amend_purchase_order",
    "reverse_payment",
    "cancel_invoice",
]
FinancialReconciliationStatus = Literal["requested", "applied", "rejected"]


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


class SupplierAgreementItemBase(BaseModel):
    material_id: int
    description: str = Field(min_length=1, max_length=255)
    unit: str = Field(min_length=1, max_length=40)
    unit_price: NonNegativeDecimal
    currency: str = Field(default="MXN", max_length=8)
    delivery_days: int | None = Field(default=None, ge=0)
    min_quantity: NonNegativeDecimal | None = None
    max_quantity: PositiveDecimal | None = None
    status: SupplierAgreementItemStatus = "active"
    notes: str | None = None


class SupplierAgreementItemCreate(SupplierAgreementItemBase):
    pass


class SupplierAgreementItemUpdate(BaseModel):
    material_id: int | None = None
    description: str | None = Field(default=None, min_length=1, max_length=255)
    unit: str | None = Field(default=None, min_length=1, max_length=40)
    unit_price: NonNegativeDecimal | None = None
    currency: str | None = Field(default=None, max_length=8)
    delivery_days: int | None = Field(default=None, ge=0)
    min_quantity: NonNegativeDecimal | None = None
    max_quantity: PositiveDecimal | None = None
    status: SupplierAgreementItemStatus | None = None
    notes: str | None = None


class SupplierAgreementItemRead(SupplierAgreementItemBase, TimestampRead):
    id: int
    agreement_id: int


class UserSummaryRead(ORMModel):
    id: int
    full_name: str
    email: str


class SupplierAgreementClientRead(ORMModel):
    id: int
    name: str


class SupplierAgreementHouseModelRead(ORMModel):
    id: int
    name: str
    client_id: int | None = None


class SupplierAgreementBase(BaseModel):
    company_id: int | None = None
    supplier_id: int
    client_id: int
    house_model_id: int
    agreement_number: str | None = Field(default=None, max_length=120)
    name: str = Field(min_length=1, max_length=200)
    status: SupplierAgreementStatus = "active"
    valid_from: date | None = None
    valid_until: date | None = None
    payment_terms_days: int = Field(default=30, ge=0)
    average_delivery_days: int | None = Field(default=None, ge=0)
    notes: str | None = None
    request_notes: str | None = None


class SupplierAgreementCreate(SupplierAgreementBase):
    items: list[SupplierAgreementItemCreate] = Field(default_factory=list)


class SupplierAgreementUpdate(BaseModel):
    company_id: int | None = None
    supplier_id: int | None = None
    client_id: int | None = None
    house_model_id: int | None = None
    agreement_number: str | None = Field(default=None, max_length=120)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    status: SupplierAgreementStatus | None = None
    valid_from: date | None = None
    valid_until: date | None = None
    payment_terms_days: int | None = Field(default=None, ge=0)
    average_delivery_days: int | None = Field(default=None, ge=0)
    notes: str | None = None
    request_notes: str | None = None


class SupplierAgreementRead(SupplierAgreementBase, TimestampRead):
    id: int
    company_id: int
    created_by: int | None = None
    approval_status: SupplierAgreementApprovalStatus = "requested"
    decision_notes: str | None = None
    requested_at: datetime | None = None
    decided_by: int | None = None
    decided_at: datetime | None = None
    supplier: SupplierRead | None = None
    client: SupplierAgreementClientRead | None = None
    house_model: SupplierAgreementHouseModelRead | None = None
    creator: UserSummaryRead | None = None
    decider: UserSummaryRead | None = None
    items: list[SupplierAgreementItemRead] = Field(default_factory=list)


class SupplierAgreementEligibility(BaseModel):
    agreement: SupplierAgreementRead
    covered_material_ids: list[int]
    missing_material_ids: list[int]
    is_full_match: bool


class SupplierRFQItemCreate(BaseModel):
    house_model_id: int | None = None
    house_model_material_requirement_id: int | None = None
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
    portal_token_expires_at: datetime | None = None
    portal_last_accessed_at: datetime | None = None
    notes: str | None = None
    supplier: SupplierRead | None = None


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
    supplier_agreement_id: int | None = None
    material_requisition_id: int | None = None


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
    request_type: str = "standard"
    supplier_agreement_id: int | None = None
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


class SupplierQuoteUploadRead(TimestampRead):
    id: int
    company_id: int
    rfq_id: int
    rfq_supplier_id: int
    supplier_id: int
    quote_number: str | None = None
    original_file_name: str
    content_type: str | None = None
    file_extension: str
    file_size_bytes: int
    file_sha256: str
    status: str
    uploaded_at: datetime
    notes: str | None = None
    supplier: SupplierRead | None = None


class SupplierPortalRFQRead(BaseModel):
    rfq_number: str
    title: str
    required_by: date | None = None
    response_deadline: date | None = None
    supplier_name: str
    items: list[SupplierRFQItemRead] = Field(default_factory=list)
    previous_uploads: list[SupplierQuoteUploadRead] = Field(default_factory=list)


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


class PurchaseCaseStepRead(BaseModel):
    key: str
    label: str
    status: Literal["complete", "current", "pending", "attention"]
    detail: str


class PurchaseCaseRead(BaseModel):
    id: int
    rfq_id: int
    rfq_number: str
    title: str
    status: RFQStatus
    project_id: int
    project_name: str
    requisition_id: int | None = None
    requisition_number: str | None = None
    owner_name: str | None = None
    required_by: date | None = None
    response_deadline: date | None = None
    supplier_count: int
    item_count: int
    upload_count: int
    quote_count: int
    complete_quote_count: int
    required_quote_count: int
    approval_status: SupplierQuoteApprovalStatus | None = None
    approved_supplier_name: str | None = None
    approved_total: Decimal | None = None
    purchase_order_id: int | None = None
    purchase_order_number: str | None = None
    purchase_order_status: PurchaseOrderStatus | None = None
    current_stage: str
    current_stage_label: str
    next_action_label: str
    next_action_url: str
    needs_attention: bool = False
    steps: list[PurchaseCaseStepRead]
    created_at: datetime
    updated_at: datetime


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
    billing_mode: PurchaseOrderBillingMode = "single"
    issued_at: date
    expected_delivery_date: date | None = None
    payment_terms_days: int
    subtotal: Decimal
    notes: str | None = None
    approved_by: int | None = None
    approved_at: datetime | None = None
    supplier: SupplierRead | None = None
    items: list[PurchaseOrderItemRead] = Field(default_factory=list)


class PurchaseOrderBillingModeUpdate(BaseModel):
    billing_mode: PurchaseOrderBillingMode


class SupplierInvoiceItemCreate(BaseModel):
    purchase_order_item_id: int
    quantity: PositiveDecimal
    unit_price: NonNegativeDecimal | None = None
    notes: str | None = None


class SupplierInvoiceItemRead(ORMModel):
    id: int
    supplier_invoice_id: int
    purchase_order_item_id: int
    material_id: int | None = None
    description: str
    unit: str
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal
    notes: str | None = None


class SupplierInvoiceCreate(BaseModel):
    purchase_order_id: int
    invoice_number: str = Field(min_length=1, max_length=100)
    invoice_date: date
    due_date: date | None = None
    subtotal: NonNegativeDecimal | None = None
    discount: NonNegativeDecimal | None = None
    transferred_taxes: NonNegativeDecimal | None = None
    withheld_taxes: NonNegativeDecimal | None = None
    total: PositiveDecimal
    currency: str = Field(default="MXN", min_length=3, max_length=10)
    exchange_rate: PositiveDecimal | None = None
    fiscal_uuid: str | None = Field(default=None, max_length=40)
    series: str | None = Field(default=None, max_length=40)
    issuer_tax_id: str | None = Field(default=None, max_length=20)
    receiver_tax_id: str | None = Field(default=None, max_length=20)
    payment_method: str | None = Field(default=None, max_length=10)
    payment_form: str | None = Field(default=None, max_length=10)
    document_name: str | None = Field(default=None, max_length=255)
    notes: str | None = None
    items: list[SupplierInvoiceItemCreate] = Field(default_factory=list)


class SupplierInvoiceRead(TimestampRead):
    id: int
    company_id: int
    supplier_id: int
    purchase_order_id: int
    invoice_number: str
    invoice_date: date
    due_date: date
    subtotal: Decimal | None = None
    discount: Decimal | None = None
    transferred_taxes: Decimal | None = None
    withheld_taxes: Decimal | None = None
    total: Decimal
    currency: str
    exchange_rate: Decimal | None = None
    fiscal_uuid: str | None = None
    series: str | None = None
    issuer_tax_id: str | None = None
    receiver_tax_id: str | None = None
    payment_method: str | None = None
    payment_form: str | None = None
    fiscal_status: str
    fiscal_validation_message: str | None = None
    status: SupplierInvoiceStatus
    document_name: str | None = None
    notes: str | None = None
    validated_at: datetime | None = None
    validated_by: int | None = None
    supplier: SupplierRead | None = None
    purchase_order: PurchaseOrderRead | None = None
    items: list[SupplierInvoiceItemRead] = Field(default_factory=list)
    documents: list["SupplierInvoiceDocumentRead"] = Field(default_factory=list)


class SupplierInvoiceDocumentRead(TimestampRead):
    id: int
    company_id: int
    supplier_invoice_id: int
    document_type: str
    original_file_name: str
    content_type: str
    extension: str
    file_size: int
    sha256: str
    validation_status: str
    validation_message: str | None = None
    parsed_data: dict | None = None
    is_active: bool
    uploaded_by: int | None = None
    uploaded_at: datetime


class SupplierInvoiceXMLAnalysis(BaseModel):
    document_type: str = "xml"
    validation_status: str
    validation_message: str | None = None
    parsed_data: dict


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


class FinancialReconciliationCreate(BaseModel):
    supplier_invoice_id: int
    supplier_payment_id: int | None = None
    issue_type: str = Field(default="amount_mismatch", min_length=3, max_length=60)
    resolution_type: FinancialReconciliationResolution
    reason: str = Field(min_length=10, max_length=2000)
    corrected_subtotal: PositiveDecimal | None = None
    corrected_total: PositiveDecimal | None = None
    corrected_discount: NonNegativeDecimal | None = None
    corrected_transferred_taxes: NonNegativeDecimal | None = None
    corrected_withheld_taxes: NonNegativeDecimal | None = None
    amended_purchase_order_subtotal: PositiveDecimal | None = None


class FinancialReconciliationDecision(BaseModel):
    decision: Literal["approved", "rejected"]
    notes: str = Field(min_length=5, max_length=2000)


class FinancialReconciliationRead(TimestampRead):
    id: int
    company_id: int
    project_id: int
    project_name: str
    purchase_order_id: int
    purchase_order_number: str
    supplier_invoice_id: int
    invoice_number: str
    supplier_payment_id: int | None = None
    payment_reference: str | None = None
    case_number: str
    issue_type: str
    resolution_type: FinancialReconciliationResolution
    status: FinancialReconciliationStatus
    reason: str
    proposed_data: dict
    original_snapshot: dict
    decision_notes: str | None = None
    requested_by: int | None = None
    requester_name: str | None = None
    requested_at: datetime
    decided_by: int | None = None
    decider_name: str | None = None
    decided_at: datetime | None = None
    applied_by: int | None = None
    applied_at: datetime | None = None


class ProjectMaterialBudgetApproval(BaseModel):
    notes: str | None = Field(default=None, max_length=1000)


class ProjectMaterialBudgetBaselineRead(TimestampRead):
    id: int
    company_id: int
    project_id: int
    revision: int
    status: str
    currency: str
    total_amount: Decimal
    approved_at: datetime
    approved_by: int | None = None
    notes: str | None = None
    item_count: int = 0


class ProjectFinancialMaterialRow(BaseModel):
    baseline_item_id: int
    house_model_id: int | None = None
    house_model_name: str
    source_code: str | None = None
    description: str
    unit: str
    houses_quantity: Decimal
    quantity_per_house: Decimal
    budget_quantity: Decimal
    ordered_quantity: Decimal
    received_quantity: Decimal
    budget_amount: Decimal
    committed_amount: Decimal
    received_amount: Decimal
    invoiced_amount: Decimal
    paid_amount: Decimal
    available_amount: Decimal
    committed_percent: Decimal
    paid_percent: Decimal
    status: str


class ProjectFinancialProgressRead(BaseModel):
    project_id: int
    project_name: str
    client_name: str
    houses_count: Decimal
    models_count: int
    baseline_id: int | None = None
    baseline_revision: int | None = None
    baseline_status: str | None = None
    baseline_approved_at: datetime | None = None
    budget_amount: Decimal
    committed_amount: Decimal
    received_amount: Decimal
    invoiced_amount: Decimal
    paid_amount: Decimal
    available_amount: Decimal
    over_budget_amount: Decimal
    committed_percent: Decimal
    received_percent: Decimal
    invoiced_percent: Decimal
    paid_percent: Decimal
    purchase_orders_count: int
    invoices_count: int
    payments_count: int
    integrity_issues: list[str] = Field(default_factory=list)


class ProjectFinancialProgressResponse(BaseModel):
    projects: list[ProjectFinancialProgressRead] = Field(default_factory=list)
    selected_project_id: int | None = None
    materials: list[ProjectFinancialMaterialRow] = Field(default_factory=list)


def invoice_due_date(invoice_date: date, payment_terms_days: int) -> date:
    return invoice_date + timedelta(days=payment_terms_days)
