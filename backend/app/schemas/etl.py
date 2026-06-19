"""
Schemas Pydantic del módulo ETL.

DTOs para el historial de cargas (`/api/etl/status`) y la respuesta del
endpoint de upload. El error_log se expone como dict permisivo: el frontend
sabe interpretarlo (estructura `{ global: [str], rows: [...] }`).
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.models import ETLLoadKind, ETLLoadStatus
from app.schemas.common import ORMConfig


class ETLLoadResponse(BaseModel):
    """Una fila del historial de cargas ETL."""

    model_config = ORMConfig

    id: int
    filename: str
    kind: ETLLoadKind
    status: ETLLoadStatus
    uploaded_by_id: Optional[int] = None
    uploaded_at: datetime

    rows_total: int = Field(..., ge=0)
    rows_inserted: int = Field(..., ge=0)
    rows_updated: int = Field(..., ge=0)
    rows_skipped: int = Field(..., ge=0)
    rows_failed: int = Field(..., ge=0)

    duration_ms: int = Field(..., ge=0)
    error_log: Optional[Dict[str, Any]] = None


class ETLLoadListResponse(BaseModel):
    """Lista paginada del historial."""

    total: int
    limit: int
    offset: int
    items: List[ETLLoadResponse]
