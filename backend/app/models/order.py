"""
Modelo ProductionOrder — orden de producción.

Representa la fabricación de una cantidad específica de un producto en una
máquina, con horarios planificados y reales. Es la entidad central del
sistema: ETL la importa desde SAP, los operarios la ejecutan, el motor de ML
predice su retraso y los KPIs se calculan a partir de ella.
"""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import OrderPriority, OrderStatus

if TYPE_CHECKING:
    from app.models.event import ProductionEvent
    from app.models.machine import Machine
    from app.models.material import Material
    from app.models.operation import OrderOperation
    from app.models.prediction import MLPrediction
    from app.models.quality import QualityRecord


class ProductionOrder(Base):
    __tablename__ = "production_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_number: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, index=True
    )

    product_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    product_description: Mapped[Optional[str]] = mapped_column(String(255))

    # Cantidad pedida en UNIDADES (sacos). La producción se registra siempre
    # en unidades; el desperdicio en kg.
    quantity_ordered: Mapped[int] = mapped_column(Integer, nullable=False)
    # Unidades buenas finales — solo se actualiza cuando la operación EMP
    # se completa (es lo que va a inventario para despacho).
    quantity_produced: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Suma denormalizada del scrap_kg de las operaciones IMP+TUB+FON.
    # EMP no contribuye porque no genera desperdicio.
    scrap_total_kg: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    # Peso de un saco vacío (papel) — permite estimar cuántas unidades
    # equivalen al desperdicio reportado en kg.
    unit_weight_kg: Mapped[float] = mapped_column(Float, default=0.1, nullable=False)

    # Máquina actual donde está la orden (la operación más reciente con
    # status running/in_progress). Denormalizado para queries rápidos del
    # Digital Twin; la fuente de verdad son las operaciones.
    machine_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("machines.id", ondelete="SET NULL"), index=True
    )

    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status"),
        default=OrderStatus.PENDING,
        nullable=False,
        index=True,
    )
    priority: Mapped[OrderPriority] = mapped_column(
        Enum(OrderPriority, name="order_priority"),
        default=OrderPriority.NORMAL,
        nullable=False,
    )

    planned_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    planned_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actual_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    actual_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ---- Relaciones ----
    machine: Mapped[Optional["Machine"]] = relationship(
        "Machine", back_populates="orders", foreign_keys=[machine_id]
    )
    events: Mapped[List["ProductionEvent"]] = relationship(
        "ProductionEvent", back_populates="order", cascade="all, delete-orphan"
    )
    operations: Mapped[List["OrderOperation"]] = relationship(
        "OrderOperation",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderOperation.sequence",
    )
    materials: Mapped[List["Material"]] = relationship(
        "Material", back_populates="order", cascade="all, delete-orphan"
    )
    quality_records: Mapped[List["QualityRecord"]] = relationship(
        "QualityRecord", back_populates="order", cascade="all, delete-orphan"
    )
    ml_predictions: Mapped[List["MLPrediction"]] = relationship(
        "MLPrediction", back_populates="order", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<ProductionOrder n={self.order_number!r} "
            f"qty={self.quantity_produced}/{self.quantity_ordered} "
            f"status={self.status.value}>"
        )
