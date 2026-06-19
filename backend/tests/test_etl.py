"""
Tests del módulo ETL.

Cubren:
- Validación de columnas requeridas (CSV ilegible o incompleto → status FAILED).
- Carga válida de cada uno de los 4 tipos.
- Detección de duplicados intra-archivo (skipped).
- Idempotencia: segunda corrida actualiza, no re-inserta.
- Errores por fila no abortan el batch (status PARTIAL).
- Permisos por rol en /upload (operario → 403).
- /status devuelve historial paginado.
- /sample-csv/{kind} devuelve la plantilla esperada.

Todos los tests usan la sesión transaccional del conftest, así que las filas
creadas se revierten al final.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.models import (
    ETLLoad,
    ETLLoadKind,
    ETLLoadStatus,
    EventType,
    Machine,
    OperationStatus,
    OrderOperation,
    OrderStatus,
    ProductionEvent,
    ProductionOrder,
    ScrapReason,
)
from app.services import etl_service
from tests.conftest import auth_header


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _csv_bytes(rows: list[dict]) -> bytes:
    """Construye un CSV en memoria a partir de una lista de dicts."""
    if not rows:
        return b""
    headers = list(rows[0].keys())
    lines = [",".join(headers)]
    for r in rows:
        lines.append(",".join("" if r.get(h) is None else str(r[h]) for h in headers))
    return ("\n".join(lines) + "\n").encode("utf-8")


def _upload(client, token, kind: str, content: bytes, filename: str = "test.csv"):
    return client.post(
        "/api/etl/upload",
        headers=auth_header(token),
        data={"kind": kind},
        files={"file": (filename, content, "text/csv")},
    )


# -----------------------------------------------------------------------------
# Servicio (sin pasar por HTTP)
# -----------------------------------------------------------------------------
def test_service_rejects_csv_without_required_columns(db_session) -> None:
    bad = b"foo,bar\n1,2\n"
    load = etl_service.process_upload(
        db_session,
        content=bad,
        filename="bad.csv",
        kind=ETLLoadKind.PRODUCTION_ORDERS,
        uploaded_by_id=None,
    )
    assert load.status == ETLLoadStatus.FAILED
    assert load.error_log is not None
    assert any("Faltan columnas" in g for g in load.error_log["global"])


def test_service_rejects_empty_csv(db_session) -> None:
    load = etl_service.process_upload(
        db_session,
        content=b"order_number,product_type,quantity_ordered,machine_code,planned_start,planned_end\n",
        filename="empty.csv",
        kind=ETLLoadKind.PRODUCTION_ORDERS,
        uploaded_by_id=None,
    )
    assert load.status == ETLLoadStatus.FAILED


def test_service_loads_valid_orders(db_session) -> None:
    rows = [
        {
            "order_number": "OP-TEST-000001",
            "product_type": "Saco prueba 50kg",
            "product_description": "Test ETL",
            "quantity_ordered": 1000,
            "machine_code": "TUB-01",
            "planned_start": "2026-06-01T06:00:00",
            "planned_end": "2026-06-01T14:00:00",
            "priority": "normal",
        },
        {
            "order_number": "OP-TEST-000002",
            "product_type": "Saco prueba 25kg",
            "product_description": "Test ETL 2",
            "quantity_ordered": 2000,
            "machine_code": "IMP-01",
            "planned_start": "2026-06-01T08:00:00",
            "planned_end": "2026-06-01T18:00:00",
            "priority": "high",
        },
    ]
    load = etl_service.process_upload(
        db_session,
        content=_csv_bytes(rows),
        filename="ok.csv",
        kind=ETLLoadKind.PRODUCTION_ORDERS,
        uploaded_by_id=None,
    )
    assert load.status == ETLLoadStatus.SUCCESS
    assert load.rows_inserted == 2
    assert load.rows_failed == 0

    persisted = db_session.scalar(
        select(ProductionOrder).where(ProductionOrder.order_number == "OP-TEST-000001")
    )
    assert persisted is not None
    assert persisted.quantity_ordered == 1000


def test_service_idempotent_second_run_updates(db_session) -> None:
    rows = [
        {
            "order_number": "OP-TEST-IDEMP",
            "product_type": "Saco idemp",
            "product_description": "v1",
            "quantity_ordered": 1000,
            "machine_code": "TUB-01",
            "planned_start": "2026-06-01T06:00:00",
            "planned_end": "2026-06-01T14:00:00",
            "priority": "normal",
        }
    ]
    first = etl_service.process_upload(
        db_session,
        content=_csv_bytes(rows),
        filename="v1.csv",
        kind=ETLLoadKind.PRODUCTION_ORDERS,
        uploaded_by_id=None,
    )
    assert first.rows_inserted == 1

    rows[0]["product_description"] = "v2"
    rows[0]["quantity_ordered"] = 1500
    second = etl_service.process_upload(
        db_session,
        content=_csv_bytes(rows),
        filename="v2.csv",
        kind=ETLLoadKind.PRODUCTION_ORDERS,
        uploaded_by_id=None,
    )
    assert second.rows_inserted == 0
    assert second.rows_updated == 1

    persisted = db_session.scalar(
        select(ProductionOrder).where(ProductionOrder.order_number == "OP-TEST-IDEMP")
    )
    assert persisted is not None
    assert persisted.quantity_ordered == 1500
    assert persisted.product_description == "v2"


def test_service_intra_file_duplicates_skipped(db_session) -> None:
    rows = [
        {
            "order_number": "OP-TEST-DUP",
            "product_type": "X",
            "product_description": "",
            "quantity_ordered": 1000,
            "machine_code": "TUB-01",
            "planned_start": "2026-06-01T06:00:00",
            "planned_end": "2026-06-01T14:00:00",
            "priority": "normal",
        },
        # Duplicado dentro del mismo archivo
        {
            "order_number": "OP-TEST-DUP",
            "product_type": "X",
            "product_description": "",
            "quantity_ordered": 999,
            "machine_code": "TUB-01",
            "planned_start": "2026-06-01T06:00:00",
            "planned_end": "2026-06-01T14:00:00",
            "priority": "normal",
        },
    ]
    load = etl_service.process_upload(
        db_session,
        content=_csv_bytes(rows),
        filename="dup.csv",
        kind=ETLLoadKind.PRODUCTION_ORDERS,
        uploaded_by_id=None,
    )
    assert load.rows_inserted == 1
    assert load.rows_skipped == 1


def test_service_partial_status_when_some_rows_fail(db_session) -> None:
    rows = [
        {
            "order_number": "OP-TEST-OK",
            "product_type": "X",
            "product_description": "",
            "quantity_ordered": 1000,
            "machine_code": "TUB-01",
            "planned_start": "2026-06-01T06:00:00",
            "planned_end": "2026-06-01T14:00:00",
            "priority": "normal",
        },
        {
            "order_number": "OP-TEST-BAD",
            "product_type": "X",
            "product_description": "",
            "quantity_ordered": "no-es-numero",
            "machine_code": "TUB-01",
            "planned_start": "2026-06-01T06:00:00",
            "planned_end": "2026-06-01T14:00:00",
            "priority": "normal",
        },
    ]
    load = etl_service.process_upload(
        db_session,
        content=_csv_bytes(rows),
        filename="partial.csv",
        kind=ETLLoadKind.PRODUCTION_ORDERS,
        uploaded_by_id=None,
    )
    assert load.status == ETLLoadStatus.PARTIAL
    assert load.rows_inserted == 1
    assert load.rows_failed == 1
    assert load.error_log["rows"][0]["order_number"] == "OP-TEST-BAD"


def test_service_unknown_machine_code_is_row_error(db_session) -> None:
    rows = [
        {
            "order_number": "OP-TEST-NOMACH",
            "product_type": "X",
            "product_description": "",
            "quantity_ordered": 1000,
            "machine_code": "ZZZ-99",
            "planned_start": "2026-06-01T06:00:00",
            "planned_end": "2026-06-01T14:00:00",
            "priority": "normal",
        }
    ]
    load = etl_service.process_upload(
        db_session,
        content=_csv_bytes(rows),
        filename="nomach.csv",
        kind=ETLLoadKind.PRODUCTION_ORDERS,
        uploaded_by_id=None,
    )
    assert load.rows_failed == 1
    assert "ZZZ-99" in load.error_log["rows"][0]["error"]


def test_service_confirmations_updates_existing_order(db_session) -> None:
    # Inserto la orden primero — esto auto-crea las 4 operaciones de la línea A.
    etl_service.process_upload(
        db_session,
        content=_csv_bytes([
            {
                "order_number": "OP-TEST-CONF",
                "product_type": "X",
                "product_description": "",
                "quantity_ordered": 1000,
                "machine_code": "IMP-01",
                "planned_start": "2026-06-01T06:00:00",
                "planned_end": "2026-06-01T14:00:00",
                "priority": "normal",
            }
        ]),
        filename="seed.csv",
        kind=ETLLoadKind.PRODUCTION_ORDERS,
        uploaded_by_id=None,
    )
    # Confirmaciones — una por máquina de la ruta IMP→TUB→FON→EMP.
    # Recorremos toda la cadena para verificar que la orden cierra al cerrar EMP.
    conf = etl_service.process_upload(
        db_session,
        content=_csv_bytes([
            {
                "order_number": "OP-TEST-CONF",
                "machine_code": "IMP-01",
                "quantity_produced": 990,
                "actual_start": "2026-06-01T06:30:00",
                "actual_end": "2026-06-01T08:00:00",
                "scrap_kg": 1.5,
                "scrap_reason": "quality_defect",
            },
            {
                "order_number": "OP-TEST-CONF",
                "machine_code": "TUB-01",
                "quantity_produced": 985,
                "actual_start": "2026-06-01T08:00:00",
                "actual_end": "2026-06-01T10:00:00",
                "scrap_kg": 1.0,
                "scrap_reason": "setup_loss",
            },
            {
                "order_number": "OP-TEST-CONF",
                "machine_code": "FON-01",
                "quantity_produced": 982,
                "actual_start": "2026-06-01T10:00:00",
                "actual_end": "2026-06-01T12:00:00",
                "scrap_kg": 0.8,
                "scrap_reason": "material_break",
            },
            {
                "order_number": "OP-TEST-CONF",
                "machine_code": "EMP-01",
                "quantity_produced": 980,
                "actual_start": "2026-06-01T12:00:00",
                "actual_end": "2026-06-01T13:00:00",
                "scrap_kg": 0,
                "scrap_reason": "",
            },
        ]),
        filename="conf.csv",
        kind=ETLLoadKind.CONFIRMATIONS,
        uploaded_by_id=None,
    )
    assert conf.status == ETLLoadStatus.SUCCESS
    assert conf.rows_updated == 4

    persisted = db_session.scalar(
        select(ProductionOrder).where(ProductionOrder.order_number == "OP-TEST-CONF")
    )
    assert persisted.quantity_produced == 980
    assert persisted.status == OrderStatus.COMPLETED
    assert persisted.scrap_total_kg == pytest.approx(3.3, rel=0.01)


def test_service_confirmation_unknown_order_is_row_error(db_session) -> None:
    load = etl_service.process_upload(
        db_session,
        content=_csv_bytes([
            {
                "order_number": "OP-NO-EXISTE",
                "machine_code": "IMP-01",
                "quantity_produced": 100,
                "actual_start": "2026-06-01T06:00:00",
                "actual_end": "",
            }
        ]),
        filename="conf_bad.csv",
        kind=ETLLoadKind.CONFIRMATIONS,
        uploaded_by_id=None,
    )
    assert load.status == ETLLoadStatus.PARTIAL
    assert load.rows_failed == 1


# -----------------------------------------------------------------------------
# Helpers para los tests de eventos production_update
# -----------------------------------------------------------------------------
def _seed_line_a_order(db_session, order_number: str) -> None:
    """Inserta una orden en la línea A (IMP-01) → auto-crea sus 4 operaciones."""
    etl_service.process_upload(
        db_session,
        content=_csv_bytes([
            {
                "order_number": order_number,
                "product_type": "X",
                "product_description": "",
                "quantity_ordered": 1000,
                "machine_code": "IMP-01",
                "planned_start": "2026-06-01T06:00:00",
                "planned_end": "2026-06-01T14:00:00",
                "priority": "normal",
            }
        ]),
        filename="seed.csv",
        kind=ETLLoadKind.PRODUCTION_ORDERS,
        uploaded_by_id=None,
    )


def _operation_for(db_session, order_number: str, machine_code: str) -> OrderOperation:
    order = db_session.scalar(
        select(ProductionOrder).where(ProductionOrder.order_number == order_number)
    )
    machine = db_session.scalar(select(Machine).where(Machine.code == machine_code))
    return db_session.scalar(
        select(OrderOperation)
        .where(OrderOperation.order_id == order.id)
        .where(OrderOperation.machine_id == machine.id)
    )


def _events_for_operation(db_session, operation_id: int) -> list[ProductionEvent]:
    return list(
        db_session.scalars(
            select(ProductionEvent)
            .where(ProductionEvent.operation_id == operation_id)
            .where(ProductionEvent.event_type == EventType.PRODUCTION_UPDATE)
        )
    )


def test_service_confirmation_creates_production_update_event(db_session) -> None:
    """Una confirmación válida deja una traza production_update en la operación."""
    _seed_line_a_order(db_session, "OP-EVT-CREATE")
    load = etl_service.process_upload(
        db_session,
        content=_csv_bytes([
            {
                "order_number": "OP-EVT-CREATE",
                "machine_code": "IMP-01",
                "quantity_produced": 990,
                "actual_start": "2026-06-01T06:30:00",
                "actual_end": "",
                "scrap_kg": 2.0,
                "scrap_reason": "quality_defect",
            }
        ]),
        filename="conf.csv",
        kind=ETLLoadKind.CONFIRMATIONS,
        uploaded_by_id=None,
    )
    assert load.status == ETLLoadStatus.SUCCESS

    op = _operation_for(db_session, "OP-EVT-CREATE", "IMP-01")
    events = _events_for_operation(db_session, op.id)
    assert len(events) == 1
    ev = events[0]
    assert ev.operation_id == op.id
    assert ev.order_id == op.order_id
    assert ev.machine_id == op.machine_id
    assert ev.quantity == 990
    assert ev.scrap_kg == pytest.approx(2.0)
    assert ev.scrap_reason == ScrapReason.QUALITY_DEFECT
    assert ev.description.startswith("[ETL]")


def test_service_confirmation_event_is_idempotent(db_session) -> None:
    """Recargar el mismo CSV de confirmación actualiza el evento, no lo duplica."""
    _seed_line_a_order(db_session, "OP-EVT-IDEMP")
    conf = _csv_bytes([
        {
            "order_number": "OP-EVT-IDEMP",
            "machine_code": "IMP-01",
            "quantity_produced": 980,
            "actual_start": "2026-06-01T06:30:00",
            "actual_end": "",
            "scrap_kg": 1.0,
            "scrap_reason": "setup_loss",
        }
    ])
    etl_service.process_upload(
        db_session, content=conf, filename="c1.csv",
        kind=ETLLoadKind.CONFIRMATIONS, uploaded_by_id=None,
    )
    etl_service.process_upload(
        db_session, content=conf, filename="c2.csv",
        kind=ETLLoadKind.CONFIRMATIONS, uploaded_by_id=None,
    )
    op = _operation_for(db_session, "OP-EVT-IDEMP", "IMP-01")
    events = _events_for_operation(db_session, op.id)
    assert len(events) == 1
    assert events[0].quantity == 980


def test_service_confirmation_completes_and_promotes_next(db_session) -> None:
    """Confirmar con actual_end completa la operación y promueve la siguiente a READY."""
    _seed_line_a_order(db_session, "OP-EVT-PROMO")
    etl_service.process_upload(
        db_session,
        content=_csv_bytes([
            {
                "order_number": "OP-EVT-PROMO",
                "machine_code": "IMP-01",
                "quantity_produced": 950,
                "actual_start": "2026-06-01T06:30:00",
                "actual_end": "2026-06-01T08:00:00",
                "scrap_kg": 0,
                "scrap_reason": "",
            }
        ]),
        filename="conf.csv",
        kind=ETLLoadKind.CONFIRMATIONS,
        uploaded_by_id=None,
    )
    imp = _operation_for(db_session, "OP-EVT-PROMO", "IMP-01")
    tub = _operation_for(db_session, "OP-EVT-PROMO", "TUB-01")
    assert imp.status == OperationStatus.COMPLETED
    assert tub.status == OperationStatus.READY
    assert tub.quantity_in == 950


# -----------------------------------------------------------------------------
# Endpoints HTTP
# -----------------------------------------------------------------------------
def test_upload_requires_supervisor_or_admin(client, operator_token) -> None:
    response = client.post(
        "/api/etl/upload",
        headers=auth_header(operator_token),
        data={"kind": "production_orders"},
        files={"file": ("x.csv", b"foo,bar\n1,2", "text/csv")},
    )
    assert response.status_code == 403


def test_upload_rejects_non_csv_extension(client, supervisor_token) -> None:
    response = _upload(
        client, supervisor_token, "production_orders", b"hola", filename="bad.txt"
    )
    assert response.status_code == 400


def test_upload_rejects_empty_file(client, supervisor_token) -> None:
    response = _upload(client, supervisor_token, "production_orders", b"", filename="empty.csv")
    assert response.status_code == 400


def test_upload_returns_summary(client, supervisor_token) -> None:
    rows = [
        {
            "order_number": "OP-HTTP-001",
            "product_type": "X",
            "product_description": "",
            "quantity_ordered": 500,
            "machine_code": "TUB-01",
            "planned_start": "2026-07-01T06:00:00",
            "planned_end": "2026-07-01T14:00:00",
            "priority": "normal",
        }
    ]
    response = _upload(
        client, supervisor_token, "production_orders", _csv_bytes(rows), filename="http.csv"
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "success"
    assert body["rows_inserted"] == 1
    assert body["uploaded_by_id"] is not None
    assert body["filename"] == "http.csv"


def test_status_lists_recent_loads(client, supervisor_token) -> None:
    # Subo dos cargas
    rows = [
        {
            "order_number": "OP-LIST-001",
            "product_type": "X",
            "product_description": "",
            "quantity_ordered": 500,
            "machine_code": "TUB-01",
            "planned_start": "2026-07-01T06:00:00",
            "planned_end": "2026-07-01T14:00:00",
            "priority": "normal",
        }
    ]
    _upload(client, supervisor_token, "production_orders", _csv_bytes(rows), filename="L1.csv")
    rows[0]["order_number"] = "OP-LIST-002"
    _upload(client, supervisor_token, "production_orders", _csv_bytes(rows), filename="L2.csv")

    response = client.get(
        "/api/etl/status?limit=5", headers=auth_header(supervisor_token)
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 2
    filenames = [it["filename"] for it in body["items"][:5]]
    assert "L2.csv" in filenames or "L1.csv" in filenames


def test_status_filtered_by_kind(client, supervisor_token) -> None:
    response = client.get(
        "/api/etl/status?kind=materials&limit=5",
        headers=auth_header(supervisor_token),
    )
    assert response.status_code == 200
    body = response.json()
    for it in body["items"]:
        assert it["kind"] == "materials"


def test_get_load_by_id(client, supervisor_token) -> None:
    rows = [
        {
            "order_number": "OP-GET-001",
            "product_type": "X",
            "product_description": "",
            "quantity_ordered": 500,
            "machine_code": "TUB-01",
            "planned_start": "2026-07-01T06:00:00",
            "planned_end": "2026-07-01T14:00:00",
            "priority": "normal",
        }
    ]
    upload = _upload(
        client, supervisor_token, "production_orders", _csv_bytes(rows), filename="g.csv"
    )
    load_id = upload.json()["id"]
    detail = client.get(
        f"/api/etl/status/{load_id}", headers=auth_header(supervisor_token)
    )
    assert detail.status_code == 200
    assert detail.json()["id"] == load_id


def test_sample_csv_template(client, supervisor_token) -> None:
    response = client.get(
        "/api/etl/sample-csv/production_orders",
        headers=auth_header(supervisor_token),
    )
    assert response.status_code == 200
    text = response.text
    assert "order_number" in text
    assert "machine_code" in text
    assert response.headers["content-type"].startswith("text/csv")
