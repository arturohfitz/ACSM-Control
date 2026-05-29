from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Client(TimestampMixin, Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    legal_name: Mapped[str | None] = mapped_column(String(255))
    tax_id: Mapped[str | None] = mapped_column(String(80))
    contact_name: Mapped[str | None] = mapped_column(String(200))
    contact_phone: Mapped[str | None] = mapped_column(String(80))
    contact_email: Mapped[str | None] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)

    projects: Mapped[list["Project"]] = relationship(back_populates="client")
    house_models: Mapped[list["HouseModel"]] = relationship(back_populates="client")


class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date)
    estimated_end_date: Mapped[date | None] = mapped_column(Date)
    approved_at: Mapped[date | None] = mapped_column(Date)

    client: Mapped[Client] = relationship(back_populates="projects")
    project_house_models: Mapped[list["ProjectHouseModel"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    material_prices: Mapped[list["ProjectMaterialPrice"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    quotes: Mapped[list["Quote"]] = relationship(back_populates="project")


class HouseModel(TimestampMixin, Base):
    __tablename__ = "house_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"), index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    construction_m2: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    levels: Mapped[int | None] = mapped_column(Integer)
    bedrooms: Mapped[int | None] = mapped_column(Integer)
    bathrooms: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    base_notes: Mapped[str | None] = mapped_column(Text)

    client: Mapped[Client | None] = relationship(back_populates="house_models")
    model_concepts: Mapped[list["HouseModelConcept"]] = relationship(
        back_populates="house_model", cascade="all, delete-orphan"
    )
    documents: Mapped[list["HouseModelDocument"]] = relationship(
        back_populates="house_model", cascade="all, delete-orphan"
    )
    material_requirements: Mapped[list["HouseModelMaterialRequirement"]] = relationship(
        back_populates="house_model", cascade="all, delete-orphan"
    )
    budget_activities: Mapped[list["HouseModelBudgetActivity"]] = relationship(
        back_populates="house_model", cascade="all, delete-orphan"
    )
    project_house_models: Mapped[list["ProjectHouseModel"]] = relationship(
        back_populates="house_model"
    )


class HouseModelDocument(TimestampMixin, Base):
    __tablename__ = "house_model_documents"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "house_model_id",
            "document_type",
            "file_hash",
            name="uq_house_model_document_hash",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False, index=True)
    house_model_id: Mapped[int] = mapped_column(
        ForeignKey("house_models.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_type: Mapped[str] = mapped_column(String(40), nullable=False)
    version: Mapped[str | None] = mapped_column(String(80))
    source_code: Mapped[str | None] = mapped_column(String(120))
    source_date: Mapped[date | None] = mapped_column(Date)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(500))
    file_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="interpreted", nullable=False)
    total_items: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    notes: Mapped[str | None] = mapped_column(Text)

    house_model: Mapped[HouseModel] = relationship(back_populates="documents")
    material_requirements: Mapped[list["HouseModelMaterialRequirement"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    budget_activities: Mapped[list["HouseModelBudgetActivity"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class HouseModelMaterialRequirement(Base):
    __tablename__ = "house_model_material_requirements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False, index=True)
    house_model_id: Mapped[int] = mapped_column(
        ForeignKey("house_models.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[int] = mapped_column(
        ForeignKey("house_model_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    material_id: Mapped[int | None] = mapped_column(ForeignKey("materials.id"), index=True)
    source_code: Mapped[str | None] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    quantity_per_house: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    unit_cost_reference: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    total_cost_reference: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    family: Mapped[str | None] = mapped_column(String(120))
    validation_status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    house_model: Mapped[HouseModel] = relationship(back_populates="material_requirements")
    document: Mapped[HouseModelDocument] = relationship(back_populates="material_requirements")
    material: Mapped["Material | None"] = relationship()


class HouseModelBudgetActivity(Base):
    __tablename__ = "house_model_budget_activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False, index=True)
    house_model_id: Mapped[int] = mapped_column(
        ForeignKey("house_models.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[int] = mapped_column(
        ForeignKey("house_model_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    construction_concept_id: Mapped[int | None] = mapped_column(
        ForeignKey("construction_concepts.id"), index=True
    )
    chapter_code: Mapped[str | None] = mapped_column(String(40))
    chapter_name: Mapped[str | None] = mapped_column(String(200))
    source_code: Mapped[str | None] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    quantity_per_house: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    unit_price_reference: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    total_price_reference: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    validation_status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    house_model: Mapped[HouseModel] = relationship(back_populates="budget_activities")
    document: Mapped[HouseModelDocument] = relationship(back_populates="budget_activities")
    construction_concept: Mapped["ConstructionConcept | None"] = relationship()


class ProjectHouseModel(Base):
    __tablename__ = "project_house_models"
    __table_args__ = (
        UniqueConstraint("project_id", "house_model_id", name="uq_project_house_model_pair"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    house_model_id: Mapped[int] = mapped_column(
        ForeignKey("house_models.id"), nullable=False, index=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    estimated_cost_per_unit: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    estimated_price_per_unit: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    total_estimated_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    total_estimated_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))

    project: Mapped[Project] = relationship(back_populates="project_house_models")
    house_model: Mapped[HouseModel] = relationship(back_populates="project_house_models")
    quote_items: Mapped[list["QuoteItem"]] = relationship(back_populates="project_house_model")


class ProjectMaterialPrice(TimestampMixin, Base):
    __tablename__ = "project_material_prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    house_model_id: Mapped[int | None] = mapped_column(ForeignKey("house_models.id"), index=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"), nullable=False, index=True)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0, nullable=False)
    supply_source: Mapped[str] = mapped_column(String(40), default="constructor", nullable=False)
    supplier_name: Mapped[str | None] = mapped_column(String(200))
    include_in_quote: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    source_document_name: Mapped[str | None] = mapped_column(String(255))
    effective_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    project: Mapped[Project] = relationship(back_populates="material_prices")
    house_model: Mapped[HouseModel | None] = relationship()
    material: Mapped["Material"] = relationship(back_populates="project_prices")


class Material(TimestampMixin, Base):
    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    current_unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    supplier_name: Mapped[str | None] = mapped_column(String(200))
    last_price_update: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    concept_materials: Mapped[list["ConceptMaterial"]] = relationship(
        back_populates="material", cascade="all, delete-orphan"
    )
    project_prices: Mapped[list[ProjectMaterialPrice]] = relationship(back_populates="material")


class LaborRate(TimestampMixin, Base):
    __tablename__ = "labor_rates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    performance_per_day: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    concept_labor: Mapped[list["ConceptLabor"]] = relationship(
        back_populates="labor_rate", cascade="all, delete-orphan"
    )


class ConstructionConcept(TimestampMixin, Base):
    __tablename__ = "construction_concepts"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_construction_concepts_company_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    default_waste_percent: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=0, nullable=False)
    default_indirect_percent: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), default=0, nullable=False
    )

    house_model_concepts: Mapped[list["HouseModelConcept"]] = relationship(
        back_populates="construction_concept", cascade="all, delete-orphan"
    )
    concept_materials: Mapped[list["ConceptMaterial"]] = relationship(
        back_populates="construction_concept", cascade="all, delete-orphan"
    )
    concept_labor: Mapped[list["ConceptLabor"]] = relationship(
        back_populates="construction_concept", cascade="all, delete-orphan"
    )
    quote_items: Mapped[list["QuoteItem"]] = relationship(back_populates="construction_concept")


class HouseModelConcept(Base):
    __tablename__ = "house_model_concepts"
    __table_args__ = (
        UniqueConstraint(
            "house_model_id",
            "construction_concept_id",
            name="uq_house_model_concept_pair",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    house_model_id: Mapped[int] = mapped_column(
        ForeignKey("house_models.id"), nullable=False, index=True
    )
    construction_concept_id: Mapped[int] = mapped_column(
        ForeignKey("construction_concepts.id"), nullable=False, index=True
    )
    quantity_formula_type: Mapped[str] = mapped_column(String(40), default="fixed", nullable=False)
    quantity_value: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    house_model: Mapped[HouseModel] = relationship(back_populates="model_concepts")
    construction_concept: Mapped[ConstructionConcept] = relationship(
        back_populates="house_model_concepts"
    )


class ConceptMaterial(Base):
    __tablename__ = "concept_materials"
    __table_args__ = (
        UniqueConstraint(
            "construction_concept_id", "material_id", name="uq_concept_material_pair"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    construction_concept_id: Mapped[int] = mapped_column(
        ForeignKey("construction_concepts.id"), nullable=False, index=True
    )
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"), nullable=False, index=True)
    quantity_per_unit: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)

    construction_concept: Mapped[ConstructionConcept] = relationship(
        back_populates="concept_materials"
    )
    material: Mapped[Material] = relationship(back_populates="concept_materials")


class ConceptLabor(Base):
    __tablename__ = "concept_labor"
    __table_args__ = (
        UniqueConstraint(
            "construction_concept_id", "labor_rate_id", name="uq_concept_labor_pair"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    construction_concept_id: Mapped[int] = mapped_column(
        ForeignKey("construction_concepts.id"), nullable=False, index=True
    )
    labor_rate_id: Mapped[int] = mapped_column(
        ForeignKey("labor_rates.id"), nullable=False, index=True
    )
    quantity_per_unit: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)

    construction_concept: Mapped[ConstructionConcept] = relationship(
        back_populates="concept_labor"
    )
    labor_rate: Mapped[LaborRate] = relationship(back_populates="concept_labor")
