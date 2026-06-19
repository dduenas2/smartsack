"""
Endpoint WebSocket del Digital Twin.

URL pública (a través de Nginx):
    ws://localhost/ws/plant?token=<jwt>

El token JWT se valida por query string porque el navegador no permite
adjuntar headers personalizados al handshake WebSocket. Tras la validación,
se envía un snapshot inicial con el estado de todas las máquinas y luego
el manager se encarga de difundir cambios en tiempo real.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List

import jwt
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select

from app.database import SessionLocal
from app.models import Machine, ProductionOrder
from app.services.auth_service import decode_access_token, get_user_by_username
from app.websocket.manager import manager


log = logging.getLogger("smartsack.ws")
router = APIRouter()


def _machine_to_dict(machine: Machine, order: ProductionOrder | None) -> Dict[str, Any]:
    """Serializa una máquina + su orden actual al payload que consume el frontend."""
    return {
        "id": machine.id,
        "code": machine.code,
        "name": machine.name,
        "type": machine.type.value,
        "location": machine.location,
        "status": machine.status.value,
        "current_order_id": machine.current_order_id,
        "current_order": (
            {
                "id": order.id,
                "order_number": order.order_number,
                "product_type": order.product_type,
                "quantity_ordered": order.quantity_ordered,
                "quantity_produced": order.quantity_produced,
                "status": order.status.value,
            }
            if order is not None
            else None
        ),
    }


def _build_snapshot() -> List[Dict[str, Any]]:
    """Lee de BD el estado completo de la planta. Sesión efímera y autocerrada."""
    with SessionLocal() as db:
        machines = list(db.scalars(select(Machine).order_by(Machine.code)))
        order_ids = [m.current_order_id for m in machines if m.current_order_id]
        orders_by_id: Dict[int, ProductionOrder] = {}
        if order_ids:
            for order in db.scalars(
                select(ProductionOrder).where(ProductionOrder.id.in_(order_ids))
            ):
                orders_by_id[order.id] = order
        return [
            _machine_to_dict(m, orders_by_id.get(m.current_order_id))
            for m in machines
        ]


@router.websocket("/ws/plant")
async def plant_websocket(
    websocket: WebSocket,
    token: str | None = Query(default=None),
) -> None:
    """
    Canal WebSocket compartido por la vista supervisor.

    Flujo:
    1. Valida el token JWT recibido por query string.
    2. Acepta la conexión y la registra en el ConnectionManager.
    3. Envía un snapshot inicial con todas las máquinas + sus órdenes actuales.
    4. Quedará escuchando hasta que el cliente cierre o falle el envío.
    """
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError as exc:
        log.warning("WS rechazado: token inválido (%s)", exc)
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    username = payload.get("sub")
    if not username:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Validar que el usuario sigue activo en la BD.
    with SessionLocal() as db:
        user = get_user_by_username(db, username)
        if user is None or not user.is_active:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        user_role = user.role.value
        user_machine_id = user.machine_id

    await manager.connect(websocket, role=user_role, machine_id=user_machine_id)
    try:
        # Snapshot inicial para que el cliente pinte el estado actual.
        snapshot = _build_snapshot()
        await websocket.send_json({"type": "snapshot", "machines": snapshot})

        # Bucle de mantenimiento: respondemos pings o lo que mande el cliente.
        # No esperamos mensajes de aplicación reales; usamos receive_text para
        # detectar cierre limpio del cliente.
        while True:
            try:
                # Espera con timeout: si no llega nada en 30s, mandamos un ping
                # vacío para mantener la conexión viva tras el reverse proxy.
                await asyncio.wait_for(websocket.receive_text(), timeout=30)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        log.info("WS cerrado por el cliente")
    finally:
        manager.disconnect(websocket)
