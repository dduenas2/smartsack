"""
Router CRUD de órdenes de producción.

Permisos:
- GET   : cualquier usuario autenticado.
- POST  : ADMIN o SUPERVISOR.
- PATCH : ADMIN, SUPERVISOR (y OPERARIO sobre órdenes asignadas a su máquina).
- DELETE: solo ADMIN.

Filtros expuestos en la lista:
- status, priority, machine_id, product_type, planned_start_from/to.
- limit/offset para paginación.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_active_user, require_roles
from app.models import (
    Machine,
    OrderPriority,
    OrderStatus,
    ProductionOrder,
    User,
    UserRole,
)
from app.schemas import (
    PaginatedResponse,
    ProductionOrderCreate,
    ProductionOrderResponse,
    ProductionOrderUpdate,
)
from app.services import audit_service
from app.services.etl_service import create_operations_for_order


router = APIRouter(prefix="/orders", tags=["orders"])


# -----------------------------------------------------------------------------
# Listado con filtros + paginación
# -----------------------------------------------------------------------------
@router.get(
    "",
    response_model=PaginatedResponse[ProductionOrderResponse],
    summary="Listar órdenes con filtros y paginación",
)
def list_orders(
    status_filter: Optional[OrderStatus] = Query(default=None, alias="status"),
    priority: Optional[OrderPriority] = Query(default=None),
    machine_id: Optional[int] = Query(default=None),
    product_type: Optional[str] = Query(default=None),
    planned_start_from: Optional[datetime] = Query(default=None),
    planned_start_to: Optional[datetime] = Query(default=None),
    sort: str = Query(
        default="planned_start_desc",
        description="planned_start_desc | created_at_desc",
    ),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_active_user),
) -> PaginatedResponse[ProductionOrderResponse]:
    base = select(ProductionOrder)
    if status_filter is not None:
        base = base.where(ProductionOrder.status == status_filter)
    if priority is not None:
        base = base.where(ProductionOrder.priority == priority)
    if machine_id is not None:
        base = base.where(ProductionOrder.machine_id == machine_id)
    if product_type is not None:
        base = base.where(ProductionOrder.product_type == product_type)
    if planned_start_from is not None:
        base = base.where(ProductionOrder.planned_start >= planned_start_from)
    if planned_start_to is not None:
        base = base.where(ProductionOrder.planned_start <= planned_start_to)

    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0

    # El panel admin necesita ver primero las órdenes recién creadas; el
    # resto del sistema sigue prefiriendo el orden por planificación.
    sort_column = (
        ProductionOrder.created_at.desc()
        if sort == "created_at_desc"
        else ProductionOrder.planned_start.desc()
    )
    items_stmt = base.order_by(sort_column).offset(offset).limit(limit)
    items = list(db.scalars(items_stmt))

    return PaginatedResponse[ProductionOrderResponse](
        total=int(total),
        limit=limit,
        offset=offset,
        items=[ProductionOrderResponse.model_validate(o) for o in items],
    )


@router.get(
    "/{order_id}",
    response_model=ProductionOrderResponse,
    summary="Obtener una orden por id",
)
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_active_user),
) -> ProductionOrder:
    order = db.get(ProductionOrder, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orden no encontrada")
    return order


# -----------------------------------------------------------------------------
# Mutaciones
# -----------------------------------------------------------------------------
@router.post(
    "",
    response_model=ProductionOrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una nueva orden de producción (admin o supervisor)",
)
def create_order(
    payload: ProductionOrderCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPERVISOR)),
) -> ProductionOrder:
    if db.scalar(
        select(ProductionOrder).where(ProductionOrder.order_number == payload.order_number)
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe una orden con número '{payload.order_number}'",
        )
    anchor_machine: Optional[Machine] = None
    if payload.machine_id is not None:
        anchor_machine = db.get(Machine, payload.machine_id)
        if anchor_machine is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"machine_id={payload.machine_id} no existe",
            )

    order = ProductionOrder(**payload.model_dump())
    db.add(order)
    db.flush()

    # Auto-crear la cadena de operaciones para que el operario asignado a esa
    # máquina pueda tomar la orden desde /operator de inmediato. Sin esto la
    # orden existe sólo a nivel cabecera y no aparece en la cola.
    if anchor_machine is not None:
        create_operations_for_order(db, order, anchor_machine)

    audit_service.log_admin_action(
        db,
        actor=user,
        action="create",
        entity_type="order",
        entity_id=order.id,
        after=audit_service.serialize_order(order),
    )
    db.commit()
    db.refresh(order)
    return order


@router.patch(
    "/{order_id}",
    response_model=ProductionOrderResponse,
    summary="Actualizar parcialmente una orden",
)
def update_order(
    order_id: int,
    payload: ProductionOrderUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> ProductionOrder:
    order = db.get(ProductionOrder, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orden no encontrada")

    # Reglas de autorización por rol.
    is_admin_or_super = user.role in (UserRole.ADMIN, UserRole.SUPERVISOR)
    is_assigned_operator = (
        user.role == UserRole.OPERATOR
        and user.machine_id is not None
        and order.machine_id == user.machine_id
    )
    if not (is_admin_or_super or is_assigned_operator):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para modificar esta orden",
        )

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(order, field, value)

    db.commit()
    db.refresh(order)
    return order


@router.delete(
    "/{order_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar una orden (solo admin)",
)
def delete_order(
    order_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.ADMIN)),
) -> None:
    order = db.get(ProductionOrder, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orden no encontrada")
    audit_service.log_admin_action(
        db,
        actor=admin,
        action="delete",
        entity_type="order",
        entity_id=order.id,
        before=audit_service.serialize_order(order),
    )
    db.delete(order)
    db.commit()
