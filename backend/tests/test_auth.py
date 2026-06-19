"""
Tests del flujo de autenticación: /api/auth/login y /api/auth/me.
"""

from tests.conftest import auth_header


def test_login_success(client) -> None:
    response = client.post(
        "/api/auth/login",
        data={"username": "admin", "password": "smartsack123"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0
    assert isinstance(body["access_token"], str)
    assert len(body["access_token"]) > 20


def test_login_wrong_password(client) -> None:
    response = client.post(
        "/api/auth/login",
        data={"username": "admin", "password": "incorrecta"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Usuario o contraseña incorrectos"


def test_login_nonexistent_user(client) -> None:
    response = client.post(
        "/api/auth/login",
        data={"username": "no_existe", "password": "x"},
    )
    assert response.status_code == 401


def test_me_returns_current_user(client, admin_token) -> None:
    response = client.get("/api/auth/me", headers=auth_header(admin_token))
    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "admin"
    assert body["role"] == "admin"
    assert body["is_active"] is True


def test_me_requires_token(client) -> None:
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_me_rejects_invalid_token(client) -> None:
    response = client.get(
        "/api/auth/me", headers={"Authorization": "Bearer not-a-real-jwt"}
    )
    assert response.status_code == 401


def test_operator_token_carries_machine_id(client, operator_token) -> None:
    response = client.get("/api/auth/me", headers=auth_header(operator_token))
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "operario"
    assert body["machine_id"] is not None
