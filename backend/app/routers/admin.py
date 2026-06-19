"""
Router /api/admin — panel administrativo.

Agrupa tres áreas ortogonales bajo el mismo prefijo:

  · /api/admin/audit       Bitácora de acciones privilegiadas (read-only).
  · /api/admin/system/*    Settings, health del sistema, ML status.

Todos los endpoints requieren rol ADMIN. La gestión de usuarios vive en su
propio router (/api/users) para mantenerlo cerca del recurso clásico.
"""

from datetime import datetime, timezone
from time import perf_counter
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import require_roles
from app.models import (
    AdminAuditLog,
    ETLLoad,
    MLPrediction,
    SystemSetting,
    User,
    UserRole,
)
from app.schemas import PaginatedResponse
from app.schemas.admin import (
    AuditLogEntry,
    HealthCheck,
    MLModelStatusResponse,
    SystemHealthResponse,
    SystemSettingItem,
    SystemSettingUpdate,
)
from app.services import audit_service, prediction_service
from app.services.chat_service import is_llm_available
from app.websocket.manager import manager as ws_manager


router = APIRouter(prefix="/admin", tags=["admin"])


# =============================================================================
# Audit log
# =============================================================================
@router.get(
    "/audit",
    response_model=PaginatedResponse[AuditLogEntry],
    summary="Bitácora de acciones administrativas (admin)",
)
def list_audit(
    entity_type: Optional[str] = Query(default=None),
    action: Optional[str] = Query(default=None),
    actor_id: Optional[int] = Query(default=None),
    days_back: Optional[int] = Query(
        default=None, ge=0, le=365, description="Restringe a últimos N días"
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_roles(UserRole.ADMIN)),
) -> PaginatedResponse[AuditLogEntry]:
    base = select(AdminAuditLog)
    if entity_type:
        base = base.where(AdminAuditLog.entity_type == entity_type)
    if action:
        base = base.where(AdminAuditLog.action == action)
    if actor_id is not None:
        base = base.where(AdminAuditLog.actor_id == actor_id)
    if days_back is not None:
        from datetime import timedelta

        anchor = datetime.now(tz=timezone.utc) - timedelta(days=days_back)
        base = base.where(AdminAuditLog.created_at >= anchor)

    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    items = list(
        db.scalars(
            base.order_by(AdminAuditLog.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    )
    return PaginatedResponse[AuditLogEntry](
        total=int(total),
        limit=limit,
        offset=offset,
        items=[AuditLogEntry.model_validate(e) for e in items],
    )


# =============================================================================
# System settings
# =============================================================================
# Catálogo: define qué claves son legítimas y su default. Si el admin pide una
# clave nueva la rechazamos para evitar que cualquier string se cree
# automáticamente — esto da control sobre la superficie de configuración.
SETTINGS_CATALOG = {
    "chatbot_enabled": {
        "default": True,
        "description": "Si está deshabilitado, /api/chat responde 503 sin consultar el LLM.",
        "type": bool,
    },
    "predictions_enabled": {
        "default": True,
        "description": "Oculta las alertas de retraso si el modelo está caído o en revisión.",
        "type": bool,
    },
    "maintenance_mode": {
        "default": False,
        "description": "Activa un banner global de mantenimiento en la SPA.",
        "type": bool,
    },
}


def _coerce_setting_value(key: str, raw: object) -> object:
    """Valida y convierte el valor según el tipo declarado en el catálogo."""
    expected = SETTINGS_CATALOG[key]["type"]
    if expected is bool:
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str):
            return raw.strip().lower() in ("1", "true", "yes", "on")
        if isinstance(raw, int):
            return bool(raw)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'{key}' espera un booleano",
        )
    return raw


def _ensure_settings_seeded(db: Session) -> None:
    """Crea filas con defaults del catálogo si aún no existen."""
    existing = {
        s.key for s in db.scalars(select(SystemSetting))
    }
    for key, meta in SETTINGS_CATALOG.items():
        if key in existing:
            continue
        db.add(
            SystemSetting(
                key=key, value=meta["default"], description=meta["description"]
            )
        )
    if existing != set(SETTINGS_CATALOG.keys()):
        db.commit()


@router.get(
    "/system/settings",
    response_model=List[SystemSettingItem],
    summary="Lista los settings runtime con sus valores actuales (admin)",
)
def list_settings(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_roles(UserRole.ADMIN)),
) -> List[SystemSetting]:
    _ensure_settings_seeded(db)
    return list(db.scalars(select(SystemSetting).order_by(SystemSetting.key)))


@router.patch(
    "/system/settings/{key}",
    response_model=SystemSettingItem,
    summary="Modificar un setting runtime (admin)",
)
def update_setting(
    key: str,
    payload: SystemSettingUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.ADMIN)),
) -> SystemSetting:
    if key not in SETTINGS_CATALOG:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Setting '{key}' no existe en el catálogo",
        )
    _ensure_settings_seeded(db)

    setting = db.get(SystemSetting, key)
    before_value = setting.value if setting else None
    new_value = _coerce_setting_value(key, payload.value)

    if setting is None:
        setting = SystemSetting(
            key=key,
            value=new_value,
            description=SETTINGS_CATALOG[key]["description"],
            updated_by_id=admin.id,
        )
        db.add(setting)
    else:
        setting.value = new_value
        setting.updated_by_id = admin.id

    audit_service.log_admin_action(
        db,
        actor=admin,
        action="update_setting",
        entity_type="setting",
        entity_id=None,
        before={"key": key, "value": before_value},
        after={"key": key, "value": new_value},
    )
    db.commit()
    db.refresh(setting)
    return setting


# =============================================================================
# System health
# =============================================================================
def _check_db(db: Session) -> HealthCheck:
    t0 = perf_counter()
    try:
        db.execute(text("SELECT 1"))
        return HealthCheck(
            name="postgres",
            status="ok",
            latency_ms=round((perf_counter() - t0) * 1000, 2),
        )
    except SQLAlchemyError as exc:
        return HealthCheck(name="postgres", status="down", detail=str(exc))


def _check_redis() -> HealthCheck:
    """Best-effort redis check — no falla la respuesta global si no hay cliente."""
    try:
        import redis  # type: ignore

        from app.config import settings

        client = redis.from_url(settings.redis_url, socket_connect_timeout=1.0)
        t0 = perf_counter()
        client.ping()
        return HealthCheck(
            name="redis",
            status="ok",
            latency_ms=round((perf_counter() - t0) * 1000, 2),
        )
    except Exception as exc:  # noqa: BLE001
        return HealthCheck(name="redis", status="down", detail=str(exc))


def _check_llm() -> HealthCheck:
    """Sólo confirma si la API key parece real — no consume cuota."""
    if is_llm_available():
        return HealthCheck(name="anthropic", status="ok", detail="API key configurada")
    return HealthCheck(
        name="anthropic",
        status="degraded",
        detail="Sin API key válida — chatbot en modo fallback",
    )


def _check_ml_model() -> HealthCheck:
    info = prediction_service.get_model_info()
    if info.get("loaded"):
        return HealthCheck(
            name="ml_model",
            status="ok",
            detail=f"version={info.get('version', '?')}",
        )
    return HealthCheck(
        name="ml_model", status="degraded", detail="Modelo no cargado en memoria"
    )


@router.get(
    "/system/health",
    response_model=SystemHealthResponse,
    summary="Estado agregado de los componentes externos (admin)",
)
def system_health(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_roles(UserRole.ADMIN)),
) -> SystemHealthResponse:
    checks = [_check_db(db), _check_redis(), _check_llm(), _check_ml_model()]

    last_etl = db.scalar(
        select(ETLLoad.uploaded_at).order_by(ETLLoad.uploaded_at.desc()).limit(1)
    )
    last_pred = db.scalar(
        select(MLPrediction.created_at)
        .order_by(MLPrediction.created_at.desc())
        .limit(1)
    )

    has_down = any(c.status == "down" for c in checks)
    has_degraded = any(c.status == "degraded" for c in checks)
    overall = "down" if has_down else ("degraded" if has_degraded else "ok")

    return SystemHealthResponse(
        overall=overall,
        checked_at=datetime.now(tz=timezone.utc),
        checks=checks,
        last_etl_load_at=last_etl,
        last_ml_prediction_at=last_pred,
        websocket_connections=ws_manager.active_count,
    )


# =============================================================================
# ML model status
# =============================================================================
@router.get(
    "/system/ml-status",
    response_model=MLModelStatusResponse,
    summary="Detalle del modelo ML cargado en memoria (admin)",
)
def ml_status(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_roles(UserRole.ADMIN)),
) -> MLModelStatusResponse:
    info = prediction_service.get_model_info()
    last_pred_at = db.scalar(
        select(MLPrediction.created_at)
        .order_by(MLPrediction.created_at.desc())
        .limit(1)
    )
    total = int(db.scalar(select(func.count()).select_from(MLPrediction)) or 0)
    # `models` contiene métricas de RF y XGB cuando el manifest está disponible.
    metrics = info.get("models") or info.get("metrics")
    return MLModelStatusResponse(
        model_loaded=bool(info.get("loaded")),
        model_version=info.get("version"),
        trained_at=info.get("trained_at"),
        feature_count=info.get("feature_count"),
        metrics=metrics,
        last_prediction_at=last_pred_at,
        predictions_count_total=total,
    )
