"""
Tests del router /api/operations: cola, start, report, complete, auto-promoción.
"""

from sqlalchemy import select

from app.models import OperationStatus, OrderOperation
from tests.conftest import auth_header


def test_list_operations_requires_auth(client) -> None:
    assert client.get("/api/operations").status_code == 401


def test_list_operations_for_machine(client, admin_token) -> None:
    """La cola filtra por máquina y status."""
    response = client.get(
        "/api/operations?machine_id=1&status=ready", headers=auth_header(admin_token)
    )
    assert response.status_code == 200
    items = response.json()
    # En seed, IMP-01 tiene operaciones ready (las primeras de cada orden pendiente)
    assert isinstance(items, list)
    if items:
        assert all(it["machine_id"] == 1 for it in items)
        assert all(it["status"] == "ready" for it in items)
        # Resumen de orden anidado debe estar presente
        assert "order" in items[0]
        assert "machine" in items[0]


def test_start_then_report_then_complete_flow(client, db_session, admin_token) -> None:
    """End-to-end: tomar operación → reportar → cerrar → promover siguiente."""
    # Pillar una operación READY de IMP-01
    op = db_session.scalar(
        select(OrderOperation)
        .where(OrderOperation.machine_id == 1)
        .where(OrderOperation.status == OperationStatus.READY)
        .limit(1)
    )
    assert op is not None, "El seed debería tener al menos 1 operación READY en IMP-01"
    op_id = op.id
    order_id = op.order_id

    # 1) START
    r = client.post(f"/api/operations/{op_id}/start", headers=auth_header(admin_token))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "in_progress"

    # 2) REPORT — 5000 unidades + 12 kg scrap
    r = client.post(
        f"/api/operations/{op_id}/report",
        headers=auth_header(admin_token),
        json={"quantity": 5000, "scrap_kg": 12.0, "scrap_reason": "quality_defect"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["quantity_out"] == 5000
    assert body["scrap_kg"] == 12.0
    assert body["scrap_reason"] == "quality_defect"

    # 3) COMPLETE — promueve op2 (TUB) a READY
    r = client.post(f"/api/operations/{op_id}/complete", headers=auth_header(admin_token))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "completed"

    # 4) Verificar promoción: la op2 (TUB) debe estar READY con quantity_in=5000
    r = client.get(
        f"/api/orders/{order_id}/operations", headers=auth_header(admin_token)
    )
    assert r.status_code == 200
    ops = r.json()
    assert len(ops) == 4
    assert ops[0]["status"] == "completed"
    assert ops[1]["status"] == "ready"
    assert ops[1]["quantity_in"] == 5000  # = quantity_out de op1


def test_report_rejects_zero_quantity(client, db_session, admin_token) -> None:
    op = db_session.scalar(
        select(OrderOperation)
        .where(OrderOperation.status == OperationStatus.READY)
        .limit(1)
    )
    assert op is not None
    client.post(f"/api/operations/{op.id}/start", headers=auth_header(admin_token))
    r = client.post(
        f"/api/operations/{op.id}/report",
        headers=auth_header(admin_token),
        json={"quantity": 0, "scrap_kg": 0},
    )
    assert r.status_code == 400


def test_report_rejects_scrap_in_empacadora(client, db_session, admin_token) -> None:
    """En EMP no se puede reportar scrap (empacadora no genera desperdicio)."""
    # Buscar una operación READY de una máquina empacadora (id 4 = EMP-01)
    op = db_session.scalar(
        select(OrderOperation)
        .where(OrderOperation.machine_id == 4)
        .where(OrderOperation.status == OperationStatus.READY)
        .limit(1)
    )
    if op is None:
        # Si no hay EMP ready en seed actual, lo simulamos arrancando la cadena
        # Skip si no hay condiciones
        import pytest
        pytest.skip("No hay EMP-01 READY en este seed")

    client.post(f"/api/operations/{op.id}/start", headers=auth_header(admin_token))
    r = client.post(
        f"/api/operations/{op.id}/report",
        headers=auth_header(admin_token),
        json={"quantity": 100, "scrap_kg": 5.0, "scrap_reason": "quality_defect"},
    )
    assert r.status_code == 400
    assert "empacadora" in r.json()["detail"].lower()


def test_operator_cannot_report_for_other_machine(
    client, db_session, operator_token
) -> None:
    """Operario de TUB-01 no puede reportar en operación de IMP-01."""
    # Buscar operación READY en IMP-01 (machine_id=1, no la del operario)
    op = db_session.scalar(
        select(OrderOperation)
        .where(OrderOperation.machine_id == 1)
        .where(OrderOperation.status == OperationStatus.READY)
        .limit(1)
    )
    assert op is not None
    r = client.post(f"/api/operations/{op.id}/start", headers=auth_header(operator_token))
    assert r.status_code == 403


def test_trace_lists_four_operations_per_order(client, db_session, admin_token) -> None:
    op = db_session.scalar(select(OrderOperation).limit(1))
    assert op is not None
    r = client.get(
        f"/api/orders/{op.order_id}/operations", headers=auth_header(admin_token)
    )
    assert r.status_code == 200
    ops = r.json()
    assert len(ops) == 4
    assert [o["sequence"] for o in ops] == [1, 2, 3, 4]
