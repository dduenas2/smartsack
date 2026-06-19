"""
Tests del router /api/events: listado, registro y guardas para operarios.
"""

from sqlalchemy import select

from app.models import User
from tests.conftest import auth_header


def test_list_events_requires_auth(client) -> None:
    assert client.get("/api/events").status_code == 401


def test_list_events_paginated(client, admin_token) -> None:
    response = client.get(
        "/api/events?limit=20", headers=auth_header(admin_token)
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] > 0
    assert len(body["items"]) <= 20


def test_list_events_filter_by_type(client, admin_token) -> None:
    response = client.get(
        "/api/events?event_type=incident&limit=10",
        headers=auth_header(admin_token),
    )
    assert response.status_code == 200
    body = response.json()
    assert all(e["event_type"] == "incident" for e in body["items"])


def test_operator_can_create_event_on_own_machine(
    client, operator_token, db_session
) -> None:
    # El operador del seed (op_tub-01_1) está asignado a TUB-01.
    op = db_session.scalar(select(User).where(User.username == "op_tub-01_1"))
    assert op is not None and op.machine_id is not None

    response = client.post(
        "/api/events",
        headers=auth_header(operator_token),
        json={
            "machine_id": op.machine_id,
            "event_type": "stop",
            "description": "Parada por cambio de bobina (test)",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["machine_id"] == op.machine_id
    assert body["user_id"] == op.id
    assert body["event_type"] == "stop"


def test_operator_cannot_create_event_on_other_machine(
    client, operator_token, db_session
) -> None:
    op = db_session.scalar(select(User).where(User.username == "op_tub-01_1"))
    other_machine_id = 999  # Casi seguro distinto al asignado al operario.
    if op.machine_id == other_machine_id:
        other_machine_id = 998

    # El backend valida primero la existencia de la máquina; usamos una
    # máquina real distinta a la del operario.
    other = 2 if op.machine_id != 2 else 3

    response = client.post(
        "/api/events",
        headers=auth_header(operator_token),
        json={
            "machine_id": other,
            "event_type": "stop",
            "description": "Intento de operar otra máquina",
        },
    )
    assert response.status_code == 403


def test_admin_can_create_event_on_any_machine(client, admin_token) -> None:
    response = client.post(
        "/api/events",
        headers=auth_header(admin_token),
        json={
            "machine_id": 5,
            "event_type": "maintenance",
            "description": "Mantenimiento programado",
        },
    )
    assert response.status_code == 201
    assert response.json()["machine_id"] == 5
