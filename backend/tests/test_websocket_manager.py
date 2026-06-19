"""
Tests del ConnectionManager — filtrado de broadcasts por rol/máquina.

No abre WebSockets reales. Sustituimos cada conexión por un mock asíncrono
que captura `send_json` y verificamos qué mensajes habría recibido cada
suscriptor según las reglas:
- supervisor / admin → todo.
- operario → solo mensajes de su machine_id.
"""

from __future__ import annotations

import pytest

from app.websocket.manager import ConnectionManager


class _FakeWS:
    """Stub mínimo que cumple con el contrato (.accept, .send_json) del manager."""

    def __init__(self) -> None:
        self.received: list[dict] = []
        self.accepted = False

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, msg: dict) -> None:
        self.received.append(msg)


@pytest.mark.asyncio
async def test_operator_only_receives_messages_for_own_machine() -> None:
    mgr = ConnectionManager()
    ws_op_a = _FakeWS()
    ws_op_b = _FakeWS()
    ws_sup = _FakeWS()
    await mgr.connect(ws_op_a, role="operario", machine_id=1)
    await mgr.connect(ws_op_b, role="operario", machine_id=2)
    await mgr.connect(ws_sup, role="supervisor", machine_id=None)

    # Mensaje específico de la máquina 1 (formato machine_update).
    await mgr.broadcast(
        {"type": "machine_update", "machine": {"id": 1, "code": "IMP-01"}}
    )
    assert len(ws_op_a.received) == 1
    assert len(ws_op_b.received) == 0  # no ve la otra máquina
    assert len(ws_sup.received) == 1

    # Mensaje de operación en máquina 2 (formato operation_update).
    await mgr.broadcast(
        {"type": "operation_update", "operation": {"id": 99, "machine_id": 2}}
    )
    assert len(ws_op_a.received) == 1
    assert len(ws_op_b.received) == 1
    assert len(ws_sup.received) == 2


@pytest.mark.asyncio
async def test_admin_receives_everything() -> None:
    mgr = ConnectionManager()
    ws = _FakeWS()
    await mgr.connect(ws, role="admin", machine_id=None)

    for mid in (1, 2, 3):
        await mgr.broadcast(
            {"type": "machine_update", "machine": {"id": mid}}
        )
    assert len(ws.received) == 3


@pytest.mark.asyncio
async def test_message_without_machine_target_reaches_all() -> None:
    """Mensajes sin machine_id (ej. ping global) llegan a todos."""
    mgr = ConnectionManager()
    ws_op = _FakeWS()
    ws_sup = _FakeWS()
    await mgr.connect(ws_op, role="operario", machine_id=1)
    await mgr.connect(ws_sup, role="supervisor", machine_id=None)

    await mgr.broadcast({"type": "ping"})
    assert len(ws_op.received) == 1
    assert len(ws_sup.received) == 1


@pytest.mark.asyncio
async def test_disconnect_removes_subscriber() -> None:
    mgr = ConnectionManager()
    ws = _FakeWS()
    await mgr.connect(ws, role="supervisor", machine_id=None)
    assert mgr.active_count == 1
    mgr.disconnect(ws)
    assert mgr.active_count == 0


@pytest.mark.asyncio
async def test_failed_send_drops_subscriber() -> None:
    """Si `send_json` falla, la conexión se elimina silenciosamente."""

    class BrokenWS(_FakeWS):
        async def send_json(self, msg: dict) -> None:  # noqa: D401, ARG002
            raise RuntimeError("conexión cerrada")

    mgr = ConnectionManager()
    healthy = _FakeWS()
    broken = BrokenWS()
    await mgr.connect(healthy, role="supervisor", machine_id=None)
    await mgr.connect(broken, role="supervisor", machine_id=None)

    await mgr.broadcast({"type": "machine_update", "machine": {"id": 7}})
    # La sana recibe, la rota se descarta.
    assert len(healthy.received) == 1
    assert mgr.active_count == 1
