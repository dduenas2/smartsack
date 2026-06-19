"""
Modelo SystemSetting — configuración runtime modificable por el admin.

Lugar donde viven los toggles que deben poder cambiarse SIN redeploy:

- chatbot_enabled        : permite desactivar el chat (modo mantenimiento del LLM).
- predictions_enabled    : oculta las alertas de retraso si el modelo está caído.
- maintenance_mode       : banner global "estamos en mantenimiento" en la SPA.

Forma genérica clave-valor para que añadir un setting nuevo no requiera
migración: se INSERT-a la fila la primera vez que el admin lo activa. El
servicio que consulta el setting siempre tiene un default de fallback.

Los valores se guardan como JSON para poder representar booleanos, números,
strings y estructuras compuestas en el futuro (ej. lista de IPs en allowlist).
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import JSON, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class SystemSetting(Base):
    __tablename__ = "system_settings"

    # La clave es el identificador estable del setting (no usamos id numérico
    # como PK para que el lookup sea siempre por nombre).
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    updated_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    updated_by: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[updated_by_id]
    )

    def __repr__(self) -> str:
        return f"<SystemSetting key={self.key!r} value={self.value!r}>"
