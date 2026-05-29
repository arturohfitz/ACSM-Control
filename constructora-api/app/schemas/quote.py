from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.common import NonNegativeDecimal, ORMModel, Percent, QuoteStatus, TimestampRead


class QuoteCreate(BaseModel):
    company_id: int | None = None
    project_id: int
    quote_number: str | None = Field(default=None, max_length=80)
    version: int = Field(default=1, ge=1)
    status: QuoteStatus = "draft"
    notes: str | None = None
    valid_until: date | None = None


class QuoteUpdate(BaseModel):
    status: QuoteStatus | None = None
    notes: str | None = None
    valid_until: date | None = None


class QuoteItemRead(ORMModel):
    id: int
    quote_id: int
    project_house_model_id: int
    house_model_id: int
    construction_concept_id: int
    description: str
    unit: str
    quantity: Decimal
    material_cost: Decimal
    labor_cost: Decimal
    equipment_cost: Decimal
    waste_amount: Decimal
    indirect_amount: Decimal
    profit_amount: Decimal
    total_cost: Decimal
    total_price: Decimal


class QuoteRead(TimestampRead):
    id: int
    company_id: int
    project_id: int
    quote_number: str
    version: int
    status: QuoteStatus
    subtotal_direct_cost: Decimal
    total_waste: Decimal
    total_indirects: Decimal
    total_profit: Decimal
    total_price: Decimal
    notes: str | None = None
    valid_until: date | None = None
    created_by: int | None = None
    approved_by: int | None = None
    approved_at: datetime | None = None
    items: list[QuoteItemRead] = Field(default_factory=list)


class QuoteCalculateRequest(BaseModel):
    notes: str | None = None
    valid_until: date | None = None
    profit_percent: Percent | None = None


class QuoteTotals(ORMModel):
    subtotal_direct_cost: NonNegativeDecimal
    total_waste: NonNegativeDecimal
    total_indirects: NonNegativeDecimal
    total_profit: NonNegativeDecimal
    total_price: NonNegativeDecimal
