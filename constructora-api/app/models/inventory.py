from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class ProjectWarehouse(TimestampMixin, Base):
    __tablename__ = "project_warehouses"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_project_warehouses_project_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    expected_lists: Mapped[list["ExpectedMaterialList"]] = relationship(
        back_populates="warehouse"
    )
    receptions: Mapped[list["MaterialReception"]] = relationship(back_populates="warehouse")
    stock_items: Mapped[list["WarehouseStock"]] = relationship(back_populates="warehouse")


class ExpectedMaterialList(TimestampMixin, Base):
    __tablename__ = "expected_material_lists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    warehouse_id: Mapped[int | None] = mapped_column(ForeignKey("project_warehouses.id"), index=True)
    purchase_order_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_orders.id"), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    document_number: Mapped[str | None] = mapped_column(String(80))
    supplier_name: Mapped[str | None] = mapped_column(String(200))
    document_date: Mapped[date | None] = mapped_column(Date)
    delivery_date: Mapped[date | None] = mapped_column(Date)
    source_document_name: Mapped[str | None] = mapped_column(String(255))
    source_document_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    source_notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="open", nullable=False)

    warehouse: Mapped[ProjectWarehouse | None] = relationship(back_populates="expected_lists")
    items: Mapped[list["ExpectedMaterialItem"]] = relationship(
        back_populates="expected_list", cascade="all, delete-orphan"
    )
    receptions: Mapped[list["MaterialReception"]] = relationship(back_populates="expected_list")


class ExpectedMaterialItem(TimestampMixin, Base):
    __tablename__ = "expected_material_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    expected_list_id: Mapped[int] = mapped_column(
        ForeignKey("expected_material_lists.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    material_id: Mapped[int | None] = mapped_column(ForeignKey("materials.id"), index=True)
    purchase_order_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("purchase_order_items.id"), index=True
    )
    source_code: Mapped[str | None] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    expected_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    line_total: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    delivery_date: Mapped[date | None] = mapped_column(Date)
    received_quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 4), default=0, nullable=False
    )
    status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    expected_list: Mapped[ExpectedMaterialList] = relationship(back_populates="items")
    reception_items: Mapped[list["MaterialReceptionItem"]] = relationship(
        back_populates="expected_item"
    )
    stock_item: Mapped["WarehouseStock | None"] = relationship(back_populates="expected_item")


class MaterialReception(TimestampMixin, Base):
    __tablename__ = "material_receptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("project_warehouses.id"), nullable=False, index=True
    )
    expected_list_id: Mapped[int] = mapped_column(
        ForeignKey("expected_material_lists.id"), nullable=False, index=True
    )
    received_at: Mapped[date] = mapped_column(Date, nullable=False)
    delivery_reference: Mapped[str | None] = mapped_column(String(160))
    delivered_by: Mapped[str | None] = mapped_column(String(160))
    received_by: Mapped[str | None] = mapped_column(String(160))
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="closed", nullable=False)

    warehouse: Mapped[ProjectWarehouse] = relationship(back_populates="receptions")
    expected_list: Mapped[ExpectedMaterialList] = relationship(back_populates="receptions")
    items: Mapped[list["MaterialReceptionItem"]] = relationship(
        back_populates="reception", cascade="all, delete-orphan"
    )


class MaterialReceptionItem(Base):
    __tablename__ = "material_reception_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reception_id: Mapped[int] = mapped_column(
        ForeignKey("material_receptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    expected_item_id: Mapped[int] = mapped_column(
        ForeignKey("expected_material_items.id"), nullable=False, index=True
    )
    material_id: Mapped[int | None] = mapped_column(ForeignKey("materials.id"), index=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    received_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    condition_status: Mapped[str] = mapped_column(String(40), default="ok", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    reception: Mapped[MaterialReception] = relationship(back_populates="items")
    expected_item: Mapped[ExpectedMaterialItem] = relationship(back_populates="reception_items")


class WarehouseStock(TimestampMixin, Base):
    __tablename__ = "warehouse_stock"
    __table_args__ = (
        UniqueConstraint("warehouse_id", "expected_item_id", name="uq_stock_warehouse_expected_item"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("project_warehouses.id"), nullable=False, index=True
    )
    expected_item_id: Mapped[int] = mapped_column(
        ForeignKey("expected_material_items.id"), nullable=False, index=True
    )
    material_id: Mapped[int | None] = mapped_column(ForeignKey("materials.id"), index=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    quantity_on_hand: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0, nullable=False)

    warehouse: Mapped[ProjectWarehouse] = relationship(back_populates="stock_items")
    expected_item: Mapped[ExpectedMaterialItem] = relationship(back_populates="stock_item")
