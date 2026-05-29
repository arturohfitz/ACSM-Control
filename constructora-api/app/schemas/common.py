from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


ProjectStatus = Literal[
    "draft",
    "quoted",
    "approved",
    "in_execution",
    "paused",
    "completed",
    "cancelled",
]
QuoteStatus = Literal["draft", "sent", "approved", "rejected", "cancelled"]
QuantityFormulaType = Literal["fixed", "per_m2"]

Money = Annotated[Decimal, Field(ge=0)]
PositiveDecimal = Annotated[Decimal, Field(gt=0)]
NonNegativeDecimal = Annotated[Decimal, Field(ge=0)]
Percent = Annotated[Decimal, Field(ge=0)]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TimestampRead(ORMModel):
    created_at: datetime
    updated_at: datetime

