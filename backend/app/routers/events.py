"""
Router de eventos de producción.

Los eventos son la bitácora inmutable que alimenta el cálculo de OEE y el
modelo de ML. Reglas:

- Cualquier usuario autenticado puede listarlos (para auditoría / dashboards).
- Cualquier usuario autenticado puede registrar uno: el `user_id` se toma
  del JWT y NO se acepta desde el cliente.
- Los OPERARIOS solo pueden registrar eventos sobre su máquina asignada.
- No se permite editar ni borrar (audit log inmutable).
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_active_user
from app.models import (
    EventType,
    Machine,
    MachineStatus,
    ProductionEvent,
    ProductionOrder,
    User,
    UserRole,
)
from app.schemas import (
    PaginatedResponse,
    ProductionEventCreate,
    ProductionEventResponse,
)
from app.websocket.manager import manager as ws_manager


router = APIRouter(prefix="/events", tags=["events"])


# Mapeo: tipo de evento → estado en el que queda la máquina tras registrarlo.
# None significa "no tocar el estado de la máquina".
_EVENT_TO_MACHINE_STATUS = {
    EventType.START: "running",
    EventType.RESUME: "running",
    EventType.STOP: "stopped",
    EventType.PAUSE: "stopped",
    EventType.MAINTENANCE: "maintenance",
    EventType.END: "idle",
}


@router.get(
    "",
    response_model=PaginatedResponse[ProductionEventResponse],
    summary="Listar eventos de producción con filtros",
)
def list_events(
    machine_id: Optional[int] = Query(default=None),
    order_id: Optional[int] = Query(default=None),
    event_type: Optional[EventType] = Query(default=None),
    user_id: Optional[int] = Query(default=None),
    timestamp_from: Optional[datetime] = Query(default=None),
    timestamp_to: Optional[datetime] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_active_user),
) -> PaginatedResponse[ProductionEventResponse]:
    base = select(ProductionEvent)
    if machine_id is not None:
        base = base.where(ProductionEvent.machine_id == machine_id)
    if order_id is not None:
        base = base.where(ProductionEvent.order_id == order_id)
    if event_type is not None:
        base = base.where(ProductionEvent.event_type == event_type)
    if user_id is not None:
        base = base.where(ProductionEvent.user_id == user_id)
    if timestamp_from is not None:
        base = base.where(ProductionEvent.timestamp >= timestamp_from)
    if timestamp_to is not None:
        base = base.where(ProductionEvent.timestamp <= timestamp_to)

    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    items_stmt = (
        base.order_by(ProductionEvent.timestamp.desc()).offset(offset).limit(limit)
    )
    items = list(db.scalars(items_stmt))

    return PaginatedResponse[ProductionEventResponse](
        total=int(total),
        limit=limit,
        offset=offset,
        items=[ProductionEventResponse.model_validate(e) for e in items],
    )


@router.get(
    "/{event_id}",
    response_model=ProductionEventResponse,
    summary="Obtener un evento por id",
)
def get_event(
    event_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_active_user),
) -> ProductionEvent:
    event = db.get(ProductionEvent, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evento no encontrado")
    return event


@router.post(
    "",
    response_model=ProductionEventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un nuevo evento (operario, supervisor, admin)",
)
async def create_event(
    payload: ProductionEventCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> ProductionEvent:
    machine = db.get(Machine, payload.machine_id)
    if machine is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"machine_id={payload.machine_id} no existe",
        )

    # Operarios solo pueden registrar eventos en su máquina asignada.
    if user.role == UserRole.OPERATOR and machine.id != user.machine_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sólo puede registrar eventos sobre su máquina asignada",
        )

    order = None
    if payload.order_id is not None:
        order = db.get(ProductionOrder, payload.order_id)
        if order is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"order_id={payload.order_id} no existe",
            )

    # production_update y los demás efectos sobre el ciclo de vida de la
    # orden ahora se manejan en el router /operations (start/report/complete).
    # Aquí solo registramos eventos "auxiliares" (incident, format_change,
    # maintenance, pause/stop/resume) que afectan al estado de la máquina
    # pero no avanzan la operación.
    if payload.event_type == EventType.PRODUCTION_UPDATE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usa POST /operations/{id}/report para reportar producción",
        )

    event = ProductionEvent(
        machine_id=payload.machine_id,
        order_id=payload.order_id,
        operation_id=payload.operation_id,
        user_id=user.id,
        event_type=payload.event_type,
        description=payload.description,
        timestamp=payload.timestamp or datetime.now(tz=timezone.utc),
    )
    db.add(event)

    # Aplicar efecto secundario sobre el estado de la máquina (Digital Twin).
    new_status_value = _EVENT_TO_MACHINE_STATUS.get(payload.event_type)
    if new_status_value is not None:
        machine.status = MachineStatus(new_status_value)

    db.commit()
    db.refresh(event)
    db.refresh(machine)

    # Broadcast del nuevo estado a la vista supervisor (incluye el resumen
    # de la orden activa para que MachineTile y PlantStats no tengan que
    # hacer un fetch extra).
    #
    # Importante: pasamos `override_order_id=payload.order_id` para que el
    # tile del supervisor muestre la orden que el operario notificó, y no
    # la que `machine.current_order_id` arrastre por desincronización (p.
    # ej. operaciones IN_PROGRESS huérfanas o `complete_operation` no
    # invocado en una iteración anterior).
    from app.routers.machines import _machine_ws_payload
    await ws_manager.broadcast(
        {
            "type": "machine_update",
            "machine": _machine_ws_payload(
                machine, db, override_order_id=payload.order_id
            ),
            "event": {
                "id": event.id,
                "event_type": event.event_type.value,
                "description": event.description,
                "timestamp": event.timestamp.isoformat(),
                "user_id": event.user_id,
            },
        }
    )

    return event
