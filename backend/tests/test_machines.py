"""
Tests del router /api/machines: listado, consulta y reglas por rol.
"""

from tests.conftest import SEED_MACHINE_CODES, auth_header


def test_list_machines_requires_auth(client) -> None:
    response = client.get("/api/machines")
    assert response.status_code == 401


def test_list_machines_includes_seed(client, admin_token) -> None:
    response = client.get("/api/machines", headers=auth_header(admin_token))
    assert response.status_code == 200
    machines = response.json()
    assert len(machines) >= len(SEED_MACHINE_CODES)
    codes = {m["code"] for m in machines}
    assert SEED_MACHINE_CODES.issubset(codes)


def test_list_machines_filtered_by_type(client, admin_token) -> None:
    response = client.get(
        "/api/machines?type=tubuladora", headers=auth_header(admin_token)
    )
    assert response.status_code == 200
    machines = response.json()
    assert len(machines) == 2
    assert all(m["type"] == "tubuladora" for m in machines)


def test_get_machine_by_id(client, admin_token) -> None:
    response = client.get("/api/machines/1", headers=auth_header(admin_token))
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == 1
    # El catálogo del seed empieza por IMP-01 (la primera máquina de la
    # ruta IMP→TUB→FON→EMP). Comprobamos que el código sigue ese formato
    # y no que sea uno concreto, así el test resiste reordenamientos.
    assert body["code"][3] == "-"
    assert body["code"][:3] in {"IMP", "TUB", "FON", "EMP"}


def test_get_machine_404(client, admin_token) -> None:
    response = client.get("/api/machines/9999", headers=auth_header(admin_token))
    assert response.status_code == 404


def test_operator_cannot_create_machine(client, operator_token) -> None:
    response = client.post(
        "/api/machines",
        headers=auth_header(operator_token),
        json={"code": "TST-01", "name": "Test", "type": "tubuladora"},
    )
    assert response.status_code == 403


def test_supervisor_cannot_create_machine(client, supervisor_token) -> None:
    response = client.post(
        "/api/machines",
        headers=auth_header(supervisor_token),
        json={"code": "TST-01", "name": "Test", "type": "tubuladora"},
    )
    assert response.status_code == 403


def test_admin_can_create_and_delete_machine(client, admin_token) -> None:
    payload = {
        "code": "TST-99",
        "name": "Máquina de prueba",
        "type": "empacadora",
        "location": "Lab",
    }
    create_resp = client.post(
        "/api/machines", headers=auth_header(admin_token), json=payload
    )
    assert create_resp.status_code == 201
    new_id = create_resp.json()["id"]

    delete_resp = client.delete(
        f"/api/machines/{new_id}", headers=auth_header(admin_token)
    )
    assert delete_resp.status_code == 204


def test_supervisor_can_update_machine_status(client, supervisor_token) -> None:
    response = client.patch(
        "/api/machines/1",
        headers=auth_header(supervisor_token),
        json={"status": "maintenance"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "maintenance"
