"""
Modelo MLPrediction — predicciones del motor de ML sobre órdenes.

Cada vez que el modelo evalúa una orden produce un registro con la
probabilidad de retraso, la cantidad esperada de horas de retraso y un
JSON con las features usadas. Permite auditar y comparar versiones del
modelo en el tiempo.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.order import ProductionOrder


class MLPrediction(Base):
    __tablename__ = "ml_predictions"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("production_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Probabilidad de retraso en [0.0, 1.0].
    delay_probability: Mapped[float] = mapped_column(Float, nullable=False)
    # Horas esperadas de retraso (puede ser 0 si delay_probability es bajo).
    predicted_delay_hours: Mapped[float] = mapped_column(Float, nullable=False)

    # Snapshot de las features usadas por el modelo en esta inferencia.
    features_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)

    model_version: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # ---- Relaciones ----
    order: Mapped["ProductionOrder"] = relationship(
        "ProductionOrder", back_populates="ml_predictions"
    )

    def __repr__(self) -> str:
        return (
            f"<MLPrediction order_id={self.order_id} "
            f"prob={self.delay_probability:.2f} model={self.model_version!r}>"
        )
