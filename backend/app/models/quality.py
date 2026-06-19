"""
Modelo QualityRecord — control de calidad de una orden.

Registra cuántas unidades se produjeron, cuántas pasaron control y cuántas
fueron rechazadas. Es el insumo para el factor "calidad" del OEE.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.order import ProductionOrder


class QualityRecord(Base):
    __tablename__ = "quality_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("production_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )

    total_produced: Mapped[int] = mapped_column(Integer, nullable=False)
    good_units: Mapped[int] = mapped_column(Integer, nullable=False)
    defective_units: Mapped[int] = mapped_column(Integer, nullable=False)

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ---- Relaciones ----
    order: Mapped["ProductionOrder"] = relationship(
        "ProductionOrder", back_populates="quality_records"
    )

    @property
    def quality_ratio(self) -> float:
        """Proporción de unidades buenas sobre total producido (0.0–1.0)."""
        return self.good_units / self.total_produced if self.total_produced else 0.0

    def __repr__(self) -> str:
        return (
            f"<QualityRecord order_id={self.order_id} "
            f"good={self.good_units}/{self.total_produced}>"
        )
