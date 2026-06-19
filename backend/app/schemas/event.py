"""
Schemas Pydantic para ProductionEvent.

Los eventos se registran sin permitir backdating arbitrario: el campo
`timestamp` es opcional y, si se omite, el backend lo genera con el
instante de creación (server_default). El usuario que registra el evento
se inyecta automáticamente desde el JWT autenticado.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models import EventType, ScrapReason
from app.schemas.common import ORMConfig


class ProductionEventCreate(BaseModel):
    """Datos que envía el cliente al registrar un evento de producción."""

    machine_id: int = Field(..., ge=1)
    order_id: Optional[int] = Field(default=None, ge=1)
    operation_id: Optional[int] = Field(default=None, ge=1)
    event_type: EventType
    description: Optional[str] = Field(default=None, max_length=500)
    # Si es None, se asigna en el servidor.
    timestamp: Optional[datetime] = None
    # production_update: unidades producidas (puede ser negativo para correcciones).
    quantity: Optional[int] = Field(default=None)
    # production_update: desperdicio en kg (>=0). Obligatorio 0/None en EMP.
    scrap_kg: Optional[float] = Field(default=None, ge=0.0)
    scrap_reason: Optional[ScrapReason] = None


class ProductionEventResponse(BaseModel):
    model_config = ORMConfig

    id: int
    machine_id: int
    order_id: Optional[int] = None
    operation_id: Optional[int] = None
    user_id: Optional[int] = None
    event_type: EventType
    description: Optional[str] = None
    timestamp: datetime
    quantity: Optional[int] = None
    scrap_kg: Optional[float] = None
    scrap_reason: Optional[ScrapReason] = None
