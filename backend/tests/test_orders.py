"""
Tests del router /api/orders: listado con filtros, consulta y permisos.
"""

from tests.conftest import auth_header


def test_list_orders_paginated(client, admin_token) -> None:
    response = client.get(
        "/api/orders?limit=10", headers=auth_header(admin_token)
    )
    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 10
    assert body["offset"] == 0
    # El seed actual genera ~900 órdenes (con sus 4 operaciones cada una).
    # Antes había una orden por máquina; ahora una por línea, así que el
    # número total es menor pero cada orden tiene ~4× más operaciones.
    assert body["total"] >= 500
    assert len(body["items"]) == 10


def test_list_orders_filter_by_status(client, admin_token) -> None:
    response = client.get(
        "/api/orders?status=delayed&limit=5", headers=auth_header(admin_token)
    )
    assert response.status_code == 200
    body = response.json()
    assert all(item["status"] == "delayed" for item in body["items"])


def test_list_orders_filter_by_machine(client, admin_token) -> None:
    response = client.get(
        "/api/orders?machine_id=1&limit=5", headers=auth_header(admin_token)
    )
    assert response.status_code == 200
    body = response.json()
    assert all(item["machine_id"] == 1 for item in body["items"])


def test_get_order_by_id(client, admin_token) -> None:
    list_resp = client.get(
        "/api/orders?limit=1", headers=auth_header(admin_token)
    )
    order_id = list_resp.json()["items"][0]["id"]

    response = client.get(
        f"/api/orders/{order_id}", headers=auth_header(admin_token)
    )
    assert response.status_code == 200
    assert response.json()["id"] == order_id


def test_operator_cannot_create_order(client, operator_token) -> None:
    response = client.post(
        "/api/orders",
        headers=auth_header(operator_token),
        json={
            "order_number": "OP-TEST-001",
            "product_type": "Saco cemento 50kg",
            "quantity_ordered": 1000,
            "machine_id": 1,
            "planned_start": "2026-06-01T08:00:00+00:00",
            "planned_end": "2026-06-01T16:00:00+00:00",
        },
    )
    assert response.status_code == 403


def test_supervisor_can_create_order(client, supervisor_token) -> None:
    response = client.post(
        "/api/orders",
        headers=auth_header(supervisor_token),
        json={
            "order_number": "OP-TEST-SUPER-001",
            "product_type": "Saco cemento 50kg",
            "product_description": "Test desde tests automatizados",
            "quantity_ordered": 5000,
            "machine_id": 1,
            "priority": "normal",
            "planned_start": "2026-06-15T06:00:00+00:00",
            "planned_end": "2026-06-15T14:00:00+00:00",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["quantity_produced"] == 0


def test_create_order_rejects_invalid_dates(client, supervisor_token) -> None:
    response = client.post(
        "/api/orders",
        headers=auth_header(supervisor_token),
        json={
            "order_number": "OP-TEST-BAD-DATES",
            "product_type": "Saco cemento 50kg",
            "quantity_ordered": 1000,
            "machine_id": 1,
            "planned_start": "2026-06-15T16:00:00+00:00",
            "planned_end": "2026-06-15T08:00:00+00:00",
        },
    )
    assert response.status_code == 422
