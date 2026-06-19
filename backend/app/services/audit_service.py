"""
Servicio de auditoría administrativa.

Punto único para escribir entradas en `admin_audit_log`. Todos los routers
privilegiados deben llamar a `log_admin_action(...)` justo después de
persistir el cambio (mismo `commit` o transacción aparte, ver detalle abajo).

Diseño:

- La función no falla aunque la auditoría no se pueda escribir: la integridad
  de la acción de negocio prima sobre la del log. Si algo va mal serializando
  un payload, se registra en `logger.exception` y se sigue.
- Los snapshots `before`/`after` se "saneadores" (`_sanitize`) para evitar que
  campos sensibles (`password_hash`) y objetos no JSON-serializables (datetimes,
  Enums, etc.) lleguen a la BD en formato problemático.
- Se almacena `actor_username` redundante para conservar la trazabilidad
  incluso si la cuenta del actor se elimina más tarde (FK on delete SET NULL).
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models import AdminAuditLog, User


logger = logging.getLogger("smartsack.audit")

# Campos que NUNCA deben aparecer en before/after — protección defensiva
# contra el filtrado accidental de credenciales o secretos.
_REDACTED_KEYS = {"password", "password_hash", "secret", "token"}


def _sanitize(value: Any) -> Any:
    """
    Normaliza valores para que sean JSON-serializables y filtra claves sensibles.

    Convierte dicts/listas recursivamente; redacta cualquier clave que coincida
    con `_REDACTED_KEYS`; serializa datetimes a ISO 8601 y Enums a su `.value`.
    """
    if value is None:
        return None
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for k, v in value.items():
            if isinstance(k, str) and k.lower() in _REDACTED_KEYS:
                out[k] = "***"
                continue
            out[k] = _sanitize(v)
        return out
    if isinstance(value, (list, tuple, set)):
        return [_sanitize(v) for v in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (str, int, float, bool)):
        return value
    # Fallback: stringificamos, mejor algo que perder la pista.
    return str(value)


def log_admin_action(
    db: Session,
    *,
    actor: Optional[User],
    action: str,
    entity_type: str,
    entity_id: Optional[int] = None,
    before: Optional[Dict[str, Any]] = None,
    after: Optional[Dict[str, Any]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Optional[AdminAuditLog]:
    """
    Registra una acción privilegiada en la bitácora.

    Devuelve la entrada creada o `None` si la escritura falló (no propagamos
    la excepción para no bloquear la acción de negocio).

    Se ESPERA que el caller haga `db.commit()` después: la entrada se añade
    a la sesión actual con `db.add(...)` para que se persista en la misma
    transacción que la acción auditada (atomicidad).
    """
    try:
        entry = AdminAuditLog(
            actor_id=actor.id if actor else None,
            actor_username=actor.username if actor else None,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before=_sanitize(before) if before is not None else None,
            after=_sanitize(after) if after is not None else None,
            extra=_sanitize(extra) if extra is not None else None,
        )
        db.add(entry)
        return entry
    except Exception:  # noqa: BLE001
        logger.exception(
            "No se pudo registrar audit log: actor=%s action=%s entity=%s#%s",
            actor.username if actor else None,
            action,
            entity_type,
            entity_id,
        )
        return None


def serialize_user(user: User) -> Dict[str, Any]:
    """Snapshot de User apto para before/after (sin password_hash)."""
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role.value,
        "machine_id": user.machine_id,
        "is_active": user.is_active,
    }


def serialize_machine(machine: Any) -> Dict[str, Any]:
    """Snapshot de Machine para before/after."""
    return {
        "id": machine.id,
        "code": machine.code,
        "name": machine.name,
        "type": machine.type.value if machine.type else None,
        "location": machine.location,
        "status": machine.status.value if machine.status else None,
    }


def serialize_order(order: Any) -> Dict[str, Any]:
    """Snapshot de ProductionOrder para before/after."""
    return {
        "id": order.id,
        "order_number": order.order_number,
        "product_type": order.product_type,
        "quantity_ordered": order.quantity_ordered,
        "machine_id": order.machine_id,
        "status": order.status.value if order.status else None,
        "priority": order.priority.value if order.priority else None,
    }
