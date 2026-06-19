"""
Modelo ETLLoad — historial de cargas ETL desde el ERP (SAP).

Cada vez que un supervisor sube un CSV o un job programado lo procesa, se
inserta una fila aquí con el resumen: cuántas filas se aceptaron, cuántas
se descartaron por duplicado, cuántas fallaron y el detalle de errores en
JSON. Es la fuente de verdad para auditoría y depuración del ETL.
"""

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class ETLLoadKind(str, enum.Enum):
    """Tipos de archivo CSV soportados por el ETL."""

    PRODUCTION_ORDERS = "production_orders"
    CONFIRMATIONS = "confirmations"
    MATERIALS = "materials"
    SHIPMENTS = "shipments"


class ETLLoadStatus(str, enum.Enum):
    """Resultado global de una carga."""

    PENDING = "pending"
    SUCCESS = "success"      # Todas las filas válidas insertadas/actualizadas.
    PARTIAL = "partial"      # Al menos una fila falló pero el resto se cargó.
    FAILED = "failed"        # Toda la carga abortó (ej. CSV ilegible).


class ETLLoad(Base):
    __tablename__ = "etl_loads"

    id: Mapped[int] = mapped_column(primary_key=True)

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[ETLLoadKind] = mapped_column(
        Enum(ETLLoadKind, name="etl_load_kind"), nullable=False, index=True
    )
    status: Mapped[ETLLoadStatus] = mapped_column(
        Enum(ETLLoadStatus, name="etl_load_status"),
        default=ETLLoadStatus.PENDING,
        nullable=False,
        index=True,
    )

    uploaded_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # Contadores del resultado de la carga.
    rows_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_inserted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_skipped: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Tiempo total del parser+commit, en milisegundos.
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Hasta N errores por fila + posibles errores globales.
    # Estructura: { "global": [str], "rows": [ {row_number, field, error, raw} ] }
    error_log: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)

    # ---- Relaciones ----
    uploaded_by: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[uploaded_by_id]
    )

    def __repr__(self) -> str:
        return (
            f"<ETLLoad id={self.id} kind={self.kind.value} status={self.status.value} "
            f"ok={self.rows_inserted + self.rows_updated}/{self.rows_total}>"
        )
