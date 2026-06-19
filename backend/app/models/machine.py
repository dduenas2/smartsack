"""
Modelo Machine — máquina de la línea de producción.

Cada máquina tiene un tipo (tubuladora, impresora, fondadora, empacadora),
un estado en tiempo real (running/stopped/maintenance/idle) que alimenta el
Digital Twin, y opcionalmente la orden actual que está ejecutando.
"""

from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import MachineStatus, MachineType

if TYPE_CHECKING:
    from app.models.event import ProductionEvent
    from app.models.oee import OEERecord
    from app.models.operation import OrderOperation
    from app.models.order import ProductionOrder
    from app.models.user import User


class Machine(Base):
    __tablename__ = "machines"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    type: Mapped[MachineType] = mapped_column(
        Enum(MachineType, name="machine_type"), nullable=False, index=True
    )
    location: Mapped[Optional[str]] = mapped_column(String(64))
    status: Mapped[MachineStatus] = mapped_column(
        Enum(MachineStatus, name="machine_status"),
        default=MachineStatus.IDLE,
        nullable=False,
        index=True,
    )

    # Orden que está ejecutando ahora; nullable cuando la máquina está IDLE.
    # use_alter + post_update evita ciclos de FK al crear las tablas: la
    # FK se añade en una sentencia ALTER TABLE separada.
    current_order_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("production_orders.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )

    # ---- Relaciones ----
    current_order: Mapped[Optional["ProductionOrder"]] = relationship(
        "ProductionOrder",
        foreign_keys=[current_order_id],
        post_update=True,
    )
    orders: Mapped[List["ProductionOrder"]] = relationship(
        "ProductionOrder",
        back_populates="machine",
        foreign_keys="ProductionOrder.machine_id",
    )
    events: Mapped[List["ProductionEvent"]] = relationship(
        "ProductionEvent", back_populates="machine"
    )
    operations: Mapped[List["OrderOperation"]] = relationship(
        "OrderOperation", back_populates="machine"
    )
    oee_records: Mapped[List["OEERecord"]] = relationship(
        "OEERecord", back_populates="machine"
    )
    operators: Mapped[List["User"]] = relationship(
        "User", back_populates="machine", foreign_keys="User.machine_id"
    )

    def __repr__(self) -> str:
        return f"<Machine code={self.code!r} status={self.status.value}>"
