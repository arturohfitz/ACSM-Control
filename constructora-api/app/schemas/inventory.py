from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import NonNegativeDecimal, ORMModel, PositiveDecimal, TimestampRead
from app.schemas.business import SupplySource


InventoryItemStatus = Literal["pending", "partial", "complete", "over_received", "with_issue"]
ReceptionConditionStatus = Literal["ok", "damaged", "incomplete", "extra", "other"]


class ProjectWarehouseBase(BaseModel):
    project_id: int
    name: str = Field(min_length=1, max_length=160)
    location: str | None = None
    notes: str | None = None
    is_active: bool = True


class ProjectWarehouseCreate(ProjectWarehouseBase):
    pass


class ProjectWarehouseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    location: str | None = None
    notes: str | None = None
    is_active: bool | None = None


class ProjectWarehouseRead(ProjectWarehouseBase, TimestampRead):
    id: int
    company_id: int


class ExpectedMaterialItemCreate(BaseModel):
    material_id: int | None = None
    purchase_order_item_id: int | None = None
    source_code: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=255)
    unit: str | None = Field(default=None, max_length=40)
    expected_quantity: PositiveDecimal
    unit_price: NonNegativeDecimal | None = None
    line_total: NonNegativeDecimal | None = None
    delivery_date: date | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def require_description_for_uncatalogued_item(self):
        if self.material_id is None and not self.description:
            raise ValueError("La descripcion es requerida si no se liga a un material")
        if self.material_id is None and not self.unit:
            raise ValueError("La unidad es requerida si no se liga a un material")
        return self


class ExpectedMaterialItemUpdate(BaseModel):
    material_id: int | None = None
    purchase_order_item_id: int | None = None
    source_code: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=255)
    unit: str | None = Field(default=None, max_length=40)
    expected_quantity: PositiveDecimal | None = None
    unit_price: NonNegativeDecimal | None = None
    line_total: NonNegativeDecimal | None = None
    delivery_date: date | None = None
    notes: str | None = None


class ExpectedMaterialItemRead(ORMModel):
    id: int
    company_id: int
    expected_list_id: int
    material_id: int | None = None
    purchase_order_item_id: int | None = None
    source_code: str | None = None
    description: str
    unit: str
    expected_quantity: Decimal
    unit_price: Decimal | None = None
    line_total: Decimal | None = None
    delivery_date: date | None = None
    received_quantity: Decimal
    status: InventoryItemStatus
    notes: str | None = None


class ExpectedMaterialListCreate(BaseModel):
    warehouse_id: int | None = None
    purchase_order_id: int | None = None
    name: str = Field(min_length=1, max_length=200)
    document_number: str | None = Field(default=None, max_length=80)
    supplier_name: str | None = Field(default=None, max_length=200)
    document_date: date | None = None
    delivery_date: date | None = None
    source_document_name: str | None = Field(default=None, max_length=255)
    source_document_hash: str | None = Field(default=None, max_length=64)
    source_notes: str | None = None
    items: list[ExpectedMaterialItemCreate] = Field(default_factory=list)


class ExpectedMaterialListRead(TimestampRead):
    id: int
    company_id: int
    project_id: int
    warehouse_id: int | None = None
    purchase_order_id: int | None = None
    name: str
    document_number: str | None = None
    supplier_name: str | None = None
    document_date: date | None = None
    delivery_date: date | None = None
    source_document_name: str | None = None
    source_document_hash: str | None = None
    source_notes: str | None = None
    status: str
    items: list[ExpectedMaterialItemRead] = Field(default_factory=list)


class MaterialReceptionItemCreate(BaseModel):
    expected_item_id: int
    received_quantity: PositiveDecimal
    condition_status: ReceptionConditionStatus = "ok"
    notes: str | None = None


class MaterialReceptionCreate(BaseModel):
    warehouse_id: int
    expected_list_id: int
    received_at: date | None = None
    delivery_reference: str | None = Field(default=None, max_length=160)
    delivered_by: str | None = Field(default=None, max_length=160)
    received_by: str | None = Field(default=None, max_length=160)
    notes: str | None = None
    items: list[MaterialReceptionItemCreate] = Field(min_length=1)


class MaterialReceptionItemRead(ORMModel):
    id: int
    reception_id: int
    expected_item_id: int
    material_id: int | None = None
    description: str
    unit: str
    received_quantity: Decimal
    condition_status: ReceptionConditionStatus
    notes: str | None = None


class MaterialReceptionRead(TimestampRead):
    id: int
    company_id: int
    project_id: int
    warehouse_id: int
    expected_list_id: int
    received_at: date
    delivery_reference: str | None = None
    delivered_by: str | None = None
    received_by: str | None = None
    notes: str | None = None
    status: str
    items: list[MaterialReceptionItemRead] = Field(default_factory=list)


class InventoryStatusItem(ORMModel):
    expected_item_id: int
    expected_list_id: int
    material_id: int | None = None
    source_code: str | None = None
    description: str
    unit: str
    expected_quantity: Decimal
    unit_price: Decimal | None = None
    line_total: Decimal | None = None
    received_quantity: Decimal
    pending_quantity: Decimal
    over_received_quantity: Decimal
    status: InventoryItemStatus
    notes: str | None = None


class WarehouseStockRead(TimestampRead):
    id: int
    company_id: int
    warehouse_id: int
    expected_item_id: int
    material_id: int | None = None
    description: str
    unit: str
    quantity_on_hand: NonNegativeDecimal


class QuickInventoryLine(BaseModel):
    material_id: int | None = None
    source_code: str | None = Field(default=None, max_length=80)
    description: str = Field(min_length=1, max_length=255)
    unit: str = Field(min_length=1, max_length=40)
    expected_quantity: PositiveDecimal
    unit_price: NonNegativeDecimal | None = None
    line_total: NonNegativeDecimal | None = None
    delivery_date: date | None = None
    received_quantity: NonNegativeDecimal | None = None
    condition_status: ReceptionConditionStatus = "ok"
    notes: str | None = None


class QuickInventoryMetadata(BaseModel):
    document_number: str | None = None
    supplier_name: str | None = None
    document_date: date | None = None
    delivery_date: date | None = None
    source_document_name: str | None = None
    source_document_hash: str | None = None


class QuickInventoryParseTextRequest(BaseModel):
    source_text: str = Field(min_length=1)
    source_document_name: str | None = None


class QuickInventoryParsedDocument(BaseModel):
    metadata: QuickInventoryMetadata
    items: list[QuickInventoryLine]


class QuickInventoryDocumentCreate(BaseModel):
    warehouse_id: int | None = None
    name: str | None = Field(default=None, max_length=200)
    document_number: str | None = Field(default=None, max_length=80)
    supplier_name: str | None = Field(default=None, max_length=200)
    document_date: date | None = None
    delivery_date: date | None = None
    source_document_name: str | None = Field(default=None, max_length=255)
    source_document_hash: str | None = Field(default=None, max_length=64)
    source_notes: str | None = None
    supply_source: SupplySource = "developer"
    include_in_quote: bool = False
    auto_create_materials: bool = True
    update_project_prices: bool = True
    received_at: date | None = None
    received_by: str | None = Field(default=None, max_length=160)
    delivery_reference: str | None = Field(default=None, max_length=160)
    items: list[QuickInventoryLine] = Field(min_length=1)


class QuickInventoryDocumentRead(BaseModel):
    expected_list: ExpectedMaterialListRead
    reception: MaterialReceptionRead | None = None
