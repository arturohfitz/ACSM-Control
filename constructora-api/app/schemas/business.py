from datetime import date
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import (
    NonNegativeDecimal,
    ORMModel,
    Percent,
    PositiveDecimal,
    ProjectStatus,
    QuantityFormulaType,
    TimestampRead,
)


SupplySource = Literal["constructor", "developer", "third_party"]
HouseModelDocumentType = Literal["explosion", "budget"]
ReviewStatus = Literal["pending", "validated", "ignored"]


class HouseModelMaterialRequirementRead(ORMModel):
    id: int
    company_id: int
    client_id: int
    house_model_id: int
    document_id: int
    material_id: int | None = None
    source_code: str | None = None
    description: str
    unit: str
    quantity_per_house: NonNegativeDecimal
    unit_cost_reference: NonNegativeDecimal | None = None
    total_cost_reference: NonNegativeDecimal | None = None
    family: str | None = None
    validation_status: ReviewStatus = "pending"
    sort_order: int
    notes: str | None = None


class HouseModelBudgetActivityRead(ORMModel):
    id: int
    company_id: int
    client_id: int
    house_model_id: int
    document_id: int
    construction_concept_id: int | None = None
    chapter_code: str | None = None
    chapter_name: str | None = None
    source_code: str | None = None
    description: str
    unit: str
    quantity_per_house: NonNegativeDecimal
    unit_price_reference: NonNegativeDecimal | None = None
    total_price_reference: NonNegativeDecimal | None = None
    validation_status: ReviewStatus = "pending"
    sort_order: int
    notes: str | None = None


class HouseModelMaterialRequirementUpdate(BaseModel):
    material_id: int | None = None
    description: str | None = Field(default=None, min_length=1, max_length=255)
    unit: str | None = Field(default=None, min_length=1, max_length=40)
    quantity_per_house: NonNegativeDecimal | None = None
    unit_cost_reference: NonNegativeDecimal | None = None
    total_cost_reference: NonNegativeDecimal | None = None
    family: str | None = Field(default=None, max_length=120)
    validation_status: ReviewStatus | None = None
    notes: str | None = None


class HouseModelBudgetActivityUpdate(BaseModel):
    construction_concept_id: int | None = None
    chapter_code: str | None = Field(default=None, max_length=40)
    chapter_name: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, min_length=1)
    unit: str | None = Field(default=None, min_length=1, max_length=40)
    quantity_per_house: NonNegativeDecimal | None = None
    unit_price_reference: NonNegativeDecimal | None = None
    total_price_reference: NonNegativeDecimal | None = None
    validation_status: ReviewStatus | None = None
    notes: str | None = None


class HouseModelDocumentRead(TimestampRead):
    id: int
    company_id: int
    client_id: int
    house_model_id: int
    document_type: HouseModelDocumentType
    version: str | None = None
    source_code: str | None = None
    source_date: date | None = None
    file_name: str
    file_hash: str
    status: str
    total_items: int
    total_amount: NonNegativeDecimal | None = None
    notes: str | None = None


class HouseModelDocumentDetail(HouseModelDocumentRead):
    material_requirements: list[HouseModelMaterialRequirementRead] = Field(default_factory=list)
    budget_activities: list[HouseModelBudgetActivityRead] = Field(default_factory=list)


class ClientBase(BaseModel):
    company_id: int | None = None
    name: str = Field(min_length=1, max_length=200)
    legal_name: str | None = None
    tax_id: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_email: EmailStr | None = None
    address: str | None = None
    notes: str | None = None


class ClientCreate(ClientBase):
    pass


class ClientUpdate(BaseModel):
    company_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    legal_name: str | None = None
    tax_id: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_email: EmailStr | None = None
    address: str | None = None
    notes: str | None = None


class ClientRead(ClientBase, TimestampRead):
    id: int


class ProjectBase(BaseModel):
    company_id: int | None = None
    client_id: int
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    location: str | None = None
    status: ProjectStatus = "draft"
    start_date: date | None = None
    estimated_end_date: date | None = None
    approved_at: date | None = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    company_id: int | None = None
    client_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    location: str | None = None
    status: ProjectStatus | None = None
    start_date: date | None = None
    estimated_end_date: date | None = None
    approved_at: date | None = None


class ProjectRead(ProjectBase, TimestampRead):
    id: int


class HouseModelBase(BaseModel):
    company_id: int | None = None
    client_id: int
    name: str = Field(min_length=1, max_length=160)
    description: str | None = None
    construction_m2: PositiveDecimal
    levels: int | None = Field(default=None, ge=0)
    bedrooms: int | None = Field(default=None, ge=0)
    bathrooms: NonNegativeDecimal | None = None
    base_notes: str | None = None


class HouseModelCreate(HouseModelBase):
    pass


class HouseModelUpdate(BaseModel):
    company_id: int | None = None
    client_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = None
    construction_m2: PositiveDecimal | None = None
    levels: int | None = Field(default=None, ge=0)
    bedrooms: int | None = Field(default=None, ge=0)
    bathrooms: NonNegativeDecimal | None = None
    base_notes: str | None = None


class HouseModelRead(HouseModelBase, TimestampRead):
    id: int


class ProjectHouseModelCreate(BaseModel):
    house_model_id: int
    quantity: PositiveDecimal
    estimated_cost_per_unit: NonNegativeDecimal | None = None
    estimated_price_per_unit: NonNegativeDecimal | None = None


class ProjectHouseModelRead(ProjectHouseModelCreate, ORMModel):
    id: int
    project_id: int
    total_estimated_cost: NonNegativeDecimal | None = None
    total_estimated_price: NonNegativeDecimal | None = None


class ProjectMaterialPriceBase(BaseModel):
    company_id: int | None = None
    project_id: int
    house_model_id: int | None = None
    material_id: int
    unit: str | None = Field(default=None, max_length=40)
    unit_price: NonNegativeDecimal = 0
    supply_source: SupplySource = "constructor"
    supplier_name: str | None = Field(default=None, max_length=200)
    include_in_quote: bool = True
    source_document_name: str | None = Field(default=None, max_length=255)
    effective_date: date | None = None
    notes: str | None = None
    is_active: bool = True


class ProjectMaterialPriceCreate(ProjectMaterialPriceBase):
    pass


class ProjectMaterialPriceUpdate(BaseModel):
    company_id: int | None = None
    project_id: int | None = None
    house_model_id: int | None = None
    material_id: int | None = None
    unit: str | None = Field(default=None, max_length=40)
    unit_price: NonNegativeDecimal | None = None
    supply_source: SupplySource | None = None
    supplier_name: str | None = Field(default=None, max_length=200)
    include_in_quote: bool | None = None
    source_document_name: str | None = Field(default=None, max_length=255)
    effective_date: date | None = None
    notes: str | None = None
    is_active: bool | None = None


class ProjectMaterialPriceRead(ProjectMaterialPriceBase, TimestampRead):
    id: int
    unit: str


class MaterialBase(BaseModel):
    company_id: int | None = None
    name: str = Field(min_length=1, max_length=200)
    unit: str = Field(min_length=1, max_length=40)
    current_unit_price: NonNegativeDecimal
    supplier_name: str | None = None
    last_price_update: date | None = None
    is_active: bool = True


class MaterialCreate(MaterialBase):
    pass


class MaterialUpdate(BaseModel):
    company_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    unit: str | None = Field(default=None, min_length=1, max_length=40)
    current_unit_price: NonNegativeDecimal | None = None
    supplier_name: str | None = None
    last_price_update: date | None = None
    is_active: bool | None = None


class MaterialRead(MaterialBase, TimestampRead):
    id: int


class LaborRateBase(BaseModel):
    company_id: int | None = None
    name: str = Field(min_length=1, max_length=200)
    unit: str = Field(min_length=1, max_length=40)
    unit_cost: NonNegativeDecimal
    performance_per_day: NonNegativeDecimal | None = None
    notes: str | None = None
    is_active: bool = True


class LaborRateCreate(LaborRateBase):
    pass


class LaborRateUpdate(BaseModel):
    company_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    unit: str | None = Field(default=None, min_length=1, max_length=40)
    unit_cost: NonNegativeDecimal | None = None
    performance_per_day: NonNegativeDecimal | None = None
    notes: str | None = None
    is_active: bool | None = None


class LaborRateRead(LaborRateBase, TimestampRead):
    id: int


class ConceptMaterialCreate(BaseModel):
    material_id: int
    quantity_per_unit: NonNegativeDecimal


class ConceptMaterialRead(ConceptMaterialCreate, ORMModel):
    id: int
    construction_concept_id: int


class ConceptLaborCreate(BaseModel):
    labor_rate_id: int
    quantity_per_unit: NonNegativeDecimal


class ConceptLaborRead(ConceptLaborCreate, ORMModel):
    id: int
    construction_concept_id: int


class ConstructionConceptBase(BaseModel):
    company_id: int | None = None
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    unit: str = Field(min_length=1, max_length=40)
    description: str | None = None
    default_waste_percent: Percent = 0
    default_indirect_percent: Percent = 0


class ConstructionConceptCreate(ConstructionConceptBase):
    materials: list[ConceptMaterialCreate] = Field(default_factory=list)
    labor: list[ConceptLaborCreate] = Field(default_factory=list)


class ConstructionConceptUpdate(BaseModel):
    company_id: int | None = None
    code: str | None = Field(default=None, min_length=1, max_length=80)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    unit: str | None = Field(default=None, min_length=1, max_length=40)
    description: str | None = None
    default_waste_percent: Percent | None = None
    default_indirect_percent: Percent | None = None
    materials: list[ConceptMaterialCreate] | None = None
    labor: list[ConceptLaborCreate] | None = None


class ConstructionConceptRead(ConstructionConceptBase, TimestampRead):
    id: int
    concept_materials: list[ConceptMaterialRead] = Field(default_factory=list)
    concept_labor: list[ConceptLaborRead] = Field(default_factory=list)


class HouseModelConceptCreate(BaseModel):
    construction_concept_id: int
    quantity_formula_type: QuantityFormulaType = "fixed"
    quantity_value: NonNegativeDecimal
    sort_order: int = 0


class HouseModelConceptRead(HouseModelConceptCreate, ORMModel):
    id: int
    house_model_id: int


class ProjectSummary(ORMModel):
    project: ProjectRead
    assigned_models: list[ProjectHouseModelRead]
    quote_count: int
    approved_quote_id: int | None = None
    total_estimated_cost: NonNegativeDecimal
    total_estimated_price: NonNegativeDecimal
