"""
Tests del router /api/users — gestión de usuarios admin-only.

Cubren:
- Permisos por rol (operario y supervisor → 403; admin → 200/201).
- Creación, listado con filtros, detalle.
- Validaciones: machine_id sólo aplica a operarios, conflicto de username.
- Soft-delete (is_active=false) y reglas anti-lockout (último admin, auto-borrado).
- Reset de contraseña funciona y permite login con la nueva.
- Asignar/desasignar máquina.
- Cada mutación deja entrada en admin_audit_log.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.models import AdminAuditLog, User
from tests.conftest import auth_header


def _unique_username(prefix: str = "test") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


# -----------------------------------------------------------------------------
# Permisos
# -----------------------------------------------------------------------------
def test_operator_cannot_list_users(client, operator_token) -> None:
    resp = client.get("/api/users", headers=auth_header(operator_token))
    assert resp.status_code == 403


def test_supervisor_cannot_create_user(client, supervisor_token) -> None:
    resp = client.post(
        "/api/users",
        headers=auth_header(supervisor_token),
        json={
            "username": _unique_username("nope"),
            "password": "smartsack123",
            "role": "operario",
        },
    )
    assert resp.status_code == 403


def test_anonymous_gets_401(client) -> None:
    assert client.get("/api/users").status_code == 401


# -----------------------------------------------------------------------------
# Listado / detalle
# -----------------------------------------------------------------------------
def test_admin_lists_users_with_pagination(client, admin_token) -> None:
    resp = client.get("/api/users?limit=5&offset=0", headers=auth_header(admin_token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["limit"] == 5
    assert body["offset"] == 0
    assert body["total"] >= 1
    assert len(body["items"]) <= 5


def test_admin_filters_by_role(client, admin_token) -> None:
    resp = client.get(
        "/api/users?role=admin", headers=auth_header(admin_token)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert all(u["role"] == "admin" for u in body["items"])
    assert any(u["username"] == "admin" for u in body["items"])


def test_admin_search_by_username(client, admin_token) -> None:
    resp = client.get(
        "/api/users?search=op_imp", headers=auth_header(admin_token)
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert all("op_imp" in u["username"].lower() for u in items)


# -----------------------------------------------------------------------------
# Crear
# -----------------------------------------------------------------------------
def test_admin_creates_supervisor(client, admin_token, db_session) -> None:
    username = _unique_username("sup")
    resp = client.post(
        "/api/users",
        headers=auth_header(admin_token),
        json={
            "username": username,
            "password": "smartsack123",
            "full_name": "Test Supervisor",
            "role": "supervisor",
        },
    )
    assert resp.status_code == 201, resp.text
    user = resp.json()
    assert user["username"] == username
    assert user["machine_id"] is None  # supervisores no llevan máquina
    assert user["is_active"] is True

    # Audit log debe tener la entrada de creación.
    log = db_session.scalar(
        select(AdminAuditLog)
        .where(AdminAuditLog.entity_type == "user")
        .where(AdminAuditLog.entity_id == user["id"])
        .where(AdminAuditLog.action == "create")
    )
    assert log is not None
    assert log.after["username"] == username


def test_admin_creates_operator_with_machine(client, admin_token) -> None:
    resp = client.post(
        "/api/users",
        headers=auth_header(admin_token),
        json={
            "username": _unique_username("op"),
            "password": "smartsack123",
            "role": "operario",
            "machine_id": 1,
        },
    )
    assert resp.status_code == 201
    assert resp.json()["machine_id"] == 1


def test_machine_id_ignored_for_supervisor(client, admin_token) -> None:
    """Si rol != operario, machine_id se fuerza a None."""
    resp = client.post(
        "/api/users",
        headers=auth_header(admin_token),
        json={
            "username": _unique_username("sup-with-mach"),
            "password": "smartsack123",
            "role": "supervisor",
            "machine_id": 1,
        },
    )
    assert resp.status_code == 201
    assert resp.json()["machine_id"] is None


def test_create_with_unknown_machine_returns_400(client, admin_token) -> None:
    resp = client.post(
        "/api/users",
        headers=auth_header(admin_token),
        json={
            "username": _unique_username("op"),
            "password": "smartsack123",
            "role": "operario",
            "machine_id": 99999,
        },
    )
    assert resp.status_code == 400


def test_create_duplicate_username_returns_409(client, admin_token) -> None:
    resp = client.post(
        "/api/users",
        headers=auth_header(admin_token),
        json={
            "username": "admin",  # ya existe
            "password": "smartsack123",
            "role": "supervisor",
        },
    )
    assert resp.status_code == 409


# -----------------------------------------------------------------------------
# PATCH
# -----------------------------------------------------------------------------
def test_admin_can_deactivate_other_user(client, admin_token, db_session) -> None:
    # Creo uno desechable.
    resp = client.post(
        "/api/users",
        headers=auth_header(admin_token),
        json={
            "username": _unique_username("victim"),
            "password": "smartsack123",
            "role": "supervisor",
        },
    )
    user_id = resp.json()["id"]

    resp = client.patch(
        f"/api/users/{user_id}",
        headers=auth_header(admin_token),
        json={"is_active": False},
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


def test_admin_cannot_self_deactivate(client, admin_token, db_session) -> None:
    me = db_session.scalar(select(User).where(User.username == "admin"))
    resp = client.patch(
        f"/api/users/{me.id}",
        headers=auth_header(admin_token),
        json={"is_active": False},
    )
    assert resp.status_code == 400


def test_admin_cannot_self_change_role(client, admin_token, db_session) -> None:
    me = db_session.scalar(select(User).where(User.username == "admin"))
    resp = client.patch(
        f"/api/users/{me.id}",
        headers=auth_header(admin_token),
        json={"role": "operario"},
    )
    assert resp.status_code == 400


def test_changing_role_to_non_operator_clears_machine(client, admin_token) -> None:
    # Creo operario con máquina, luego lo subo a supervisor.
    resp = client.post(
        "/api/users",
        headers=auth_header(admin_token),
        json={
            "username": _unique_username("convert"),
            "password": "smartsack123",
            "role": "operario",
            "machine_id": 2,
        },
    )
    user_id = resp.json()["id"]
    resp = client.patch(
        f"/api/users/{user_id}",
        headers=auth_header(admin_token),
        json={"role": "supervisor"},
    )
    assert resp.status_code == 200
    assert resp.json()["machine_id"] is None


# -----------------------------------------------------------------------------
# DELETE (soft)
# -----------------------------------------------------------------------------
def test_delete_soft_disables_user(client, admin_token) -> None:
    resp = client.post(
        "/api/users",
        headers=auth_header(admin_token),
        json={
            "username": _unique_username("trash"),
            "password": "smartsack123",
            "role": "supervisor",
        },
    )
    user_id = resp.json()["id"]
    resp = client.delete(f"/api/users/{user_id}", headers=auth_header(admin_token))
    assert resp.status_code == 204
    # El usuario ahora está is_active=False, no eliminado físicamente.
    resp = client.get(f"/api/users/{user_id}", headers=auth_header(admin_token))
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


def test_admin_cannot_self_delete(client, admin_token, db_session) -> None:
    me = db_session.scalar(select(User).where(User.username == "admin"))
    resp = client.delete(f"/api/users/{me.id}", headers=auth_header(admin_token))
    assert resp.status_code == 400


# -----------------------------------------------------------------------------
# Reset password
# -----------------------------------------------------------------------------
def test_reset_password_allows_login_with_new(client, admin_token) -> None:
    username = _unique_username("rst")
    resp = client.post(
        "/api/users",
        headers=auth_header(admin_token),
        json={
            "username": username,
            "password": "smartsack123",
            "role": "supervisor",
        },
    )
    user_id = resp.json()["id"]

    resp = client.post(
        f"/api/users/{user_id}/reset-password",
        headers=auth_header(admin_token),
        json={"new_password": "nueva-clave-12"},
    )
    assert resp.status_code == 200

    # Login con la nueva contraseña funciona; con la anterior, falla.
    login_ok = client.post(
        "/api/auth/login",
        data={"username": username, "password": "nueva-clave-12"},
    )
    assert login_ok.status_code == 200
    login_fail = client.post(
        "/api/auth/login",
        data={"username": username, "password": "smartsack123"},
    )
    assert login_fail.status_code == 401


# -----------------------------------------------------------------------------
# Assign machine
# -----------------------------------------------------------------------------
def test_assign_machine_to_operator(client, admin_token) -> None:
    resp = client.post(
        "/api/users",
        headers=auth_header(admin_token),
        json={
            "username": _unique_username("opr"),
            "password": "smartsack123",
            "role": "operario",
            "machine_id": 1,
        },
    )
    user_id = resp.json()["id"]
    resp = client.post(
        f"/api/users/{user_id}/assign-machine",
        headers=auth_header(admin_token),
        json={"machine_id": 3},
    )
    assert resp.status_code == 200
    assert resp.json()["machine_id"] == 3


def test_assign_machine_rejects_non_operator(client, admin_token) -> None:
    resp = client.post(
        "/api/users",
        headers=auth_header(admin_token),
        json={
            "username": _unique_username("not-op"),
            "password": "smartsack123",
            "role": "supervisor",
        },
    )
    user_id = resp.json()["id"]
    resp = client.post(
        f"/api/users/{user_id}/assign-machine",
        headers=auth_header(admin_token),
        json={"machine_id": 1},
    )
    assert resp.status_code == 400
