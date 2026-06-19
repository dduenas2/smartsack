"""
Tests del router /api/dashboard.

Verifican:
- Que todos los endpoints exigen autenticación (401 sin token).
- Que la forma de la respuesta cumple el contrato Pydantic.
- Que los rangos numéricos son coherentes (probabilidades en [0,1], etc.).
- Que los filtros (`days`, `machine_id`, `threshold`) se aplican.

Los tests asumen que el seed ya está cargado (oee_records, ml_predictions,
órdenes en varios estados). No mutan datos, así que el rollback del fixture
es por higiene, no por necesidad.
"""

from tests.conftest import SEED_MACHINE_CODES, auth_header


# -----------------------------------------------------------------------------
# Auth
# -----------------------------------------------------------------------------
def test_dashboard_requires_auth(client) -> None:
    for path in (
        "/api/dashboard/overview",
        "/api/dashboard/oee-trend",
        "/api/dashboard/production-by-shift",
        "/api/dashboard/order-fulfillment",
        "/api/dashboard/machine-ranking",
        "/api/dashboard/alerts",
    ):
        assert client.get(path).status_code == 401, path


# -----------------------------------------------------------------------------
# /overview
# -----------------------------------------------------------------------------
def test_overview_shape(client, admin_token) -> None:
    r = client.get("/api/dashboard/overview", headers=auth_header(admin_token))
    assert r.status_code == 200
    body = r.json()
    expected = {
        "plant_oee",
        "plant_oee_yesterday",
        "availability",
        "performance",
        "quality",
        "orders_completed_today",
        "orders_in_progress",
        "orders_pending",
        "orders_delayed",
        "production_today",
        "production_target_today",
        "active_machines",
        "total_machines",
        "reference_date",
    }
    assert expected.issubset(body.keys())
    # OEE en rango [0,1] cuando hay datos.
    assert 0.0 <= body["plant_oee"] <= 1.0
    assert 0.0 <= body["availability"] <= 1.0
    assert 0.0 <= body["performance"] <= 1.0
    assert 0.0 <= body["quality"] <= 1.0
    # El seed crea 8 máquinas; la BD puede tener más si se añadieron
    # en runtime por la UI/API.
    assert body["total_machines"] >= len(SEED_MACHINE_CODES)
    assert 0 <= body["active_machines"] <= body["total_machines"]


# -----------------------------------------------------------------------------
# /oee-trend
# -----------------------------------------------------------------------------
def test_oee_trend_default(client, admin_token) -> None:
    r = client.get("/api/dashboard/oee-trend", headers=auth_header(admin_token))
    assert r.status_code == 200
    body = r.json()
    assert body["days"] == 30
    assert body["machine_id"] is None
    assert isinstance(body["points"], list)
    if body["points"]:
        p = body["points"][0]
        assert {"date", "availability", "performance", "quality", "oee", "sample_count"} <= p.keys()
        assert 0.0 <= p["oee"] <= 1.0


def test_oee_trend_filtered_by_machine(client, admin_token) -> None:
    r = client.get(
        "/api/dashboard/oee-trend?days=7&machine_id=1",
        headers=auth_header(admin_token),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["days"] == 7
    assert body["machine_id"] == 1
    # Cada punto agregado por máquina debería tener pocos samples (≤ 3 turnos).
    for p in body["points"]:
        assert 1 <= p["sample_count"] <= 3


def test_oee_trend_validates_days_range(client, admin_token) -> None:
    r = client.get(
        "/api/dashboard/oee-trend?days=0", headers=auth_header(admin_token)
    )
    assert r.status_code == 422
    r = client.get(
        "/api/dashboard/oee-trend?days=999", headers=auth_header(admin_token)
    )
    assert r.status_code == 422


# -----------------------------------------------------------------------------
# /production-by-shift
# -----------------------------------------------------------------------------
def test_production_by_shift_shape(client, admin_token) -> None:
    r = client.get(
        "/api/dashboard/production-by-shift?days=7",
        headers=auth_header(admin_token),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["days"] == 7
    for p in body["points"]:
        assert {"date", "turno_1", "turno_2", "turno_3", "total"} <= p.keys()
        assert p["total"] == p["turno_1"] + p["turno_2"] + p["turno_3"]
        assert all(p[k] >= 0 for k in ("turno_1", "turno_2", "turno_3", "total"))


# -----------------------------------------------------------------------------
# /order-fulfillment
# -----------------------------------------------------------------------------
def test_order_fulfillment_totals_match_points(client, admin_token) -> None:
    r = client.get(
        "/api/dashboard/order-fulfillment?days=14",
        headers=auth_header(admin_token),
    )
    assert r.status_code == 200
    body = r.json()
    keys = ("completed", "in_progress", "pending", "delayed")
    sums = {k: sum(p[k] for p in body["points"]) for k in keys}
    assert sums["completed"] == body["total_completed"]
    assert sums["in_progress"] == body["total_in_progress"]
    assert sums["pending"] == body["total_pending"]
    assert sums["delayed"] == body["total_delayed"]


# -----------------------------------------------------------------------------
# /machine-ranking
# -----------------------------------------------------------------------------
def test_machine_ranking_returns_all_machines_sorted(client, admin_token) -> None:
    r = client.get(
        "/api/dashboard/machine-ranking?days=30",
        headers=auth_header(admin_token),
    )
    assert r.status_code == 200
    body = r.json()
    items = body["items"]
    # Al menos las máquinas del seed; pueden venir más si se añadieron
    # en runtime.
    assert len(items) >= len(SEED_MACHINE_CODES)
    assert SEED_MACHINE_CODES.issubset({it["code"] for it in items})
    # Orden DESC por avg_oee (None al final).
    oees = [it["avg_oee"] for it in items if it["avg_oee"] is not None]
    assert oees == sorted(oees, reverse=True)
    for it in items:
        assert {"machine_id", "code", "name", "type", "avg_oee", "sample_count"} <= it.keys()


# -----------------------------------------------------------------------------
# /alerts
# -----------------------------------------------------------------------------
def test_alerts_threshold_filters(client, admin_token) -> None:
    r_low = client.get(
        "/api/dashboard/alerts?threshold=0.0&limit=50",
        headers=auth_header(admin_token),
    )
    r_high = client.get(
        "/api/dashboard/alerts?threshold=0.95&limit=50",
        headers=auth_header(admin_token),
    )
    assert r_low.status_code == 200 and r_high.status_code == 200
    items_low = r_low.json()["items"]
    items_high = r_high.json()["items"]
    # Subir el umbral nunca puede aumentar el conteo de alertas.
    assert len(items_high) <= len(items_low)
    for it in items_high:
        assert it["delay_probability"] >= 0.95


def test_alerts_returns_only_active_orders(client, admin_token) -> None:
    r = client.get(
        "/api/dashboard/alerts?threshold=0.0&limit=100",
        headers=auth_header(admin_token),
    )
    assert r.status_code == 200
    for it in r.json()["items"]:
        assert it["status"] in ("pending", "in_progress", "delayed")
        assert 0.0 <= it["delay_probability"] <= 1.0
        assert it["predicted_delay_hours"] >= 0.0
