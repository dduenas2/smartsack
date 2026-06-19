"""
Modelo Material — consumo de materiales por orden.

Para cada orden se registra qué materiales (papel, tinta, hilo, pegamento)
estaban planificados y cuántos se consumieron realmente. Permite cálculos
de eficiencia de material y trazabilidad.
"""

from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.order import ProductionOrder


class Material(Base):
    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("production_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )

    material_type: Mapped[str] = mapped_column(String(64), nullable=False)
    unit: Mapped[str] = mapped_column(String(16), default="kg", nullable=False)

    quantity_planned: Mapped[float] = mapped_column(Float, nullable=False)
    quantity_used: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # ---- Relaciones ----
    order: Mapped["ProductionOrder"] = relationship(
        "ProductionOrder", back_populates="materials"
    )

    def __repr__(self) -> str:
        return (
            f"<Material order_id={self.order_id} type={self.material_type!r} "
            f"used={self.quantity_used}/{self.quantity_planned} {self.unit}>"
        )
