"""
Tests del router /api/admin.

Cubren:
- Permisos: solo admin tiene acceso a /audit, /system/health, /system/settings,
  /system/ml-status. Supervisor/operario reciben 403.
- /audit: filtros (entity_type, action, days_back) + paginación.
- /system/settings: lectura inicializa el catálogo, PATCH aplica cambios y
  registra entrada de auditoría, claves fuera del catálogo dan 404.
- /system/health: snapshot agregado con checks por componente.
- /system/ml-status: refleja la presencia/ausencia del modelo.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.models import AdminAuditLog, SystemSetting
from tests.conftest import auth_header


def _unique_username(prefix: str = "admt") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


# =============================================================================
# Permisos
# =============================================================================
def test_supervisor_cannot_read_audit(client, supervisor_token) -> None:
    assert (
        client.get("/api/admin/audit", headers=auth_header(supervisor_token)).status_code
        == 403
    )


def test_operator_cannot_read_settings(client, operator_token) -> None:
    assert (
        client.get(
            "/api/admin/system/settings", headers=auth_header(operator_token)
        ).status_code
        == 403
    )


def test_anonymous_cannot_reach_health(client) -> None:
    assert client.get("/api/admin/system/health").status_code == 401


# =============================================================================
# Audit
# =============================================================================
def test_audit_lists_recent_actions(client, admin_token) -> None:
    # Genera una acción auditable y la verifica en el listado.
    username = _unique_username("audit")
    create = client.post(
        "/api/users",
        headers=auth_header(admin_token),
        json={
            "username": username,
            "password": "smartsack123",
            "role": "supervisor",
        },
    )
    assert create.status_code == 201
    user_id = create.json()["id"]

    resp = client.get(
        "/api/admin/audit?entity_type=user&action=create&limit=10",
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    matching = [e for e in body["items"] if e["entity_id"] == user_id]
    assert matching, "El log debe contener la acción de creación recién hecha"
    entry = matching[0]
    assert entry["actor_username"] == "admin"
    assert entry["after"]["username"] == username
    # password_hash NO debe aparecer.
    assert "password_hash" not in (entry["after"] or {})


def test_audit_paginates(client, admin_token) -> None:
    resp = client.get(
        "/api/admin/audit?limit=2&offset=0", headers=auth_header(admin_token)
    )
    body = resp.json()
    assert resp.status_code == 200
    assert body["limit"] == 2
    assert len(body["items"]) <= 2
    assert "total" in body


def test_audit_filters_by_actor(client, admin_token, db_session) -> None:
    # Solo el admin de seed (id=1) tiene actor_id en el log creado en el test
    # anterior; pero filtramos con un actor_id imposible.
    resp = client.get(
        "/api/admin/audit?actor_id=999999", headers=auth_header(admin_token)
    )
    assert resp.status_code == 200
    assert resp.json()["items"] == []


# =============================================================================
# System settings
# =============================================================================
def test_settings_seeded_on_first_read(client, admin_token, db_session) -> None:
    # Limpio el catálogo si quedaron settings de tests previos en otra sesión.
    resp = client.get(
        "/api/admin/system/settings", headers=auth_header(admin_token)
    )
    assert resp.status_code == 200
    keys = {s["key"] for s in resp.json()}
    assert {"chatbot_enabled", "predictions_enabled", "maintenance_mode"} <= keys


def test_update_setting_writes_audit(client, admin_token, db_session) -> None:
    resp = client.patch(
        "/api/admin/system/settings/maintenance_mode",
        headers=auth_header(admin_token),
        json={"value": True},
    )
    assert resp.status_code == 200
    assert resp.json()["value"] is True

    log = db_session.scalar(
        select(AdminAuditLog)
        .where(AdminAuditLog.action == "update_setting")
        .order_by(AdminAuditLog.created_at.desc())
        .limit(1)
    )
    assert log is not None
    assert log.after["key"] == "maintenance_mode"
    assert log.after["value"] is True


def test_update_setting_coerces_value(client, admin_token) -> None:
    resp = client.patch(
        "/api/admin/system/settings/chatbot_enabled",
        headers=auth_header(admin_token),
        json={"value": "false"},
    )
    assert resp.status_code == 200
    assert resp.json()["value"] is False


def test_update_unknown_setting_returns_404(client, admin_token) -> None:
    resp = client.patch(
        "/api/admin/system/settings/nope_no_existe",
        headers=auth_header(admin_token),
        json={"value": True},
    )
    assert resp.status_code == 404


# =============================================================================
# System health
# =============================================================================
def test_system_health_returns_snapshot(client, admin_token) -> None:
    resp = client.get(
        "/api/admin/system/health", headers=auth_header(admin_token)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["overall"] in ("ok", "degraded", "down")
    names = {c["name"] for c in body["checks"]}
    assert {"postgres", "redis", "anthropic", "ml_model"} <= names
    pg = next(c for c in body["checks"] if c["name"] == "postgres")
    assert pg["status"] == "ok"
    assert pg["latency_ms"] is not None


# =============================================================================
# ML status
# =============================================================================
def test_ml_status_returns_loaded_or_unloaded(client, admin_token) -> None:
    resp = client.get(
        "/api/admin/system/ml-status", headers=auth_header(admin_token)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "model_loaded" in body
    assert isinstance(body["predictions_count_total"], int)
