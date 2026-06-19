"""
Schemas Pydantic para ProductionOrder.

Cubren creación, actualización parcial y respuesta. Los enums
(OrderStatus, OrderPriority) se reutilizan desde el dominio para que los
valores válidos sean exactamente los mismos en BD, API y frontend.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import OrderPriority, OrderStatus
from app.schemas.common import ORMConfig


class ProductionOrderBase(BaseModel):
    order_number: str = Field(..., min_length=1, max_length=32)
    product_type: str = Field(..., min_length=1, max_length=64)
    product_description: Optional[str] = Field(default=None, max_length=255)
    quantity_ordered: int = Field(..., ge=1, description="Unidades pedidas (sacos)")
    unit_weight_kg: float = Field(default=0.1, gt=0.0, description="Peso de un saco vacío en kg")
    machine_id: Optional[int] = None
    priority: OrderPriority = OrderPriority.NORMAL
    planned_start: datetime
    planned_end: datetime

    @model_validator(mode="after")
    def _validate_dates(self) -> "ProductionOrderBase":
        if self.planned_end <= self.planned_start:
            raise ValueError("planned_end debe ser posterior a planned_start")
        return self


class ProductionOrderCreate(ProductionOrderBase):
    """Estado inicial por defecto: PENDING."""

    status: OrderStatus = OrderStatus.PENDING


class ProductionOrderUpdate(BaseModel):
    """Actualización parcial. Útil para registrar avance o cambiar prioridad."""

    model_config = ConfigDict(extra="forbid")

    product_type: Optional[str] = Field(default=None, min_length=1, max_length=64)
    product_description: Optional[str] = Field(default=None, max_length=255)
    quantity_ordered: Optional[int] = Field(default=None, ge=1)
    quantity_produced: Optional[int] = Field(default=None, ge=0)
    machine_id: Optional[int] = None
    status: Optional[OrderStatus] = None
    priority: Optional[OrderPriority] = None
    planned_start: Optional[datetime] = None
    planned_end: Optional[datetime] = None
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None


class ProductionOrderResponse(ProductionOrderBase):
    model_config = ORMConfig

    id: int
    quantity_produced: int
    scrap_total_kg: float
    status: OrderStatus
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    created_at: datetime
