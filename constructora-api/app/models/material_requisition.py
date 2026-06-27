from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class MaterialRequisition(TimestampMixin, Base):
    __tablename__ = "material_requisitions"
    __table_args__ = (
        UniqueConstraint("company_id", "requisition_number", name="uq_material_requisition_number"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    house_model_id: Mapped[int] = mapped_column(ForeignKey("house_models.id"), nullable=False, index=True)
    requested_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    converted_rfq_id: Mapped[int | None] = mapped_column(ForeignKey("supplier_rfqs.id"), index=True)
    requisition_number: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="submitted", nullable=False, index=True)
    priority: Mapped[str] = mapped_column(String(40), default="normal", nullable=False)
    required_date: Mapped[date | None] = mapped_column(Date)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    review_notes: Mapped[str | None] = mapped_column(Text)

    client: Mapped["Client"] = relationship()
    project: Mapped["Project"] = relationship()
    house_model: Mapped["HouseModel"] = relationship()
    requested_by: Mapped["User | None"] = relationship(foreign_keys=[requested_by_user_id])
    reviewed_by: Mapped["User | None"] = relationship(foreign_keys=[reviewed_by_user_id])
    converted_rfq: Mapped["SupplierRFQ | None"] = relationship()
    items: Mapped[list["MaterialRequisitionItem"]] = relationship(
        back_populates="requisition", cascade="all, delete-orphan"
    )


class MaterialRequisitionItem(Base):
    __tablename__ = "material_requisition_items"
    __table_args__ = (
        Index("ix_mr_items_requirement_id", "house_model_material_requirement_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    requisition_id: Mapped[int] = mapped_column(
        ForeignKey("material_requisitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    house_model_material_requirement_id: Mapped[int | None] = mapped_column(
        ForeignKey("house_model_material_requirements.id")
    )
    material_id: Mapped[int | None] = mapped_column(ForeignKey("materials.id"), index=True)
    supplier_rfq_item_id: Mapped[int | None] = mapped_column(ForeignKey("supplier_rfq_items.id"), index=True)
    source_code: Mapped[str | None] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    requested_unit: Mapped[str | None] = mapped_column(String(40))
    requested_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    approved_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text)

    requisition: Mapped[MaterialRequisition] = relationship(back_populates="items")
    requirement: Mapped["HouseModelMaterialRequirement | None"] = relationship()
    material: Mapped["Material | None"] = relationship()
    supplier_rfq_item: Mapped["SupplierRFQItem | None"] = relationship()
