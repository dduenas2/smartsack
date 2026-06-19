"""
Modelo Shift — turno de trabajo.

Solo existen 3 turnos en la planta (turno_1, turno_2, turno_3) y son fijos.
Es una tabla de catálogo (lookup) referenciada por OEERecord para agrupar
KPIs por turno.
"""

from datetime import time
from typing import TYPE_CHECKING, List

from sqlalchemy import Enum, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import ShiftName

if TYPE_CHECKING:
    from app.models.oee import OEERecord


class Shift(Base):
    __tablename__ = "shifts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[ShiftName] = mapped_column(
        Enum(ShiftName, name="shift_name"), unique=True, nullable=False
    )
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)

    # ---- Relaciones ----
    oee_records: Mapped[List["OEERecord"]] = relationship("OEERecord", back_populates="shift")

    def __repr__(self) -> str:
        return f"<Shift {self.name.value} {self.start_time}-{self.end_time}>"
