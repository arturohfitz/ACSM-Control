from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel, PositiveDecimal, TimestampRead
from app.schemas.purchasing import SupplierRFQRead, UserSummaryRead


MaterialRequisitionStatus = Literal[
    "submitted",
    "in_review",
    "approved",
    "rejected",
    "converted_to_rfq",
    "ordered_to_suppliers",
    "cancelled",
]
MaterialRequisitionPriority = Literal["low", "normal", "high", "urgent"]


class AvailableRequirementRead(BaseModel):
    id: int
    house_model_id: int
    house_model_name: str
    material_id: int | None = None
    source_code: str | None = None
    description: str
    unit: str
    quantity_per_house: Decimal
    assigned_houses: Decimal
    total_required: Decimal
    validation_status: str
    family: str | None = None


class MaterialRequisitionItemCreate(BaseModel):
    house_model_material_requirement_id: int
    requested_quantity: PositiveDecimal
    notes: str | None = None


class MaterialRequisitionItemRead(ORMModel):
    id: int
    requisition_id: int
    house_model_material_requirement_id: int | None = None
    material_id: int | None = None
    supplier_rfq_item_id: int | None = None
    source_code: str | None = None
    description: str
    unit: str
    requested_quantity: Decimal
    approved_quantity: Decimal | None = None
    status: str
    notes: str | None = None


class MaterialRequisitionCreate(BaseModel):
    project_id: int
    house_model_id: int
    title: str = Field(min_length=1, max_length=200)
    priority: MaterialRequisitionPriority = "normal"
    required_date: date | None = None
    notes: str | None = None
    items: list[MaterialRequisitionItemCreate] = Field(min_length=1)


class MaterialRequisitionReview(BaseModel):
    decision: Literal["approved", "rejected"]
    review_notes: str | None = None


class MaterialRequisitionConvertToRFQ(BaseModel):
    supplier_ids: list[int] = Field(min_length=1)
    title: str | None = Field(default=None, max_length=200)
    required_by: date | None = None
    response_deadline: date | None = None
    notes: str | None = None


class MaterialRequisitionRead(TimestampRead):
    id: int
    company_id: int
    client_id: int
    project_id: int
    house_model_id: int
    requested_by_user_id: int | None = None
    reviewed_by_user_id: int | None = None
    converted_rfq_id: int | None = None
    requisition_number: str
    title: str
    status: MaterialRequisitionStatus
    priority: MaterialRequisitionPriority
    required_date: date | None = None
    submitted_at: datetime | None = None
    reviewed_at: datetime | None = None
    notes: str | None = None
    review_notes: str | None = None
    requested_by: UserSummaryRead | None = None
    reviewed_by: UserSummaryRead | None = None
    items: list[MaterialRequisitionItemRead] = Field(default_factory=list)


class MaterialRequisitionConvertResult(BaseModel):
    requisition: MaterialRequisitionRead
    rfq: SupplierRFQRead
