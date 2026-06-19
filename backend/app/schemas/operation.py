"""
Schemas Pydantic para OrderOperation.

Una operación es una etapa de la ruta IMP→TUB→FON→EMP. La respuesta
incluye un resumen anidado de la orden cabecera para que el frontend
no tenga que hacer un round-trip extra al pintar la cola del operario.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models import (
    MachineType,
    OperationStatus,
    OrderPriority,
    ScrapReason,
    ShiftName,
)
from app.schemas.common import ORMConfig


class OperationOrderSummary(BaseModel):
    """Resumen de la orden cabecera para incluir junto a una operación."""

    model_config = ORMConfig

    id: int
    order_number: str
    product_type: str
    quantity_ordered: int
    priority: OrderPriority
    unit_weight_kg: float


class OperationMachineSummary(BaseModel):
    """Resumen de la máquina (código + tipo) para mostrar en la UI."""

    model_config = ORMConfig

    id: int
    code: str
    name: str
    type: MachineType


class OperationResponse(BaseModel):
    """Respuesta estándar para listar operaciones."""

    model_config = ORMConfig

    id: int
    order_id: int
    machine_id: int
    sequence: int
    status: OperationStatus

    quantity_in: int
    quantity_out: int
    scrap_kg: float
    scrap_reason: Optional[ScrapReason] = None

    planned_start: datetime
    planned_end: datetime
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None

    operator_id: Optional[int] = None
    shift: Optional[ShiftName] = None
    created_at: datetime

    # Campos anidados poblados por los routers (no vienen del ORM directo).
    order: Optional[OperationOrderSummary] = None
    machine: Optional[OperationMachineSummary] = None


class OperationProductionReport(BaseModel):
    """
    Payload para reportar producción + scrap desde el operario.

    Se procesa como un evento `production_update` que apunta a la
    operación. Validaciones aplicadas en el router:
    - quantity > 0 (ó negativo solo para correcciones)
    - scrap_kg >= 0
    - en EMP: scrap_kg debe ser 0
    - si scrap_kg > 0: scrap_reason es obligatorio
    """

    quantity: int = Field(..., description="Unidades buenas producidas en este reporte")
    scrap_kg: float = Field(default=0.0, ge=0.0, description="Desperdicio en kg")
    scrap_reason: Optional[ScrapReason] = None
    description: Optional[str] = Field(default=None, max_length=500)
