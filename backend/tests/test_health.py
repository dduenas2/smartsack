"""
Pruebas básicas del endpoint de salud.

Garantiza que la app arranca correctamente y que /health responde 200.
"""


def test_root_endpoint(client) -> None:
    """La raíz responde con metadatos de la API."""
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "SmartSack"
    assert body["health"] == "/health"


def test_health_endpoint(client) -> None:
    """El healthcheck responde 'ok'."""
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "SmartSack"
