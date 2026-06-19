"""
Modelo ProductionEvent — bitácora de eventos de producción.

Cada acción significativa (inicio, parada, cambio de formato, incidencia, fin)
deja una traza inmutable. Es la fuente para reconstruir cronologías, calcular
disponibilidad para el OEE y entrenar el modelo de ML.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import EventType, ScrapReason

if TYPE_CHECKING:
    from app.models.machine import Machine
    from app.models.operation import OrderOperation
    from app.models.order import ProductionOrder
    from app.models.user import User


class ProductionEvent(Base):
    __tablename__ = "production_events"

    id: Mapped[int] = mapped_column(primary_key=True)

    machine_id: Mapped[int] = mapped_column(
        ForeignKey("machines.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("production_orders.id", ondelete="CASCADE"), index=True
    )
    # Una operación específica de la ruta (poblado para events del operario
    # que avanzan trabajo: production_update, end de operación, etc.).
    operation_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("order_operations.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    event_type: Mapped[EventType] = mapped_column(
        Enum(EventType, name="event_type"), nullable=False, index=True
    )
    description: Mapped[Optional[str]] = mapped_column(String(500))
    # production_update: unidades producidas en este reporte (puede ser
    # negativo para correcciones).
    quantity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # production_update en IMP/TUB/FON: kg de desperdicio reportados (>=0).
    # En EMP debe ser NULL/0 (validado).
    scrap_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    scrap_reason: Mapped[Optional[ScrapReason]] = mapped_column(
        Enum(ScrapReason, name="scrap_reason"), nullable=True
    )

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # ---- Relaciones ----
    machine: Mapped["Machine"] = relationship("Machine", back_populates="events")
    order: Mapped[Optional["ProductionOrder"]] = relationship(
        "ProductionOrder", back_populates="events"
    )
    operation: Mapped[Optional["OrderOperation"]] = relationship("OrderOperation")
    user: Mapped[Optional["User"]] = relationship("User", back_populates="events")

    def __repr__(self) -> str:
        return (
            f"<ProductionEvent type={self.event_type.value} "
            f"machine_id={self.machine_id} order_id={self.order_id}>"
        )
