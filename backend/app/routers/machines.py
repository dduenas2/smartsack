"""
Router CRUD de máquinas.

Permisos:
- Cualquier usuario autenticado puede listar y consultar máquinas.
- Sólo ADMIN y SUPERVISOR pueden actualizar el estado de una máquina.
- Sólo ADMIN puede crear o eliminar máquinas (catálogo cerrado de la planta).
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_active_user, require_roles
from app.models import (
    Machine,
    MachineStatus,
    MachineType,
    OperationStatus,
    OrderOperation,
    ProductionOrder,
    User,
    UserRole,
)
from app.schemas import MachineCreate, MachineResponse, MachineUpdate
from app.schemas.machine import CurrentOperationSummary, CurrentOrderSummary
from app.services import audit_service
from app.websocket.manager import manager as ws_manager


def _machine_payload(
    machine: Machine,
    db: Session,
    override_order_id: Optional[int] = None,
) -> MachineResponse:
    """
    Convierte la fila ORM a `MachineResponse` poblando el resumen anidado
    `current_order` cuando exista. Centralizado aquí para no duplicar la
    consulta en cada endpoint.

    `override_order_id` permite forzar qué orden se incrusta en el payload
    (p. ej. cuando un evento llega con un `order_id` explícito y queremos
    que el broadcast refleje esa orden, no la que `machine.current_order_id`
    apunte por desincronización).
    """
    response = MachineResponse.model_validate(machine)
    order_id_for_summary = (
        override_order_id if override_order_id is not None else machine.current_order_id
    )
    if order_id_for_summary is not None:
        order = db.get(ProductionOrder, order_id_for_summary)
        if order is not None:
            response.current_order = CurrentOrderSummary(
                id=order.id,
                order_number=order.order_number,
                product_type=order.product_type,
                quantity_ordered=order.quantity_ordered,
                quantity_produced=order.quantity_produced,
                status=order.status,
                priority=order.priority.value,
            )

    # Operación in_progress de esta máquina (si existe). Su quantity_in/out
    # es lo que pinta el dial del Digital Twin para esta máquina concreta.
    # Si se especificó `override_order_id` priorizamos la operación de esa
    # orden; si no, devolvemos la más reciente (orden estable por id DESC)
    # para evitar el no-determinismo de un `LIMIT 1` sin `ORDER BY` cuando
    # convivan varias IN_PROGRESS por mal estado de datos.
    op_stmt = (
        select(OrderOperation)
        .where(OrderOperation.machine_id == machine.id)
        .where(OrderOperation.status == OperationStatus.IN_PROGRESS)
    )
    if override_order_id is not None:
        op_stmt = op_stmt.where(OrderOperation.order_id == override_order_id)
    op = db.scalar(op_stmt.order_by(OrderOperation.id.desc()).limit(1))
    if op is not None:
        order = db.get(ProductionOrder, op.order_id)
        response.current_operation = CurrentOperationSummary(
            id=op.id,
            order_id=op.order_id,
            order_number=order.order_number if order else "",
            sequence=op.sequence,
            status=op.status,
            quantity_in=op.quantity_in,
            quantity_out=op.quantity_out,
            scrap_kg=op.scrap_kg,
        )
    return response


def _machine_ws_payload(
    machine: Machine,
    db: Session,
    override_order_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Idéntico al anterior pero como dict serializable (para WebSocket)."""
    response = _machine_payload(machine, db, override_order_id=override_order_id)
    return response.model_dump(mode="json")


router = APIRouter(prefix="/machines", tags=["machines"])


# -----------------------------------------------------------------------------
# Listado y consulta (cualquier usuario autenticado)
# -----------------------------------------------------------------------------
@router.get(
    "",
    response_model=List[MachineResponse],
    summary="Listar máquinas (con filtros opcionales)",
)
def list_machines(
    type: Optional[MachineType] = Query(default=None),
    status_filter: Optional[MachineStatus] = Query(default=None, alias="status"),
    location: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_active_user),
) -> List[MachineResponse]:
    """Devuelve todas las máquinas, opcionalmente filtradas por tipo o estado."""
    stmt = select(Machine).order_by(Machine.code)
    if type is not None:
        stmt = stmt.where(Machine.type == type)
    if status_filter is not None:
        stmt = stmt.where(Machine.status == status_filter)
    if location is not None:
        stmt = stmt.where(Machine.location == location)
    return [_machine_payload(m, db) for m in db.scalars(stmt)]


@router.get(
    "/{machine_id}",
    response_model=MachineResponse,
    summary="Obtener una máquina por id",
)
def get_machine(
    machine_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_active_user),
) -> MachineResponse:
    machine = db.get(Machine, machine_id)
    if machine is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Máquina no encontrada")
    return _machine_payload(machine, db)


# -----------------------------------------------------------------------------
# Mutaciones — restringidas por rol
# -----------------------------------------------------------------------------
@router.post(
    "",
    response_model=MachineResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una máquina (solo admin)",
)
def create_machine(
    payload: MachineCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.ADMIN)),
) -> MachineResponse:
    if db.scalar(select(Machine).where(Machine.code == payload.code)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe una máquina con código '{payload.code}'",
        )
    machine = Machine(**payload.model_dump())
    db.add(machine)
    db.flush()
    audit_service.log_admin_action(
        db,
        actor=admin,
        action="create",
        entity_type="machine",
        entity_id=machine.id,
        after=audit_service.serialize_machine(machine),
    )
    db.commit()
    db.refresh(machine)
    return _machine_payload(machine, db)


@router.patch(
    "/{machine_id}",
    response_model=MachineResponse,
    summary="Actualizar parcialmente una máquina (admin o supervisor)",
)
async def update_machine(
    machine_id: int,
    payload: MachineUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPERVISOR)),
) -> MachineResponse:
    machine = db.get(Machine, machine_id)
    if machine is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Máquina no encontrada")

    before = audit_service.serialize_machine(machine)
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(machine, field, value)

    audit_service.log_admin_action(
        db,
        actor=user,
        action="update",
        entity_type="machine",
        entity_id=machine.id,
        before=before,
        after=audit_service.serialize_machine(machine),
    )
    db.commit()
    db.refresh(machine)

    # Notificar a los supervisores conectados al Digital Twin.
    await ws_manager.broadcast(
        {"type": "machine_update", "machine": _machine_ws_payload(machine, db)}
    )

    return _machine_payload(machine, db)


@router.delete(
    "/{machine_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar una máquina (solo admin)",
)
def delete_machine(
    machine_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.ADMIN)),
) -> None:
    machine = db.get(Machine, machine_id)
    if machine is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Máquina no encontrada")

    # Validación previa: el modelo de operaciones usa ondelete=RESTRICT, así
    # que el DELETE caería con IntegrityError. Devolvemos 409 con un mensaje
    # accionable (cuántas operaciones bloquean) en vez de un 500 oscuro.
    op_count = int(
        db.scalar(
            select(func.count())
            .select_from(OrderOperation)
            .where(OrderOperation.machine_id == machine.id)
        )
        or 0
    )
    if op_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"No se puede eliminar {machine.code}: tiene {op_count} "
                "operaciones registradas en el histórico. Cámbiale el estado "
                "a 'maintenance' si deseas sacarla de servicio."
            ),
        )

    audit_service.log_admin_action(
        db,
        actor=admin,
        action="delete",
        entity_type="machine",
        entity_id=machine.id,
        before=audit_service.serialize_machine(machine),
    )
    db.delete(machine)
    db.commit()
