from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Quote(TimestampMixin, Base):
    __tablename__ = "quotes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    quote_number: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False)
    subtotal_direct_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    total_waste: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    total_indirects: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    total_profit: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    total_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    valid_until: Mapped[date | None] = mapped_column(Date)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    project: Mapped["Project"] = relationship(back_populates="quotes")
    items: Mapped[list["QuoteItem"]] = relationship(
        back_populates="quote", cascade="all, delete-orphan"
    )


class QuoteItem(Base):
    __tablename__ = "quote_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id", ondelete="CASCADE"), nullable=False)
    project_house_model_id: Mapped[int] = mapped_column(
        ForeignKey("project_house_models.id"), nullable=False, index=True
    )
    house_model_id: Mapped[int] = mapped_column(ForeignKey("house_models.id"), nullable=False)
    construction_concept_id: Mapped[int] = mapped_column(
        ForeignKey("construction_concepts.id"), nullable=False
    )
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    material_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    labor_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    equipment_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    waste_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    indirect_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    profit_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    total_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)

    quote: Mapped[Quote] = relationship(back_populates="items")
    project_house_model: Mapped["ProjectHouseModel"] = relationship(back_populates="quote_items")
    construction_concept: Mapped["ConstructionConcept"] = relationship(back_populates="quote_items")
