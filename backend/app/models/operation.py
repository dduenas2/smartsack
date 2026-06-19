"""
Modelo OrderOperation — una operación de la ruta IMP→TUB→FON→EMP.

Una orden de producción se descompone en 4 operaciones encadenadas, una
por máquina. Cada operación tiene su propia entrada (unidades recibidas
de la operación anterior), salida (unidades buenas que pasan a la
siguiente) y desperdicio (en kg, salvo en EMP que no genera scrap).

La promoción entre operaciones es automática: cuando una operación se
marca `completed`, el router de eventos pasa la siguiente a `ready` con
`quantity_in = quantity_out` de la anterior. Así el siguiente operario
ve la operación lista en su cola sin coordinación manual.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import OperationStatus, ScrapReason, ShiftName

if TYPE_CHECKING:
    from app.models.machine import Machine
    from app.models.order import ProductionOrder
    from app.models.user import User


class OrderOperation(Base):
    __tablename__ = "order_operations"
    __table_args__ = (
        # Una orden no puede tener dos operaciones con el mismo sequence.
        UniqueConstraint("order_id", "sequence", name="uq_op_order_sequence"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    order_id: Mapped[int] = mapped_column(
        ForeignKey("production_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    machine_id: Mapped[int] = mapped_column(
        ForeignKey("machines.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # 1=IMP, 2=TUB, 3=FON, 4=EMP. Define el orden de la ruta.
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    status: Mapped[OperationStatus] = mapped_column(
        Enum(OperationStatus, name="operation_status"),
        default=OperationStatus.PENDING,
        nullable=False,
        index=True,
    )

    # Unidades recibidas de la operación anterior (0 si sequence=1).
    quantity_in: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Unidades buenas que salen y alimentan a la siguiente operación.
    quantity_out: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Desperdicio en kg. EMP siempre 0 (validado en backend).
    scrap_kg: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    scrap_reason: Mapped[Optional[ScrapReason]] = mapped_column(
        Enum(ScrapReason, name="scrap_reason"), nullable=True
    )

    planned_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    planned_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    actual_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    actual_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Quién la procesó (último operario que la tomó). El turno se rellena
    # al iniciar la operación a partir de la hora real de arranque.
    operator_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    shift: Mapped[Optional[ShiftName]] = mapped_column(
        Enum(ShiftName, name="shift_name"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ---- Relaciones ----
    order: Mapped["ProductionOrder"] = relationship(
        "ProductionOrder", back_populates="operations"
    )
    machine: Mapped["Machine"] = relationship("Machine", back_populates="operations")
    operator: Mapped[Optional["User"]] = relationship("User")

    def __repr__(self) -> str:
        return (
            f"<OrderOperation order_id={self.order_id} seq={self.sequence} "
            f"machine_id={self.machine_id} status={self.status.value}>"
        )
