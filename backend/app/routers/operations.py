"""
Router de operaciones — la unidad de trabajo del operario.

Una operación es una etapa de la ruta IMP→TUB→FON→EMP. El operario solo
ve operaciones de su máquina con status `ready` o `in_progress`. Al
reportar producción, el sistema acumula sobre la operación; al completar,
promueve automáticamente la siguiente.

Endpoints:
- GET  /operations               — lista filtrada (machine_id, status, etc.)
- GET  /operations/{id}          — detalle con orden y máquina anidadas
- POST /operations/{id}/start    — el operario toma la operación (ready→in_progress)
- POST /operations/{id}/report   — reporte de producción + scrap
- POST /operations/{id}/complete — cierra la operación y promueve la siguiente
- GET  /orders/{id}/operations   — todas las operaciones de una orden (trazabilidad)
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_active_user
from app.models import (
    EventType,
    Machine,
    MachineStatus,
    OperationStatus,
    OrderOperation,
    OrderStatus,
    ProductionEvent,
    ProductionOrder,
    ScrapReason,
    ShiftName,
    User,
    UserRole,
    MachineType,
)
from app.schemas import OperationResponse
from app.schemas.operation import (
    OperationMachineSummary,
    OperationOrderSummary,
    OperationProductionReport,
)
from app.websocket.manager import manager as ws_manager


router = APIRouter(prefix="/operations", tags=["operations"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _determine_shift(dt: datetime) -> ShiftName:
    h = dt.hour
    if 6 <= h < 14:
        return ShiftName.TURNO_1
    if 14 <= h < 22:
        return ShiftName.TURNO_2
    return ShiftName.TURNO_3


def _build_response(op: OrderOperation, db: Session) -> OperationResponse:
    """Empaqueta una operación con resumen de orden y máquina anidados."""
    response = OperationResponse.model_validate(op)
    order = db.get(ProductionOrder, op.order_id)
    machine = db.get(Machine, op.machine_id)
    if order is not None:
        response.order = OperationOrderSummary.model_validate(order)
    if machine is not None:
        response.machine = OperationMachineSummary.model_validate(machine)
    return response


def _ws_payload(op: OrderOperation, db: Session) -> Dict[str, Any]:
    return _build_response(op, db).model_dump(mode="json")


async def _broadcast_op_and_machine(
    op: OrderOperation, event: ProductionEvent, db: Session
) -> None:
    """
    Emite dos mensajes WebSocket:
    - `operation_update` con la operación entera (consumido por la cola del
      operario y futuras vistas de trazabilidad).
    - `machine_update` con el formato compatible con SupervisorView para que
      las animaciones flash y el ticker en vivo sigan funcionando como antes.
    """
    machine = db.get(Machine, op.machine_id)
    event_payload = {
        "id": event.id,
        "event_type": event.event_type.value,
        "description": event.description,
        "timestamp": event.timestamp.isoformat(),
        "user_id": event.user_id,
        "quantity": event.quantity,
        "scrap_kg": event.scrap_kg,
    }
    await ws_manager.broadcast(
        {
            "type": "operation_update",
            "operation": _ws_payload(op, db),
            "event": event_payload,
        }
    )
    if machine is not None:
        # Importación tardía para evitar ciclo (machines → operations).
        from app.routers.machines import _machine_ws_payload
        await ws_manager.broadcast(
            {
                "type": "machine_update",
                "machine": _machine_ws_payload(machine, db),
                "event": event_payload,
            }
        )


def _ensure_operator_owns_machine(user: User, machine_id: int) -> None:
    if user.role == UserRole.OPERATOR and user.machine_id != machine_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sólo puede operar sobre su máquina asignada",
        )


def _get_operation_or_404(db: Session, operation_id: int) -> OrderOperation:
    op = db.get(OrderOperation, operation_id)
    if op is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Operación no encontrada"
        )
    return op


# ---------------------------------------------------------------------------
# GET /operations
# ---------------------------------------------------------------------------
@router.get("", response_model=List[OperationResponse], summary="Listar operaciones")
def list_operations(
    machine_id: Optional[int] = Query(default=None),
    order_id: Optional[int] = Query(default=None),
    status_in: Optional[List[OperationStatus]] = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_active_user),
) -> List[OperationResponse]:
    """
    Lista operaciones con filtros. La cola del operario consulta:
        ?machine_id=X&status=ready&status=in_progress
    """
    stmt = select(OrderOperation)
    if machine_id is not None:
        stmt = stmt.where(OrderOperation.machine_id == machine_id)
    if order_id is not None:
        stmt = stmt.where(OrderOperation.order_id == order_id)
    if status_in:
        stmt = stmt.where(OrderOperation.status.in_(status_in))
    stmt = stmt.order_by(OrderOperation.planned_start.asc()).limit(limit)
    items = list(db.scalars(stmt))
    return [_build_response(op, db) for op in items]


# ---------------------------------------------------------------------------
# GET /operations/{id}
# ---------------------------------------------------------------------------
@router.get("/{operation_id}", response_model=OperationResponse, summary="Detalle de operación")
def get_operation(
    operation_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_active_user),
) -> OperationResponse:
    op = _get_operation_or_404(db, operation_id)
    return _build_response(op, db)


# ---------------------------------------------------------------------------
# POST /operations/{id}/start  — el operario toma la operación
# ---------------------------------------------------------------------------
@router.post(
    "/{operation_id}/start",
    response_model=OperationResponse,
    summary="Iniciar una operación que está READY",
)
async def start_operation(
    operation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> OperationResponse:
    op = _get_operation_or_404(db, operation_id)
    _ensure_operator_owns_machine(user, op.machine_id)

    if op.status != OperationStatus.READY:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"La operación está en estado {op.status.value}, no READY",
        )

    now = datetime.now(tz=timezone.utc)
    op.status = OperationStatus.IN_PROGRESS
    op.actual_start = now
    op.operator_id = user.id
    op.shift = _determine_shift(now)

    # Actualizar la máquina y la orden cabecera
    machine = db.get(Machine, op.machine_id)
    if machine is not None:
        machine.status = MachineStatus.RUNNING
        machine.current_order_id = op.order_id
    order = db.get(ProductionOrder, op.order_id)
    if order is not None:
        if order.status == OrderStatus.PENDING:
            order.status = OrderStatus.IN_PROGRESS
        if order.actual_start is None:
            order.actual_start = now
        order.machine_id = op.machine_id

    # Evento START vinculado a la operación
    event = ProductionEvent(
        machine_id=op.machine_id,
        order_id=op.order_id,
        operation_id=op.id,
        user_id=user.id,
        event_type=EventType.START,
        description=f"Inicio op{op.sequence} ({machine.code if machine else op.machine_id})",
        timestamp=now,
    )
    db.add(event)
    db.commit()
    db.refresh(op)

    await _broadcast_op_and_machine(op, event, db)
    return _build_response(op, db)


# ---------------------------------------------------------------------------
# POST /operations/{id}/report  — producción + scrap
# ---------------------------------------------------------------------------
@router.post(
    "/{operation_id}/report",
    response_model=OperationResponse,
    summary="Reportar producción + scrap en una operación en curso",
)
async def report_production(
    operation_id: int,
    payload: OperationProductionReport,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> OperationResponse:
    op = _get_operation_or_404(db, operation_id)
    _ensure_operator_owns_machine(user, op.machine_id)

    if op.status != OperationStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"La operación está en estado {op.status.value}, no IN_PROGRESS",
        )

    if payload.quantity == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="quantity debe ser distinto de cero",
        )

    machine = db.get(Machine, op.machine_id)
    is_emp = machine is not None and machine.type == MachineType.EMPACADORA

    if is_emp and payload.scrap_kg and payload.scrap_kg > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La empacadora no genera desperdicio: scrap_kg debe ser 0",
        )
    if (payload.scrap_kg or 0) > 0 and payload.scrap_reason is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="scrap_reason es obligatorio cuando scrap_kg > 0",
        )

    new_out = (op.quantity_out or 0) + payload.quantity
    if new_out < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Corrección demasiado grande: el acumulado quedaría en {new_out}",
        )
    if op.quantity_in > 0 and new_out > op.quantity_in:
        # Permitido pero inusual: el operario está reportando más de lo que entró.
        # En la práctica significa una corrección al alza por reconteo.
        pass

    op.quantity_out = new_out
    if payload.scrap_kg:
        op.scrap_kg = round((op.scrap_kg or 0.0) + payload.scrap_kg, 3)
        if payload.scrap_reason:
            op.scrap_reason = payload.scrap_reason

    # Acumular en la orden cabecera
    order = db.get(ProductionOrder, op.order_id)
    if order is not None:
        if is_emp:
            # Lo que sale de EMP es el producto bueno final
            order.quantity_produced = (order.quantity_produced or 0) + payload.quantity
        if payload.scrap_kg:
            order.scrap_total_kg = round(
                (order.scrap_total_kg or 0.0) + payload.scrap_kg, 3
            )

    event = ProductionEvent(
        machine_id=op.machine_id,
        order_id=op.order_id,
        operation_id=op.id,
        user_id=user.id,
        event_type=EventType.PRODUCTION_UPDATE,
        description=payload.description
        or f"Reporte op{op.sequence}: +{payload.quantity} unidades",
        timestamp=datetime.now(tz=timezone.utc),
        quantity=payload.quantity,
        scrap_kg=payload.scrap_kg if payload.scrap_kg else None,
        scrap_reason=payload.scrap_reason,
    )
    db.add(event)
    db.commit()
    db.refresh(op)

    await _broadcast_op_and_machine(op, event, db)
    return _build_response(op, db)


# ---------------------------------------------------------------------------
# POST /operations/{id}/complete  — cierra y promueve la siguiente
# ---------------------------------------------------------------------------
@router.post(
    "/{operation_id}/complete",
    response_model=OperationResponse,
    summary="Cerrar la operación y promover la siguiente a READY",
)
async def complete_operation(
    operation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> OperationResponse:
    op = _get_operation_or_404(db, operation_id)
    _ensure_operator_owns_machine(user, op.machine_id)

    if op.status != OperationStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"La operación está en estado {op.status.value}, no IN_PROGRESS",
        )

    now = datetime.now(tz=timezone.utc)
    op.status = OperationStatus.COMPLETED
    op.actual_end = now

    # ---- Promoción automática de la siguiente operación ----
    next_op = db.scalar(
        select(OrderOperation).where(
            OrderOperation.order_id == op.order_id,
            OrderOperation.sequence == op.sequence + 1,
        )
    )
    if next_op is not None and next_op.status == OperationStatus.PENDING:
        next_op.status = OperationStatus.READY
        next_op.quantity_in = op.quantity_out

    # ---- Si era la última operación (EMP), cerrar la orden ----
    machine = db.get(Machine, op.machine_id)
    order = db.get(ProductionOrder, op.order_id)
    if next_op is None and order is not None:
        # Era EMP: producto terminado a inventario
        order.status = OrderStatus.COMPLETED
        order.actual_end = now
        order.machine_id = None

    # ---- Liberar la máquina (pasa a IDLE) ----
    if machine is not None:
        machine.status = MachineStatus.IDLE
        machine.current_order_id = None

    # Evento END
    event = ProductionEvent(
        machine_id=op.machine_id,
        order_id=op.order_id,
        operation_id=op.id,
        user_id=user.id,
        event_type=EventType.END,
        description=f"Fin op{op.sequence}",
        timestamp=now,
    )
    db.add(event)
    db.commit()
    db.refresh(op)

    await _broadcast_op_and_machine(op, event, db)
    if next_op is not None:
        # Notificar al operario de la siguiente máquina que tiene trabajo listo
        await ws_manager.broadcast(
            {
                "type": "operation_promoted",
                "operation": _ws_payload(next_op, db),
            }
        )
    return _build_response(op, db)


# ---------------------------------------------------------------------------
# GET /orders/{order_id}/operations  — vista trazabilidad
# ---------------------------------------------------------------------------
trace_router = APIRouter(prefix="/orders", tags=["operations"])


@trace_router.get(
    "/{order_id}/operations",
    response_model=List[OperationResponse],
    summary="Trazabilidad: las 4 operaciones de una orden",
)
def list_order_operations(
    order_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_active_user),
) -> List[OperationResponse]:
    if db.get(ProductionOrder, order_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Orden no encontrada"
        )
    items = list(
        db.scalars(
            select(OrderOperation)
            .where(OrderOperation.order_id == order_id)
            .order_by(OrderOperation.sequence.asc())
        )
    )
    return [_build_response(op, db) for op in items]
