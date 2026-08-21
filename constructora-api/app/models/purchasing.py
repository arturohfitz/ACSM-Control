from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Supplier(TimestampMixin, Base):
    __tablename__ = "suppliers"
    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_suppliers_company_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    legal_name: Mapped[str | None] = mapped_column(String(255))
    tax_id: Mapped[str | None] = mapped_column(String(80))
    contact_name: Mapped[str | None] = mapped_column(String(200))
    contact_email: Mapped[str | None] = mapped_column(String(255))
    contact_phone: Mapped[str | None] = mapped_column(String(80))
    address: Mapped[str | None] = mapped_column(Text)
    payment_terms_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    average_delivery_days: Mapped[int | None] = mapped_column(Integer)
    material_categories: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    rfq_suppliers: Mapped[list["SupplierRFQSupplier"]] = relationship(back_populates="supplier")
    agreements: Mapped[list["SupplierAgreement"]] = relationship(back_populates="supplier")
    quotes: Mapped[list["SupplierQuote"]] = relationship(back_populates="supplier")
    purchase_orders: Mapped[list["PurchaseOrder"]] = relationship(back_populates="supplier")
    invoices: Mapped[list["SupplierInvoice"]] = relationship(back_populates="supplier")


class SupplierAgreement(TimestampMixin, Base):
    __tablename__ = "supplier_agreements"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "supplier_id",
            "client_id",
            "house_model_id",
            "agreement_number",
            name="uq_supplier_agreements_scope_number",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False, index=True)
    house_model_id: Mapped[int] = mapped_column(ForeignKey("house_models.id"), nullable=False, index=True)
    agreement_number: Mapped[str | None] = mapped_column(String(120))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False, index=True)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_until: Mapped[date | None] = mapped_column(Date)
    payment_terms_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    average_delivery_days: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approval_status: Mapped[str] = mapped_column(String(40), default="requested", nullable=False, index=True)
    request_notes: Mapped[str | None] = mapped_column(Text)
    decision_notes: Mapped[str | None] = mapped_column(Text)
    requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    supplier: Mapped[Supplier] = relationship(back_populates="agreements")
    client: Mapped["Client"] = relationship()
    house_model: Mapped["HouseModel"] = relationship()
    items: Mapped[list["SupplierAgreementItem"]] = relationship(
        back_populates="agreement", cascade="all, delete-orphan"
    )
    creator: Mapped["User | None"] = relationship(foreign_keys=[created_by])
    decider: Mapped["User | None"] = relationship(foreign_keys=[decided_by])


class SupplierAgreementItem(TimestampMixin, Base):
    __tablename__ = "supplier_agreement_items"
    __table_args__ = (
        UniqueConstraint("agreement_id", "material_id", name="uq_supplier_agreement_item_material"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agreement_id: Mapped[int] = mapped_column(
        ForeignKey("supplier_agreements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"), nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="MXN", nullable=False)
    delivery_days: Mapped[int | None] = mapped_column(Integer)
    min_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    max_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text)

    agreement: Mapped[SupplierAgreement] = relationship(back_populates="items")
    material: Mapped["Material"] = relationship()


class SupplierRFQ(TimestampMixin, Base):
    __tablename__ = "supplier_rfqs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    warehouse_id: Mapped[int | None] = mapped_column(ForeignKey("project_warehouses.id"), index=True)
    rfq_number: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False)
    request_type: Mapped[str] = mapped_column(String(40), default="standard", nullable=False, index=True)
    supplier_agreement_id: Mapped[int | None] = mapped_column(
        ForeignKey("supplier_agreements.id"), index=True
    )
    required_by: Mapped[date | None] = mapped_column(Date)
    response_deadline: Mapped[date | None] = mapped_column(Date)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    project: Mapped["Project"] = relationship()
    warehouse: Mapped["ProjectWarehouse | None"] = relationship()
    supplier_agreement: Mapped["SupplierAgreement | None"] = relationship()
    items: Mapped[list["SupplierRFQItem"]] = relationship(
        back_populates="rfq", cascade="all, delete-orphan"
    )
    supplier_links: Mapped[list["SupplierRFQSupplier"]] = relationship(
        back_populates="rfq", cascade="all, delete-orphan"
    )
    quotes: Mapped[list["SupplierQuote"]] = relationship(back_populates="rfq")
    quote_drafts: Mapped[list["SupplierQuoteDraft"]] = relationship(
        back_populates="rfq", cascade="all, delete-orphan"
    )
    creator: Mapped["User | None"] = relationship(foreign_keys=[created_by])


class SupplierRFQExceptionRequest(TimestampMixin, Base):
    __tablename__ = "supplier_rfq_exception_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    rfq_id: Mapped[int | None] = mapped_column(ForeignKey("supplier_rfqs.id"), index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="requested", nullable=False, index=True)
    required_by: Mapped[date | None] = mapped_column(Date)
    response_deadline: Mapped[date | None] = mapped_column(Date)
    supplier_count: Mapped[int] = mapped_column(Integer, nullable=False)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False)
    payload_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    payload_fingerprint: Mapped[str | None] = mapped_column(String(64), index=True)
    request_notes: Mapped[str] = mapped_column(Text, nullable=False)
    decision_notes: Mapped[str | None] = mapped_column(Text)
    requested_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    project: Mapped["Project"] = relationship()
    rfq: Mapped["SupplierRFQ | None"] = relationship()
    requester: Mapped["User | None"] = relationship(foreign_keys=[requested_by])
    decider: Mapped["User | None"] = relationship(foreign_keys=[decided_by])


class SupplierRFQItem(Base):
    __tablename__ = "supplier_rfq_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rfq_id: Mapped[int] = mapped_column(
        ForeignKey("supplier_rfqs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    house_model_id: Mapped[int | None] = mapped_column(ForeignKey("house_models.id"), index=True)
    house_model_material_requirement_id: Mapped[int | None] = mapped_column(
        ForeignKey("house_model_material_requirements.id"), index=True
    )
    material_id: Mapped[int | None] = mapped_column(ForeignKey("materials.id"), index=True)
    source_code: Mapped[str | None] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    rfq: Mapped[SupplierRFQ] = relationship(back_populates="items")
    house_model: Mapped["HouseModel | None"] = relationship()
    house_model_material_requirement: Mapped["HouseModelMaterialRequirement | None"] = relationship()
    material: Mapped["Material | None"] = relationship()
    quote_items: Mapped[list["SupplierQuoteItem"]] = relationship(back_populates="rfq_item")


class SupplierRFQSupplier(Base):
    __tablename__ = "supplier_rfq_suppliers"
    __table_args__ = (
        UniqueConstraint("rfq_id", "supplier_id", name="uq_supplier_rfq_supplier_pair"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rfq_id: Mapped[int] = mapped_column(
        ForeignKey("supplier_rfqs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), default="invited", nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    portal_token_hash: Mapped[str | None] = mapped_column(String(128), unique=True, index=True)
    portal_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    portal_last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)

    rfq: Mapped[SupplierRFQ] = relationship(back_populates="supplier_links")
    supplier: Mapped[Supplier] = relationship(back_populates="rfq_suppliers")
    quote_uploads: Mapped[list["SupplierQuoteUpload"]] = relationship(
        back_populates="rfq_supplier", cascade="all, delete-orphan"
    )


class SupplierQuoteUpload(TimestampMixin, Base):
    __tablename__ = "supplier_quote_uploads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    rfq_id: Mapped[int] = mapped_column(ForeignKey("supplier_rfqs.id", ondelete="CASCADE"), nullable=False, index=True)
    rfq_supplier_id: Mapped[int] = mapped_column(
        ForeignKey("supplier_rfq_suppliers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False, index=True)
    quote_number: Mapped[str | None] = mapped_column(String(120))
    original_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(120))
    file_extension: Mapped[str] = mapped_column(String(16), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), default="received", nullable=False, index=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    security_notes: Mapped[str | None] = mapped_column(Text)

    rfq: Mapped[SupplierRFQ] = relationship()
    rfq_supplier: Mapped[SupplierRFQSupplier] = relationship(back_populates="quote_uploads")
    supplier: Mapped[Supplier] = relationship()
    draft: Mapped["SupplierQuoteDraft | None"] = relationship(back_populates="upload")


class SupplierQuoteDraft(TimestampMixin, Base):
    __tablename__ = "supplier_quote_drafts"
    __table_args__ = (
        UniqueConstraint("upload_id", name="uq_supplier_quote_drafts_upload"),
        UniqueConstraint("supplier_quote_id", name="uq_supplier_quote_drafts_quote"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    rfq_id: Mapped[int] = mapped_column(
        ForeignKey("supplier_rfqs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rfq_supplier_id: Mapped[int] = mapped_column(
        ForeignKey("supplier_rfq_suppliers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False, index=True)
    upload_id: Mapped[int | None] = mapped_column(
        ForeignKey("supplier_quote_uploads.id", ondelete="SET NULL"), index=True
    )
    supplier_quote_id: Mapped[int | None] = mapped_column(
        ForeignKey("supplier_quotes.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[str] = mapped_column(String(40), default="review_required", nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(40), default="portal", nullable=False)
    parser_version: Mapped[str | None] = mapped_column(String(40))
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=1, nullable=False)
    quote_number: Mapped[str | None] = mapped_column(String(80))
    received_at: Mapped[date | None] = mapped_column(Date)
    valid_until: Mapped[date | None] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(String(3), default="MXN", nullable=False)
    delivery_days: Mapped[int | None] = mapped_column(Integer)
    payment_terms_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    discount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    shipping_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    validation_errors: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    detected_supplier_name: Mapped[str | None] = mapped_column(String(255))
    detected_supplier_tax_id: Mapped[str | None] = mapped_column(String(80))
    detected_supplier_email: Mapped[str | None] = mapped_column(String(255))
    supplier_match_status: Mapped[str] = mapped_column(
        String(40), default="not_detected", nullable=False
    )
    supplier_match_confidence: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), default=0, nullable=False
    )
    detected_rfq_number: Mapped[str | None] = mapped_column(String(80))
    document_subtotal: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    document_tax_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    document_total: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    extraction_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    confirmed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    rfq: Mapped[SupplierRFQ] = relationship(back_populates="quote_drafts")
    rfq_supplier: Mapped[SupplierRFQSupplier] = relationship()
    supplier: Mapped[Supplier] = relationship()
    upload: Mapped[SupplierQuoteUpload | None] = relationship(back_populates="draft")
    supplier_quote: Mapped["SupplierQuote | None"] = relationship()
    confirmer: Mapped["User | None"] = relationship(foreign_keys=[confirmed_by])
    items: Mapped[list["SupplierQuoteDraftItem"]] = relationship(
        back_populates="draft", cascade="all, delete-orphan"
    )


class SupplierQuoteDraftItem(Base):
    __tablename__ = "supplier_quote_draft_items"
    __table_args__ = (
        UniqueConstraint("draft_id", "rfq_item_id", name="uq_supplier_quote_draft_items_rfq_item"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    draft_id: Mapped[int] = mapped_column(
        ForeignKey("supplier_quote_drafts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rfq_item_id: Mapped[int] = mapped_column(
        ForeignKey("supplier_rfq_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    material_id: Mapped[int | None] = mapped_column(ForeignKey("materials.id"), index=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    delivery_days: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=1, nullable=False)
    match_method: Mapped[str] = mapped_column(String(40), default="rfq_item_id", nullable=False)

    draft: Mapped[SupplierQuoteDraft] = relationship(back_populates="items")
    rfq_item: Mapped[SupplierRFQItem] = relationship()
    material: Mapped["Material | None"] = relationship()


class SupplierQuote(TimestampMixin, Base):
    __tablename__ = "supplier_quotes"
    __table_args__ = (
        UniqueConstraint("rfq_id", "supplier_id", name="uq_supplier_quotes_rfq_supplier"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    rfq_id: Mapped[int] = mapped_column(ForeignKey("supplier_rfqs.id"), nullable=False, index=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False, index=True)
    quote_number: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(40), default="received", nullable=False)
    received_at: Mapped[date | None] = mapped_column(Date)
    valid_until: Mapped[date | None] = mapped_column(Date)
    delivery_days: Mapped[int | None] = mapped_column(Integer)
    payment_terms_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="MXN", nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    discount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    shipping_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    attachment_name: Mapped[str | None] = mapped_column(String(255))

    rfq: Mapped[SupplierRFQ] = relationship(back_populates="quotes")
    supplier: Mapped[Supplier] = relationship(back_populates="quotes")
    items: Mapped[list["SupplierQuoteItem"]] = relationship(
        back_populates="supplier_quote", cascade="all, delete-orphan"
    )
    purchase_order: Mapped["PurchaseOrder | None"] = relationship(back_populates="supplier_quote")
    approval: Mapped["SupplierQuoteApproval | None"] = relationship(back_populates="supplier_quote")


class SupplierQuoteApproval(TimestampMixin, Base):
    __tablename__ = "supplier_quote_approvals"
    __table_args__ = (
        UniqueConstraint("supplier_quote_id", name="uq_supplier_quote_approvals_quote"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    rfq_id: Mapped[int] = mapped_column(ForeignKey("supplier_rfqs.id"), nullable=False, index=True)
    supplier_quote_id: Mapped[int] = mapped_column(
        ForeignKey("supplier_quotes.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(40), default="requested", nullable=False, index=True)
    request_notes: Mapped[str | None] = mapped_column(Text)
    decision_notes: Mapped[str | None] = mapped_column(Text)
    requested_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    rfq: Mapped[SupplierRFQ] = relationship()
    supplier_quote: Mapped[SupplierQuote] = relationship(back_populates="approval")
    requester: Mapped["User | None"] = relationship(foreign_keys=[requested_by])
    decider: Mapped["User | None"] = relationship(foreign_keys=[decided_by])


class SupplierQuoteItem(Base):
    __tablename__ = "supplier_quote_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    supplier_quote_id: Mapped[int] = mapped_column(
        ForeignKey("supplier_quotes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rfq_item_id: Mapped[int] = mapped_column(ForeignKey("supplier_rfq_items.id"), nullable=False)
    material_id: Mapped[int | None] = mapped_column(ForeignKey("materials.id"), index=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    delivery_days: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)

    supplier_quote: Mapped[SupplierQuote] = relationship(back_populates="items")
    rfq_item: Mapped[SupplierRFQItem] = relationship(back_populates="quote_items")
    material: Mapped["Material | None"] = relationship()


class PurchaseOrder(TimestampMixin, Base):
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    warehouse_id: Mapped[int | None] = mapped_column(ForeignKey("project_warehouses.id"), index=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False, index=True)
    supplier_quote_id: Mapped[int | None] = mapped_column(
        ForeignKey("supplier_quotes.id"), unique=True, index=True
    )
    po_number: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="issued", nullable=False)
    billing_mode: Mapped[str] = mapped_column(String(40), default="single", nullable=False)
    issued_at: Mapped[date] = mapped_column(Date, nullable=False)
    expected_delivery_date: Mapped[date | None] = mapped_column(Date)
    payment_terms_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invoice_portal_token_hash: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    invoice_portal_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invoice_portal_last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    project: Mapped["Project"] = relationship()
    warehouse: Mapped["ProjectWarehouse | None"] = relationship()
    supplier: Mapped[Supplier] = relationship(back_populates="purchase_orders")
    supplier_quote: Mapped[SupplierQuote | None] = relationship(back_populates="purchase_order")
    items: Mapped[list["PurchaseOrderItem"]] = relationship(
        back_populates="purchase_order", cascade="all, delete-orphan"
    )
    invoices: Mapped[list["SupplierInvoice"]] = relationship(back_populates="purchase_order")
    invoice_submissions: Mapped[list["SupplierInvoiceSubmission"]] = relationship(
        back_populates="purchase_order", cascade="all, delete-orphan"
    )


class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    purchase_order_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rfq_item_id: Mapped[int | None] = mapped_column(ForeignKey("supplier_rfq_items.id"), index=True)
    house_model_id: Mapped[int | None] = mapped_column(ForeignKey("house_models.id"), index=True)
    house_model_material_requirement_id: Mapped[int | None] = mapped_column(
        ForeignKey("house_model_material_requirements.id"), index=True
    )
    material_id: Mapped[int | None] = mapped_column(ForeignKey("materials.id"), index=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    quantity_ordered: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    received_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    purchase_order: Mapped[PurchaseOrder] = relationship(back_populates="items")
    house_model: Mapped["HouseModel | None"] = relationship()
    house_model_material_requirement: Mapped["HouseModelMaterialRequirement | None"] = relationship()
    material: Mapped["Material | None"] = relationship()


class SupplierInvoice(TimestampMixin, Base):
    __tablename__ = "supplier_invoices"
    __table_args__ = (
        UniqueConstraint("company_id", "fiscal_uuid", name="uq_supplier_invoices_company_fiscal_uuid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False, index=True)
    purchase_order_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_orders.id"), nullable=False, index=True
    )
    invoice_number: Mapped[str] = mapped_column(String(100), nullable=False)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    subtotal: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    discount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    transferred_taxes: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    withheld_taxes: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="MXN", nullable=False)
    exchange_rate: Mapped[Decimal | None] = mapped_column(Numeric(14, 6))
    fiscal_uuid: Mapped[str | None] = mapped_column(String(40), index=True)
    series: Mapped[str | None] = mapped_column(String(40))
    issuer_tax_id: Mapped[str | None] = mapped_column(String(20), index=True)
    receiver_tax_id: Mapped[str | None] = mapped_column(String(20), index=True)
    payment_method: Mapped[str | None] = mapped_column(String(10))
    payment_form: Mapped[str | None] = mapped_column(String(10))
    fiscal_status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)
    fiscal_validation_message: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="document_pending", nullable=False)
    document_name: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    validated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    supplier: Mapped[Supplier] = relationship(back_populates="invoices")
    purchase_order: Mapped[PurchaseOrder] = relationship(back_populates="invoices")
    items: Mapped[list["SupplierInvoiceItem"]] = relationship(
        back_populates="supplier_invoice", cascade="all, delete-orphan"
    )
    payments: Mapped[list["SupplierPayment"]] = relationship(back_populates="invoice")
    documents: Mapped[list["SupplierInvoiceDocument"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )


class SupplierInvoiceDocument(TimestampMixin, Base):
    __tablename__ = "supplier_invoice_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    supplier_invoice_id: Mapped[int] = mapped_column(
        ForeignKey("supplier_invoices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    original_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(700), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    extension: Mapped[str] = mapped_column(String(20), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    validation_status: Mapped[str] = mapped_column(String(40), default="uploaded", nullable=False)
    validation_message: Mapped[str | None] = mapped_column(Text)
    parsed_data: Mapped[dict | None] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    invoice: Mapped[SupplierInvoice] = relationship(back_populates="documents")


class SupplierInvoiceSubmission(TimestampMixin, Base):
    __tablename__ = "supplier_invoice_submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    purchase_order_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False, index=True)
    invoice_number: Mapped[str | None] = mapped_column(String(100))
    invoice_date: Mapped[date | None] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(String(10), default="MXN", nullable=False)
    subtotal: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    total: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    fiscal_uuid: Mapped[str | None] = mapped_column(String(40), index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="review_required", nullable=False, index=True)
    validation_message: Mapped[str | None] = mapped_column(Text)
    parsed_data: Mapped[dict | None] = mapped_column(JSON)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    supplier_invoice_id: Mapped[int | None] = mapped_column(
        ForeignKey("supplier_invoices.id"), unique=True, index=True
    )

    purchase_order: Mapped[PurchaseOrder] = relationship(back_populates="invoice_submissions")
    supplier: Mapped[Supplier] = relationship()
    invoice: Mapped[SupplierInvoice | None] = relationship()
    documents: Mapped[list["SupplierInvoiceSubmissionDocument"]] = relationship(
        back_populates="submission", cascade="all, delete-orphan"
    )


class SupplierInvoiceSubmissionDocument(TimestampMixin, Base):
    __tablename__ = "supplier_invoice_submission_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_id: Mapped[int] = mapped_column(
        ForeignKey("supplier_invoice_submissions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    original_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(700), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    extension: Mapped[str] = mapped_column(String(20), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    validation_status: Mapped[str] = mapped_column(String(40), default="uploaded", nullable=False)
    validation_message: Mapped[str | None] = mapped_column(Text)
    parsed_data: Mapped[dict | None] = mapped_column(JSON)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    submission: Mapped[SupplierInvoiceSubmission] = relationship(back_populates="documents")


class SupplierInvoiceItem(Base):
    __tablename__ = "supplier_invoice_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    supplier_invoice_id: Mapped[int] = mapped_column(
        ForeignKey("supplier_invoices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    purchase_order_item_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_order_items.id"), nullable=False, index=True
    )
    material_id: Mapped[int | None] = mapped_column(ForeignKey("materials.id"), index=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    supplier_invoice: Mapped[SupplierInvoice] = relationship(back_populates="items")
    purchase_order_item: Mapped[PurchaseOrderItem] = relationship()
    material: Mapped["Material | None"] = relationship()


class SupplierPayment(TimestampMixin, Base):
    __tablename__ = "supplier_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    supplier_invoice_id: Mapped[int] = mapped_column(
        ForeignKey("supplier_invoices.id"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    scheduled_date: Mapped[date | None] = mapped_column(Date)
    paid_at: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(40), default="scheduled", nullable=False)
    reference: Mapped[str | None] = mapped_column(String(160))
    proof_document_name: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    invoice: Mapped[SupplierInvoice] = relationship(back_populates="payments")


class FinancialReconciliationCase(TimestampMixin, Base):
    __tablename__ = "financial_reconciliation_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    purchase_order_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_orders.id"), nullable=False, index=True
    )
    supplier_invoice_id: Mapped[int] = mapped_column(
        ForeignKey("supplier_invoices.id"), nullable=False, index=True
    )
    supplier_payment_id: Mapped[int | None] = mapped_column(
        ForeignKey("supplier_payments.id"), index=True
    )
    case_number: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    issue_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    resolution_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), default="requested", nullable=False, index=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    original_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    decision_notes: Mapped[str | None] = mapped_column(Text)
    requested_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    applied_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    project: Mapped["Project"] = relationship()
    purchase_order: Mapped[PurchaseOrder] = relationship()
    supplier_invoice: Mapped[SupplierInvoice] = relationship()
    supplier_payment: Mapped[SupplierPayment | None] = relationship()
    requester: Mapped["User | None"] = relationship(foreign_keys=[requested_by])
    decider: Mapped["User | None"] = relationship(foreign_keys=[decided_by])
    applier: Mapped["User | None"] = relationship(foreign_keys=[applied_by])


class SupplierInvoiceCorrection(TimestampMixin, Base):
    __tablename__ = "supplier_invoice_corrections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    supplier_invoice_id: Mapped[int] = mapped_column(
        ForeignKey("supplier_invoices.id"), nullable=False, index=True
    )
    reconciliation_case_id: Mapped[int] = mapped_column(
        ForeignKey("financial_reconciliation_cases.id"), nullable=False, unique=True, index=True
    )
    before_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    after_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    applied_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PurchaseOrderAmendment(TimestampMixin, Base):
    __tablename__ = "purchase_order_amendments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    purchase_order_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_orders.id"), nullable=False, index=True
    )
    reconciliation_case_id: Mapped[int] = mapped_column(
        ForeignKey("financial_reconciliation_cases.id"), nullable=False, unique=True, index=True
    )
    previous_subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    new_subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    difference: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    applied_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SupplierPaymentReversal(TimestampMixin, Base):
    __tablename__ = "supplier_payment_reversals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    supplier_payment_id: Mapped[int] = mapped_column(
        ForeignKey("supplier_payments.id"), nullable=False, unique=True, index=True
    )
    reconciliation_case_id: Mapped[int] = mapped_column(
        ForeignKey("financial_reconciliation_cases.id"), nullable=False, unique=True, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    applied_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
