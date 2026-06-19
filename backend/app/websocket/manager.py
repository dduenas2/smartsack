"""
ConnectionManager — gestor de conexiones WebSocket del Digital Twin.

Mantiene la lista de WebSockets activos y expone `broadcast` para publicar
mensajes JSON a todos los suscriptores autorizados. Cada conexión guarda
metadatos del usuario (role, machine_id) para filtrar el tráfico:

- Supervisor / Admin → reciben todos los mensajes (visión global de planta).
- Operador → solo recibe mensajes de su máquina asignada
  (machine_update.machine.id == user.machine_id, operation_update.operation.machine_id ==
  user.machine_id, etc.). Esto evita filtraciones cruzadas y reduce ruido
  en la UI del operario.

El filtrado se basa en el campo `machine_id` que aparece dentro del payload
del mensaje (operation.machine_id, machine.id). Si un mensaje no apunta a
ninguna máquina (p.ej. snapshots iniciales) se entrega solo al destinatario
original (no se difunde).
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from fastapi import WebSocket

log = logging.getLogger("smartsack.ws")


@dataclass
class _Subscriber:
    """Una conexión WebSocket viva con su contexto de autorización."""

    ws: WebSocket
    role: str
    machine_id: Optional[int]


def _machine_id_in(message: Dict[str, Any]) -> Optional[int]:
    """
    Extrae el machine_id al que apunta un mensaje, si está implícito en el
    payload. Devuelve None si el mensaje no es específico de máquina.
    """
    op = message.get("operation")
    if isinstance(op, dict):
        mid = op.get("machine_id")
        if isinstance(mid, int):
            return mid
    machine = message.get("machine")
    if isinstance(machine, dict):
        mid = machine.get("id")
        if isinstance(mid, int):
            return mid
    mid = message.get("machine_id")
    if isinstance(mid, int):
        return mid
    return None


class ConnectionManager:
    """Mantiene conexiones WebSocket activas y emite mensajes filtrados."""

    def __init__(self) -> None:
        self._active: List[_Subscriber] = []

    async def connect(
        self,
        websocket: WebSocket,
        *,
        role: str = "admin",
        machine_id: Optional[int] = None,
    ) -> None:
        """Acepta el handshake y registra la conexión con metadatos del usuario."""
        await websocket.accept()
        self._active.append(_Subscriber(ws=websocket, role=role, machine_id=machine_id))
        log.info(
            "WS conectado (role=%s machine_id=%s). Total activas: %d",
            role,
            machine_id,
            len(self._active),
        )

    def disconnect(self, websocket: WebSocket) -> None:
        """Quita la conexión de la lista (cuando ya está cerrada o falla)."""
        self._active = [s for s in self._active if s.ws is not websocket]
        log.info("WS desconectado. Total activas: %d", len(self._active))

    def _can_receive(self, sub: _Subscriber, message: Dict[str, Any]) -> bool:
        """
        Decide si un suscriptor debe recibir un mensaje.

        Reglas:
        - Si el rol no es 'operario' → recibe todo.
        - Si es operario y el mensaje no es específico de máquina → recibe.
        - Si es operario y el mensaje apunta a su machine_id → recibe.
        - En otro caso, se filtra.
        """
        if sub.role != "operario":
            return True
        target = _machine_id_in(message)
        if target is None:
            return True
        return sub.machine_id is not None and sub.machine_id == target

    async def broadcast(self, message: Dict[str, Any]) -> None:
        """
        Envía un mensaje JSON a los clientes autorizados.

        Si una conexión falla, se elimina silenciosamente (no rompe el broadcast
        para los demás).
        """
        dead: List[WebSocket] = []
        for sub in self._active:
            if not self._can_receive(sub, message):
                continue
            try:
                await sub.ws.send_json(message)
            except Exception as exc:  # noqa: BLE001
                log.warning("WS falló al enviar; descartando conexión: %s", exc)
                dead.append(sub.ws)
        for ws in dead:
            self.disconnect(ws)

    @property
    def active_count(self) -> int:
        return len(self._active)


# Instancia global compartida — los routers la importan desde aquí.
manager = ConnectionManager()
