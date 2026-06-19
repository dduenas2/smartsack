"""
Schemas Pydantic del panel administrativo.

Reúne las respuestas/requests de:
- /api/admin/audit  (auditoría)
- /api/admin/system (settings + health + ml-status)

Las entradas del audit log son inmutables: sólo se ofrece DTO de respuesta.
Los settings se exponen como `key/value/description` para que el panel los
pinte en una grilla genérica.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.schemas.common import ORMConfig


# -----------------------------------------------------------------------------
# Audit log
# -----------------------------------------------------------------------------
class AuditLogEntry(BaseModel):
    model_config = ORMConfig

    id: int
    actor_id: Optional[int] = None
    actor_username: Optional[str] = None
    action: str
    entity_type: str
    entity_id: Optional[int] = None
    before: Optional[Dict[str, Any]] = None
    after: Optional[Dict[str, Any]] = None
    extra: Optional[Dict[str, Any]] = None
    created_at: datetime


# -----------------------------------------------------------------------------
# System settings
# -----------------------------------------------------------------------------
class SystemSettingItem(BaseModel):
    model_config = ORMConfig

    key: str
    value: Any
    description: Optional[str] = None
    updated_by_id: Optional[int] = None
    updated_at: datetime


class SystemSettingUpdate(BaseModel):
    """Modifica un setting individual. El value se valida contra el catálogo."""

    value: Any


# -----------------------------------------------------------------------------
# System health
# -----------------------------------------------------------------------------
class HealthCheck(BaseModel):
    name: str
    status: str  # "ok" | "degraded" | "down"
    detail: Optional[str] = None
    latency_ms: Optional[float] = None


class SystemHealthResponse(BaseModel):
    overall: str  # "ok" | "degraded" | "down"
    checked_at: datetime
    checks: List[HealthCheck]
    last_etl_load_at: Optional[datetime] = None
    last_ml_prediction_at: Optional[datetime] = None
    websocket_connections: int = Field(default=0, ge=0)


# -----------------------------------------------------------------------------
# ML model status
# -----------------------------------------------------------------------------
class MLModelStatusResponse(BaseModel):
    model_loaded: bool
    model_version: Optional[str] = None
    trained_at: Optional[datetime] = None
    feature_count: Optional[int] = None
    metrics: Optional[Dict[str, Any]] = None
    last_prediction_at: Optional[datetime] = None
    predictions_count_total: int = 0
