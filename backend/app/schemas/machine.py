"""
Schemas Pydantic para la entidad Machine.

Distinción habitual:
- *Create* contiene los campos requeridos al insertar.
- *Update* hace todos los campos opcionales para PATCH parcial.
- *Response* refleja la fila tal como viene de la BD (incluye id y status).
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models import MachineStatus, MachineType, OperationStatus, OrderStatus
from app.schemas.common import ORMConfig


class CurrentOrderSummary(BaseModel):
    """Resumen anidado de la orden activa de una máquina (para Digital Twin)."""

    model_config = ORMConfig

    id: int
    order_number: str
    product_type: str
    quantity_ordered: int
    quantity_produced: int
    status: OrderStatus
    priority: str


class CurrentOperationSummary(BaseModel):
    """
    Resumen de la operación que la máquina está procesando AHORA mismo.

    Permite que MachineTile pinte el avance correcto: para IMP/TUB/FON
    es quantity_out / quantity_in de la operación, no de la orden
    cabecera (que solo se actualiza al cerrar EMP).
    """

    model_config = ORMConfig

    id: int
    order_id: int
    order_number: str
    sequence: int
    status: OperationStatus
    quantity_in: int
    quantity_out: int
    scrap_kg: float


class MachineBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=32, examples=["TUB-01"])
    name: str = Field(..., min_length=1, max_length=64, examples=["Tubuladora 1"])
    type: MachineType
    location: Optional[str] = Field(default=None, max_length=64, examples=["Línea A"])


class MachineCreate(MachineBase):
    """Payload de creación. El status inicial por defecto es IDLE."""

    status: MachineStatus = MachineStatus.IDLE


class MachineUpdate(BaseModel):
    """Todos los campos opcionales para soportar PATCH parcial."""

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    location: Optional[str] = Field(default=None, max_length=64)
    status: Optional[MachineStatus] = None
    current_order_id: Optional[int] = None


class MachineResponse(MachineBase):
    model_config = ORMConfig

    id: int
    status: MachineStatus
    current_order_id: Optional[int] = None
    # Orden cabecera asignada (su quantity_produced solo refleja lo que ya
    # pasó por EMP — útil como contexto, no como avance de la máquina).
    current_order: Optional[CurrentOrderSummary] = None
    # Operación que esta máquina está procesando ahora mismo. Es la fuente
    # correcta para el % de avance del tile en el Digital Twin.
    current_operation: Optional[CurrentOperationSummary] = None
