"""
Modelo AdminAuditLog — bitácora de acciones administrativas.

Cada acción privilegiada (crear/editar/eliminar usuarios, máquinas, órdenes,
cambios de configuración, recargas del modelo ML) deja una fila aquí con:

- actor_id        : quién la hizo (FK users, nullable si la cuenta se borró).
- action          : verbo corto ("create", "update", "delete", "reset_password",
                    "reload_model", "update_setting", ...).
- entity_type     : sobre qué entidad ("user", "machine", "order", "setting",
                    "ml_model", ...).
- entity_id       : id afectado (nullable cuando no aplica, ej. recarga modelo).
- before / after  : snapshots JSON del antes/después (campos sensibles
                    como password_hash NUNCA entran).
- metadata        : datos extra del request (ip, user agent, motivo opcional).

El log es append-only: se escribe en cada acción privilegiada y nunca se
modifica. Su consulta está limitada al rol admin desde
`/api/admin/audit`.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)

    actor_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    actor_username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)

    # Estado anterior / posterior de la entidad. None si no aplica
    # (ej. acciones que no modifican una fila concreta como reload_model).
    before: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    after: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Datos contextuales del request (ip, user-agent, motivo libre, etc.).
    extra: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    actor: Mapped[Optional["User"]] = relationship("User", foreign_keys=[actor_id])

    def __repr__(self) -> str:
        return (
            f"<AdminAuditLog id={self.id} actor={self.actor_username!r} "
            f"action={self.action!r} entity={self.entity_type}#{self.entity_id}>"
        )
