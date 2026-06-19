"""
Modelo User — usuario del sistema SmartSack.

Cada usuario tiene un rol (operario, supervisor, admin). Los operarios pueden
estar asociados a una máquina específica para que su vista cargue automáticamente
la información de esa estación. Las contraseñas se almacenan hasheadas con
bcrypt; nunca en texto plano.
"""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import UserRole

if TYPE_CHECKING:
    from app.models.event import ProductionEvent
    from app.models.machine import Machine


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(128))
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"), nullable=False, index=True
    )

    # Sólo aplica cuando role == OPERATOR; nullable para supervisores y admins.
    machine_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("machines.id", ondelete="SET NULL"), nullable=True
    )

    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ---- Relaciones ----
    machine: Mapped[Optional["Machine"]] = relationship(
        "Machine", foreign_keys=[machine_id], back_populates="operators"
    )
    events: Mapped[List["ProductionEvent"]] = relationship(
        "ProductionEvent", back_populates="user"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r} role={self.role.value}>"
