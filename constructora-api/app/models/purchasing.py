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
    quotes: Mapped[list["SupplierQuote"]] = relationship(back_populates="supplier")
    purchase_orders: Mapped[list["PurchaseOrder"]] = relationship(back_populates="supplier")
    invoices: Mapped[list["SupplierInvoice"]] = relationship(back_populates="supplier")


class SupplierRFQ(TimestampMixin, Base):
    __tablename__ = "supplier_rfqs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    warehouse_id: Mapped[int | None] = mapped_column(ForeignKey("project_warehouses.id"), index=True)
    rfq_number: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False)
    required_by: Mapped[date | None] = mapped_column(Date)
    response_deadline: Mapped[date | None] = mapped_column(Date)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    project: Mapped["Project"] = relationship()
    warehouse: Mapped["ProjectWarehouse | None"] = relationship()
    items: Mapped[list["SupplierRFQItem"]] = relationship(
        back_populates="rfq", cascade="all, delete-orphan"
    )
    supplier_links: Mapped[list["SupplierRFQSupplier"]] = relationship(
        back_populates="rfq", cascade="all, delete-orphan"
    )
    quotes: Mapped[list["SupplierQuote"]] = relationship(back_populates="rfq")
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
    material_id: Mapped[int | None] = mapped_column(ForeignKey("materials.id"), index=True)
    source_code: Mapped[str | None] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    rfq: Mapped[SupplierRFQ] = relationship(back_populates="items")
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
    notes: Mapped[str | None] = mapped_column(Text)

    rfq: Mapped[SupplierRFQ] = relationship(back_populates="supplier_links")
    supplier: Mapped[Supplier] = relationship(back_populates="rfq_suppliers")


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
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
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
    issued_at: Mapped[date] = mapped_column(Date, nullable=False)
    expected_delivery_date: Mapped[date | None] = mapped_column(Date)
    payment_terms_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    project: Mapped["Project"] = relationship()
    warehouse: Mapped["ProjectWarehouse | None"] = relationship()
    supplier: Mapped[Supplier] = relationship(back_populates="purchase_orders")
    supplier_quote: Mapped[SupplierQuote | None] = relationship(back_populates="purchase_order")
    items: Mapped[list["PurchaseOrderItem"]] = relationship(
        back_populates="purchase_order", cascade="all, delete-orphan"
    )
    invoices: Mapped[list["SupplierInvoice"]] = relationship(back_populates="purchase_order")


class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    purchase_order_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rfq_item_id: Mapped[int | None] = mapped_column(ForeignKey("supplier_rfq_items.id"), index=True)
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
    material: Mapped["Material | None"] = relationship()


class SupplierInvoice(TimestampMixin, Base):
    __tablename__ = "supplier_invoices"

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
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="received", nullable=False)
    document_name: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    validated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    supplier: Mapped[Supplier] = relationship(back_populates="invoices")
    purchase_order: Mapped[PurchaseOrder] = relationship(back_populates="invoices")
    payments: Mapped[list["SupplierPayment"]] = relationship(back_populates="invoice")


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
