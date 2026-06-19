"""
Tests del módulo de chat.

Cubren:
- Tools individuales (get_production_stats, get_machine_status, etc.).
- chat_service en modo fallback: routing por keywords y formato de respuesta.
- Router /api/chat: auth, formato de payload, comportamiento.

Si la API key de Anthropic está configurada, los tests del fallback siguen
siendo válidos porque no dependen del LLM. Los tests del modo LLM se
saltan automáticamente.
"""

from __future__ import annotations

import pytest

from app.chat.tools import (
    get_alerts,
    get_machine_status,
    get_oee_data,
    get_order_info,
    get_production_stats,
    get_scrap_summary,
    get_wip_status,
    get_yield_summary,
)
from app.services import chat_service
from app.services.chat_service import (
    ChatMessage,
    _detect_days_back,
    _detect_machine_code,
    _detect_order_number,
    _route_keywords,
    chat,
    is_llm_available,
)
from tests.conftest import SEED_MACHINE_CODES, auth_header


# =============================================================================
# Tools (BD real, sesión transaccional del fixture)
# =============================================================================
def test_get_production_stats_today(db_session) -> None:
    r = get_production_stats(db_session, days_back=0)
    assert "completed_orders" in r
    assert r["produced_units"] >= 0


def test_get_machine_status_returns_all(db_session) -> None:
    r = get_machine_status(db_session, days_back_for_events=0)
    assert len(r["machines"]) >= len(SEED_MACHINE_CODES)
    assert SEED_MACHINE_CODES.issubset({m["code"] for m in r["machines"]})
    # Ordenado descendente por paradas.
    stops = [m["stops_count"] for m in r["machines"]]
    assert stops == sorted(stops, reverse=True)


def test_get_machine_status_filtered(db_session) -> None:
    r = get_machine_status(db_session, machine_code="TUB-01")
    assert len(r["machines"]) == 1
    assert r["machines"][0]["code"] == "TUB-01"


def test_get_oee_data_plant(db_session) -> None:
    r = get_oee_data(db_session, days_back=7)
    assert 0.0 <= r["oee"] <= 1.0
    assert len(r["by_machine"]) >= len(SEED_MACHINE_CODES)
    assert SEED_MACHINE_CODES.issubset({m["machine_code"] for m in r["by_machine"]})


def test_get_oee_data_for_unknown_machine_returns_error(db_session) -> None:
    r = get_oee_data(db_session, machine_code="ZZZ-99")
    assert "error" in r


def test_get_order_info_requires_identifier(db_session) -> None:
    r = get_order_info(db_session)
    assert "error" in r


def test_get_order_info_unknown_returns_error(db_session) -> None:
    r = get_order_info(db_session, order_number="OP-NO-EXISTE")
    assert "error" in r


def test_get_alerts_returns_active_only(db_session) -> None:
    r = get_alerts(db_session, threshold=0.0, limit=10)
    for a in r["alerts"]:
        assert a["status"] in ("pending", "in_progress", "delayed")
        assert 0.0 <= a["delay_probability"] <= 1.0


def test_get_scrap_summary_returns_pareto(db_session) -> None:
    r = get_scrap_summary(db_session, days_back=30)
    assert "total_scrap_kg" in r
    assert isinstance(r["by_machine"], list)
    # Si hay datos, debe estar ordenado descendente.
    if len(r["by_machine"]) > 1:
        kgs = [m["scrap_kg"] for m in r["by_machine"]]
        assert kgs == sorted(kgs, reverse=True)
    # Si hay razones, también ordenadas.
    if len(r["by_reason"]) > 1:
        rs = [x["scrap_kg"] for x in r["by_reason"]]
        assert rs == sorted(rs, reverse=True)


def test_get_scrap_summary_unknown_machine_returns_error(db_session) -> None:
    r = get_scrap_summary(db_session, days_back=7, machine_code="ZZZ-99")
    assert "error" in r


def test_get_yield_summary_returns_ratios(db_session) -> None:
    r = get_yield_summary(db_session, days_back=30)
    for item in r["items"]:
        if item["yield_ratio"] is not None:
            assert 0.0 <= item["yield_ratio"] <= 1.5


def test_get_wip_status_returns_all_machines(db_session) -> None:
    r = get_wip_status(db_session)
    assert len(r["machines"]) >= len(SEED_MACHINE_CODES)
    assert SEED_MACHINE_CODES.issubset({m["machine_code"] for m in r["machines"]})
    assert r["total_units_in_line"] >= 0
    assert r["total_in_progress_operations"] >= 0


# =============================================================================
# Helpers de detección (fallback)
# =============================================================================
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("¿Cuántos sacos hicieron ayer?", 1),
        ("¿OEE de la última semana?", 7),
        ("OEE en los últimos 14 días", 14),
        ("¿Producción de hoy?", 0),
        ("Estado actual", 0),
    ],
)
def test_detect_days_back(text, expected) -> None:
    assert _detect_days_back(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("¿OEE de TUB-01?", "TUB-01"),
        ("¿estado de imp02?", "IMP-02"),
        ("¿qué tal va FON-2?", "FON-02"),
        ("planta general", None),
    ],
)
def test_detect_machine_code(text, expected) -> None:
    assert _detect_machine_code(text) == expected


def test_detect_order_number_normalizes() -> None:
    assert _detect_order_number("Dame info de OP-2026-001372") == "OP-2026-001372"
    assert _detect_order_number("orden OP2026001372") == "OP-2026-001372"
    assert _detect_order_number("nada por aquí") is None


@pytest.mark.parametrize(
    ("text", "tool"),
    [
        ("alertas de retraso", "get_alerts"),
        ("oee de la planta", "get_oee_data"),
        ("máquina con más paradas", "get_machine_status"),
        ("info de orden OP-2026-001000", "get_order_info"),
        ("sacos producidos ayer", "get_production_stats"),
        ("¿cuántos sacos?", "get_production_stats"),
        ("cuál máquina genera más scrap", "get_scrap_summary"),
        ("desperdicio por razón esta semana", "get_scrap_summary"),
        ("yield por máquina la última semana", "get_yield_summary"),
        ("cuello de botella en calidad", "get_yield_summary"),
        ("cuántos sacos están en cola ahora", "get_wip_status"),
        ("WIP actual", "get_wip_status"),
    ],
)
def test_route_keywords(text, tool) -> None:
    assert _route_keywords(text) == tool


# =============================================================================
# chat_service.chat() en modo fallback
# =============================================================================
def test_chat_fallback_oee(db_session) -> None:
    r = chat(db_session, message="¿Cuál es el OEE de la planta?")
    assert r.mode == "fallback"
    assert "OEE" in r.reply
    assert len(r.tool_calls) == 1
    assert r.tool_calls[0].name == "get_oee_data"


def test_chat_fallback_alerts(db_session) -> None:
    r = chat(db_session, message="¿Qué alertas de retraso hay?")
    assert r.mode == "fallback"
    assert r.tool_calls[0].name == "get_alerts"


def test_chat_fallback_machine_stops(db_session) -> None:
    r = chat(db_session, message="¿Qué máquina tiene más paradas hoy?")
    assert r.tool_calls[0].name == "get_machine_status"
    assert "**" in r.reply  # marca la máquina top con bold


def test_chat_fallback_production_yesterday(db_session) -> None:
    r = chat(db_session, message="¿Cuántos sacos se produjeron ayer?")
    assert r.tool_calls[0].name == "get_production_stats"
    assert r.tool_calls[0].arguments.get("days_back") == 1


def test_chat_fallback_scrap(db_session) -> None:
    r = chat(db_session, message="¿Cuál máquina genera más scrap esta semana?")
    assert r.tool_calls[0].name == "get_scrap_summary"
    assert r.tool_calls[0].arguments.get("days_back") == 7


def test_chat_fallback_yield(db_session) -> None:
    r = chat(db_session, message="dame el yield por máquina")
    assert r.tool_calls[0].name == "get_yield_summary"


def test_chat_fallback_wip(db_session) -> None:
    r = chat(db_session, message="¿Cuántos sacos están en cola ahora mismo?")
    assert r.tool_calls[0].name == "get_wip_status"


def test_chat_empty_message_returns_friendly(db_session) -> None:
    r = chat(db_session, message="   ")
    assert "pregunta" in r.reply.lower() or "consulta" in r.reply.lower()


def test_chat_history_does_not_break(db_session) -> None:
    history = [
        ChatMessage(role="user", content="hola"),
        ChatMessage(role="assistant", content="¡Hola! ¿En qué te ayudo?"),
    ]
    r = chat(db_session, message="¿OEE de TUB-01?", history=history)
    assert r.tool_calls[0].arguments.get("machine_code") == "TUB-01"


# =============================================================================
# Router /api/chat
# =============================================================================
def test_chat_message_requires_auth(client) -> None:
    r = client.post("/api/chat/message", json={"message": "hola", "history": []})
    assert r.status_code == 401


def test_chat_status(client, admin_token) -> None:
    r = client.get("/api/chat/status", headers=auth_header(admin_token))
    assert r.status_code == 200
    body = r.json()
    assert "llm_available" in body
    assert "fallback_keywords" in body


def test_chat_message_returns_response(client, supervisor_token) -> None:
    r = client.post(
        "/api/chat/message",
        headers=auth_header(supervisor_token),
        json={"message": "¿OEE de la planta hoy?", "history": []},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] in ("llm", "fallback")
    assert len(body["reply"]) > 5
    assert len(body["tool_calls"]) >= 1


def test_chat_message_validates_max_length(client, admin_token) -> None:
    r = client.post(
        "/api/chat/message",
        headers=auth_header(admin_token),
        json={"message": "x" * 3000, "history": []},
    )
    assert r.status_code == 422


def test_chat_message_validates_role(client, admin_token) -> None:
    r = client.post(
        "/api/chat/message",
        headers=auth_header(admin_token),
        json={
            "message": "ok",
            "history": [{"role": "system", "content": "x"}],  # role inválido
        },
    )
    assert r.status_code == 422


@pytest.mark.skipif(not is_llm_available(), reason="ANTHROPIC_API_KEY no configurada")
def test_chat_message_llm_mode(client, admin_token) -> None:
    """Cuando hay API key real, se usa el LLM."""
    r = client.post(
        "/api/chat/message",
        headers=auth_header(admin_token),
        json={"message": "¿OEE planta?", "history": []},
    )
    assert r.status_code == 200
    assert r.json()["mode"] == "llm"
