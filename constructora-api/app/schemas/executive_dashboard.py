from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class ExecutivePortfolioTotals(BaseModel):
    project_count: int
    active_project_count: int
    attention_project_count: int
    houses_count: Decimal
    budget_amount: Decimal
    committed_amount: Decimal
    received_amount: Decimal
    invoiced_amount: Decimal
    paid_amount: Decimal
    available_amount: Decimal
    over_budget_amount: Decimal
    purchase_orders_count: int
    invoices_count: int
    payments_count: int


class ExecutiveFlowStage(BaseModel):
    key: str
    label: str
    count: int
    attention_count: int = 0
    description: str
    action_url: str


class ExecutiveAlert(BaseModel):
    key: str
    project_id: int | None = None
    project_name: str | None = None
    title: str
    detail: str
    priority: str
    action_label: str
    action_url: str


class ExecutiveProjectRow(BaseModel):
    project_id: int
    project_name: str
    client_name: str
    houses_count: Decimal
    models_count: int
    baseline_id: int | None = None
    baseline_revision: int | None = None
    baseline_status: str | None = None
    baseline_approved_at: datetime | None = None
    budget_amount: Decimal
    committed_amount: Decimal
    received_amount: Decimal
    invoiced_amount: Decimal
    paid_amount: Decimal
    available_amount: Decimal
    over_budget_amount: Decimal
    committed_percent: Decimal
    received_percent: Decimal
    invoiced_percent: Decimal
    paid_percent: Decimal
    purchase_orders_count: int
    invoices_count: int
    payments_count: int
    integrity_issues: list[str] = Field(default_factory=list)
    health: str
    health_label: str
    next_action_label: str
    next_action_url: str


class ExecutiveMaterialRow(BaseModel):
    baseline_item_id: int
    house_model_id: int | None = None
    house_model_name: str
    source_code: str | None = None
    description: str
    unit: str
    houses_quantity: Decimal
    quantity_per_house: Decimal
    budget_quantity: Decimal
    ordered_quantity: Decimal
    received_quantity: Decimal
    budget_amount: Decimal
    committed_amount: Decimal
    received_amount: Decimal
    invoiced_amount: Decimal
    paid_amount: Decimal
    available_amount: Decimal
    committed_percent: Decimal
    paid_percent: Decimal
    status: str


class ExecutiveDashboardResponse(BaseModel):
    generated_at: datetime
    selected_project_id: int | None = None
    totals: ExecutivePortfolioTotals
    flow: list[ExecutiveFlowStage] = Field(default_factory=list)
    alerts: list[ExecutiveAlert] = Field(default_factory=list)
    projects: list[ExecutiveProjectRow] = Field(default_factory=list)
    materials: list[ExecutiveMaterialRow] = Field(default_factory=list)
