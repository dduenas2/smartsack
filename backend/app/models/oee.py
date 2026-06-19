"""
Modelo OEERecord — registro diario del OEE por máquina y turno.

OEE = Disponibilidad × Rendimiento × Calidad. Cada factor está acotado a
[0, 1]. Se persiste un registro por (máquina, turno, fecha) para alimentar
el dashboard y calcular tendencias históricas.
"""

from datetime import date as date_t
from typing import TYPE_CHECKING

from sqlalchemy import Date, Float, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.machine import Machine
    from app.models.shift import Shift


class OEERecord(Base):
    __tablename__ = "oee_records"
    __table_args__ = (
        # Garantiza un único registro por máquina-turno-fecha.
        UniqueConstraint("machine_id", "shift_id", "date", name="uq_oee_machine_shift_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    machine_id: Mapped[int] = mapped_column(
        ForeignKey("machines.id", ondelete="CASCADE"), nullable=False, index=True
    )
    shift_id: Mapped[int] = mapped_column(
        ForeignKey("shifts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[date_t] = mapped_column(Date, nullable=False, index=True)

    # Cada factor en rango [0.0, 1.0].
    availability: Mapped[float] = mapped_column(Float, nullable=False)
    performance: Mapped[float] = mapped_column(Float, nullable=False)
    quality: Mapped[float] = mapped_column(Float, nullable=False)
    oee_value: Mapped[float] = mapped_column(Float, nullable=False)

    # ---- Relaciones ----
    machine: Mapped["Machine"] = relationship("Machine", back_populates="oee_records")
    shift: Mapped["Shift"] = relationship("Shift", back_populates="oee_records")

    def __repr__(self) -> str:
        return (
            f"<OEERecord machine_id={self.machine_id} shift_id={self.shift_id} "
            f"date={self.date} oee={self.oee_value:.3f}>"
        )
