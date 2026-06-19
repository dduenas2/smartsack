"""
Tools del chatbot — funciones que el LLM (o el fallback) puede invocar.

Cada tool:
- Recibe una `Session` SQLAlchemy + parámetros tipados.
- Devuelve un dict serializable a JSON (esto es lo que se inyecta en el
  prompt del LLM para que redacte la respuesta natural).
- Está documentada con un schema (`TOOL_SCHEMAS`) que se pasa a la API
  de Claude / LangChain como `tools=[...]`.

El módulo es agnóstico al frontend de IA usado: tanto el cliente
LangChain como el fallback por keywords lo consumen igual.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, case, desc, func, or_, select
from sqlalchemy.orm import Session

from app.models import (
    EventType,
    Machine,
    MachineStatus,
    MachineType,
    MLPrediction,
    OEERecord,
    OperationStatus,
    OrderOperation,
    OrderStatus,
    ProductionEvent,
    ProductionOrder,
    ScrapReason,
    Shift,
)


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _today_utc() -> date:
    return datetime.now(tz=timezone.utc).date()


def _date_window(days_back: int = 0, anchor: Optional[date] = None) -> tuple[datetime, datetime]:
    """
    Devuelve (start, end) tz-aware UTC para un rango "[anchor - days_back, anchor + 1d)".
    days_back=0 → solo el anchor (24h). days_back=1 → ayer + hoy. etc.
    """
    anchor = anchor or _today_utc()
    end_dt = datetime.combine(anchor + timedelta(days=1), time.min, tzinfo=timezone.utc)
    start_dt = datetime.combine(anchor - timedelta(days=days_back), time.min, tzinfo=timezone.utc)
    return start_dt, end_dt


def _parse_iso_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


# -----------------------------------------------------------------------------
# Tool 1 — Producción
# -----------------------------------------------------------------------------
def get_production_stats(
    db: Session,
    *,
    days_back: int = 0,
    machine_code: Optional[str] = None,
    product_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Estadísticas de producción para una ventana temporal.

    Args:
        days_back: 0 = sólo hoy; 1 = ayer + hoy; 7 = última semana; etc.
        machine_code: filtra por máquina (ej. "TUB-01"). None = todas.
        product_type: filtra por producto. None = todos.

    Returns:
        {
            "window": "...",
            "completed_orders": int,
            "in_progress_orders": int,
            "delayed_orders": int,
            "produced_units": int,
            "ordered_units": int,
            "fulfillment_rate": float (0-1),
            "filter": {...}
        }
    """
    start_dt, end_dt = _date_window(days_back)

    base = select(ProductionOrder).where(
        or_(
            and_(
                ProductionOrder.actual_end >= start_dt,
                ProductionOrder.actual_end < end_dt,
            ),
            and_(
                ProductionOrder.actual_start >= start_dt,
                ProductionOrder.actual_start < end_dt,
                ProductionOrder.status.in_([OrderStatus.IN_PROGRESS, OrderStatus.DELAYED]),
            ),
        )
    )
    if machine_code:
        machine = db.scalar(select(Machine).where(Machine.code == machine_code))
        if machine is None:
            return {"error": f"machine_code='{machine_code}' no existe"}
        base = base.where(ProductionOrder.machine_id == machine.id)
    if product_type:
        base = base.where(ProductionOrder.product_type == product_type)

    orders = list(db.scalars(base).all())

    by_status = {"completed": 0, "in_progress": 0, "delayed": 0, "pending": 0}
    produced = 0
    ordered = 0
    for o in orders:
        by_status[o.status.value] = by_status.get(o.status.value, 0) + 1
        produced += o.quantity_produced or 0
        ordered += o.quantity_ordered or 0

    fulfillment = produced / ordered if ordered > 0 else 0.0

    return {
        "window": f"últimos {days_back + 1} día(s)" if days_back > 0 else "hoy",
        "completed_orders": by_status["completed"],
        "in_progress_orders": by_status["in_progress"],
        "delayed_orders": by_status["delayed"],
        "produced_units": int(produced),
        "ordered_units": int(ordered),
        "fulfillment_rate": round(fulfillment, 4),
        "filter": {"machine_code": machine_code, "product_type": product_type},
    }


# -----------------------------------------------------------------------------
# Tool 2 — Estado de máquinas
# -----------------------------------------------------------------------------
def get_machine_status(
    db: Session,
    *,
    machine_code: Optional[str] = None,
    days_back_for_events: int = 0,
) -> Dict[str, Any]:
    """
    Estado actual + conteo de paradas/incidencias en la ventana.

    Args:
        machine_code: si se especifica, devuelve sólo esa máquina.
        days_back_for_events: cuenta paradas/incidencias dentro de esta ventana.

    Returns:
        Lista de máquinas con status, current_order, stops_count, incidents_count, etc.
    """
    stmt = select(Machine).order_by(Machine.code)
    if machine_code:
        stmt = stmt.where(Machine.code == machine_code)
    machines = list(db.scalars(stmt).all())
    if not machines:
        return {"machines": [], "note": "No se encontraron máquinas"}

    start_dt, end_dt = _date_window(days_back_for_events)

    items: List[Dict[str, Any]] = []
    for m in machines:
        stops = db.scalar(
            select(func.count(ProductionEvent.id)).where(
                ProductionEvent.machine_id == m.id,
                ProductionEvent.event_type == EventType.STOP,
                ProductionEvent.timestamp >= start_dt,
                ProductionEvent.timestamp < end_dt,
            )
        ) or 0
        incidents = db.scalar(
            select(func.count(ProductionEvent.id)).where(
                ProductionEvent.machine_id == m.id,
                ProductionEvent.event_type == EventType.INCIDENT,
                ProductionEvent.timestamp >= start_dt,
                ProductionEvent.timestamp < end_dt,
            )
        ) or 0

        current_order = None
        if m.current_order_id:
            o = db.get(ProductionOrder, m.current_order_id)
            if o is not None:
                current_order = {
                    "order_number": o.order_number,
                    "product_type": o.product_type,
                    "progress": (
                        round(o.quantity_produced / o.quantity_ordered, 3)
                        if o.quantity_ordered
                        else 0.0
                    ),
                }

        items.append(
            {
                "code": m.code,
                "name": m.name,
                "type": m.type.value,
                "status": m.status.value,
                "stops_count": int(stops),
                "incidents_count": int(incidents),
                "current_order": current_order,
            }
        )

    items.sort(key=lambda x: x["stops_count"], reverse=True)
    return {
        "window": f"últimos {days_back_for_events + 1} día(s)",
        "machines": items,
    }


# -----------------------------------------------------------------------------
# Tool 3 — Información de orden
# -----------------------------------------------------------------------------
def get_order_info(
    db: Session, *, order_number: Optional[str] = None, order_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Detalle completo de una orden + última predicción ML si existe.

    Debe especificarse `order_number` *o* `order_id`.
    """
    if not order_number and not order_id:
        return {"error": "Debe especificar order_number u order_id"}

    if order_number:
        order = db.scalar(
            select(ProductionOrder).where(ProductionOrder.order_number == order_number)
        )
    else:
        order = db.get(ProductionOrder, order_id)

    if order is None:
        return {"error": "Orden no encontrada"}

    machine = db.get(Machine, order.machine_id) if order.machine_id else None

    # Última predicción
    pred = db.scalar(
        select(MLPrediction)
        .where(MLPrediction.order_id == order.id)
        .order_by(desc(MLPrediction.created_at))
    )

    return {
        "order_number": order.order_number,
        "product_type": order.product_type,
        "product_description": order.product_description,
        "machine_code": machine.code if machine else None,
        "machine_name": machine.name if machine else None,
        "status": order.status.value,
        "priority": order.priority.value,
        "quantity_ordered": int(order.quantity_ordered),
        "quantity_produced": int(order.quantity_produced),
        "progress": (
            round(order.quantity_produced / order.quantity_ordered, 3)
            if order.quantity_ordered
            else 0.0
        ),
        "planned_start": order.planned_start.isoformat() if order.planned_start else None,
        "planned_end": order.planned_end.isoformat() if order.planned_end else None,
        "actual_start": order.actual_start.isoformat() if order.actual_start else None,
        "actual_end": order.actual_end.isoformat() if order.actual_end else None,
        "delay_prediction": (
            {
                "probability": round(pred.delay_probability, 3),
                "predicted_delay_hours": round(pred.predicted_delay_hours, 2),
                "model_version": pred.model_version,
                "predicted_at": pred.created_at.isoformat(),
            }
            if pred is not None
            else None
        ),
    }


# -----------------------------------------------------------------------------
# Tool 4 — OEE
# -----------------------------------------------------------------------------
def get_oee_data(
    db: Session,
    *,
    machine_code: Optional[str] = None,
    days_back: int = 0,
) -> Dict[str, Any]:
    """
    OEE (Disponibilidad × Rendimiento × Calidad) agregado.

    Si machine_code es None devuelve OEE de planta y de cada máquina.
    Si days_back > 0, agrega sobre la ventana.
    """
    # Anclamos al último día con datos en oee_records: si "hoy" todavía no
    # tiene registros (típico al inicio de la jornada UTC), retrocedemos al
    # más reciente para que la respuesta sea útil en lugar de 0%.
    last_with_data = db.scalar(select(func.max(OEERecord.date)))
    end_date = last_with_data if last_with_data is not None else _today_utc()
    start_date = end_date - timedelta(days=days_back)

    base = select(OEERecord).where(
        OEERecord.date >= start_date, OEERecord.date <= end_date
    )

    machine = None
    if machine_code:
        machine = db.scalar(select(Machine).where(Machine.code == machine_code))
        if machine is None:
            return {"error": f"machine_code='{machine_code}' no existe"}
        base = base.where(OEERecord.machine_id == machine.id)

    avg = db.execute(
        select(
            func.avg(OEERecord.oee_value),
            func.avg(OEERecord.availability),
            func.avg(OEERecord.performance),
            func.avg(OEERecord.quality),
            func.count(OEERecord.id),
        ).where(*base.whereclause.clauses if base.whereclause is not None else [])
    ).one()

    overall = {
        "scope": machine.code if machine else "planta",
        "window": f"últimos {days_back + 1} día(s)",
        "oee": round(float(avg[0] or 0), 4),
        "availability": round(float(avg[1] or 0), 4),
        "performance": round(float(avg[2] or 0), 4),
        "quality": round(float(avg[3] or 0), 4),
        "sample_count": int(avg[4] or 0),
    }

    by_machine: List[Dict[str, Any]] = []
    if machine is None:
        rows = db.execute(
            select(
                Machine.code,
                func.avg(OEERecord.oee_value),
                func.avg(OEERecord.availability),
                func.avg(OEERecord.performance),
                func.avg(OEERecord.quality),
                func.count(OEERecord.id),
            )
            .select_from(Machine)
            .join(OEERecord, OEERecord.machine_id == Machine.id, isouter=True)
            .where(
                or_(
                    OEERecord.date.is_(None),
                    and_(OEERecord.date >= start_date, OEERecord.date <= end_date),
                )
            )
            .group_by(Machine.code)
            # NULLS LAST: en PostgreSQL `DESC` pone NULL primero por defecto;
            # las máquinas sin oee_records aparecerían encabezando el ranking
            # y romperían a los consumidores (`top['oee'] * 100`). Forzamos
            # que las máquinas con datos vayan primero.
            .order_by(func.avg(OEERecord.oee_value).desc().nullslast())
        ).all()
        by_machine = [
            {
                "machine_code": r[0],
                "oee": round(float(r[1]), 4) if r[1] is not None else None,
                "availability": round(float(r[2]), 4) if r[2] is not None else None,
                "performance": round(float(r[3]), 4) if r[3] is not None else None,
                "quality": round(float(r[4]), 4) if r[4] is not None else None,
                "samples": int(r[5] or 0),
            }
            for r in rows
        ]

    return {**overall, "by_machine": by_machine}


# -----------------------------------------------------------------------------
# Tool 5 — Alertas predictivas
# -----------------------------------------------------------------------------
def get_alerts(
    db: Session, *, threshold: float = 0.6, limit: int = 5
) -> Dict[str, Any]:
    """
    Órdenes activas con probabilidad de retraso ≥ threshold según el modelo ML.
    """
    # Subquery: última predicción por orden.
    rn = (
        func.row_number()
        .over(
            partition_by=MLPrediction.order_id,
            order_by=desc(MLPrediction.created_at),
        )
        .label("rn")
    )
    pred_sub = select(
        MLPrediction.order_id,
        MLPrediction.delay_probability,
        MLPrediction.predicted_delay_hours,
        MLPrediction.model_version,
        MLPrediction.created_at,
        rn,
    ).subquery("pred")

    rows = db.execute(
        select(
            ProductionOrder.order_number,
            ProductionOrder.product_type,
            ProductionOrder.status,
            ProductionOrder.planned_end,
            Machine.code.label("machine_code"),
            pred_sub.c.delay_probability,
            pred_sub.c.predicted_delay_hours,
            pred_sub.c.model_version,
        )
        .select_from(ProductionOrder)
        .join(pred_sub, pred_sub.c.order_id == ProductionOrder.id)
        .join(Machine, Machine.id == ProductionOrder.machine_id, isouter=True)
        .where(pred_sub.c.rn == 1)
        .where(pred_sub.c.delay_probability >= threshold)
        .where(
            ProductionOrder.status.in_(
                [OrderStatus.PENDING, OrderStatus.IN_PROGRESS, OrderStatus.DELAYED]
            )
        )
        .order_by(desc(pred_sub.c.delay_probability))
        .limit(limit)
    ).all()

    items = [
        {
            "order_number": r.order_number,
            "product_type": r.product_type,
            "machine_code": r.machine_code,
            "status": r.status.value,
            "planned_end": r.planned_end.isoformat() if r.planned_end else None,
            "delay_probability": round(float(r.delay_probability), 3),
            "predicted_delay_hours": round(float(r.predicted_delay_hours), 2),
            "model_version": r.model_version,
        }
        for r in rows
    ]
    return {"threshold": threshold, "count": len(items), "alerts": items}


# -----------------------------------------------------------------------------
# Tool 6 — Scrap (desperdicio) por máquina y razón
# -----------------------------------------------------------------------------
def get_scrap_summary(
    db: Session,
    *,
    days_back: int = 0,
    machine_code: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Suma kg de scrap de operaciones cerradas en la ventana, agrupadas por
    máquina y por razón (Pareto). Útil para "¿qué máquina genera más
    desperdicio?" o "¿cuál es la causa principal de merma esta semana?".
    """
    start_dt, end_dt = _date_window(days_back=days_back)

    base_q = (
        select(
            OrderOperation.machine_id,
            func.coalesce(func.sum(OrderOperation.scrap_kg), 0.0).label("scrap"),
            func.count().label("ops"),
        )
        .where(OrderOperation.actual_end.is_not(None))
        .where(OrderOperation.actual_end >= start_dt)
        .where(OrderOperation.actual_end < end_dt)
        .group_by(OrderOperation.machine_id)
    )

    machines = list(db.scalars(select(Machine).order_by(Machine.code)))
    by_id = {m.id: m for m in machines}

    if machine_code:
        target = next((m for m in machines if m.code == machine_code), None)
        if target is None:
            return {"error": f"Máquina '{machine_code}' no existe"}
        base_q = base_q.where(OrderOperation.machine_id == target.id)

    rows = db.execute(base_q).all()
    by_machine = []
    total_scrap = 0.0
    for row in rows:
        m = by_id.get(row.machine_id)
        if m is None:
            continue
        scrap = round(float(row.scrap or 0.0), 3)
        total_scrap += scrap
        by_machine.append(
            {
                "machine_code": m.code,
                "machine_type": m.type.value,
                "scrap_kg": scrap,
                "operations_completed": int(row.ops or 0),
            }
        )
    by_machine.sort(key=lambda x: x["scrap_kg"], reverse=True)

    # Pareto por razón
    reason_q = (
        select(
            OrderOperation.scrap_reason,
            func.coalesce(func.sum(OrderOperation.scrap_kg), 0.0).label("scrap"),
        )
        .where(OrderOperation.actual_end.is_not(None))
        .where(OrderOperation.actual_end >= start_dt)
        .where(OrderOperation.actual_end < end_dt)
        .where(OrderOperation.scrap_reason.is_not(None))
        .group_by(OrderOperation.scrap_reason)
    )
    if machine_code:
        reason_q = reason_q.where(
            OrderOperation.machine_id == by_id_for_code(by_id, machine_code)
        )
    by_reason = []
    for row in db.execute(reason_q).all():
        if row.scrap_reason is None:
            continue
        by_reason.append(
            {
                "reason": row.scrap_reason.value,
                "scrap_kg": round(float(row.scrap or 0.0), 3),
            }
        )
    by_reason.sort(key=lambda x: x["scrap_kg"], reverse=True)

    return {
        "days_back": days_back,
        "machine_code": machine_code,
        "total_scrap_kg": round(total_scrap, 3),
        "by_machine": by_machine,
        "by_reason": by_reason,
    }


def by_id_for_code(by_id: Dict[int, Machine], code: str) -> int:
    """Helper inverso: devuelve el id a partir del code en el cache by_id."""
    for mid, m in by_id.items():
        if m.code == code:
            return mid
    return -1


# -----------------------------------------------------------------------------
# Tool 7 — Yield (rendimiento out/in) por máquina
# -----------------------------------------------------------------------------
def get_yield_summary(
    db: Session,
    *,
    days_back: int = 6,
    machine_code: Optional[str] = None,
    operation_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Calcula yield = quantity_out / quantity_in por máquina sobre operaciones
    COMPLETED en la ventana. Identifica cuellos de botella de calidad.
    EMP siempre da yield ≈ 1.0 (no genera scrap).

    Filtros opcionales:
      · machine_code: una máquina concreta (ej. "FON-01").
      · operation_type: una ETAPA de la ruta. El modelo no guarda un "tipo de
        operación" propio: la etapa se deriva del TIPO DE MÁQUINA
        (`machine.type`). Por eso operation_type acepta un valor de MachineType
        (impresora/tubuladora/fondadora/empacadora) y agrega TODAS las máquinas
        de esa etapa — ej. "fondadora" combina FON-01 + FON-02. Cuando se usa,
        la respuesta añade un bloque `aggregate` con el yield combinado.
    """
    start_dt, end_dt = _date_window(days_back=days_back)

    q = (
        select(
            OrderOperation.machine_id,
            func.coalesce(func.sum(OrderOperation.quantity_in), 0).label("qin"),
            func.coalesce(func.sum(OrderOperation.quantity_out), 0).label("qout"),
            func.count().label("ops"),
        )
        .where(OrderOperation.status == OperationStatus.COMPLETED)
        .where(OrderOperation.actual_end.is_not(None))
        .where(OrderOperation.actual_end >= start_dt)
        .where(OrderOperation.actual_end < end_dt)
        .group_by(OrderOperation.machine_id)
    )

    machines = list(db.scalars(select(Machine).order_by(Machine.code)))
    by_id = {m.id: m for m in machines}

    if machine_code:
        target = next((m for m in machines if m.code == machine_code), None)
        if target is None:
            return {"error": f"Máquina '{machine_code}' no existe"}
        q = q.where(OrderOperation.machine_id == target.id)

    resolved_type: Optional[MachineType] = None
    if operation_type:
        try:
            resolved_type = MachineType(operation_type)
        except ValueError:
            return {
                "error": (
                    f"operation_type='{operation_type}' inválido "
                    f"(válidos: {[t.value for t in MachineType]})"
                )
            }
        type_ids = [m.id for m in machines if m.type == resolved_type]
        q = q.where(OrderOperation.machine_id.in_(type_ids))

    items = []
    for row in db.execute(q).all():
        m = by_id.get(row.machine_id)
        if m is None:
            continue
        qin = int(row.qin or 0)
        qout = int(row.qout or 0)
        ratio = round(qout / qin, 4) if qin > 0 else None
        items.append(
            {
                "machine_code": m.code,
                "machine_type": m.type.value,
                "quantity_in": qin,
                "quantity_out": qout,
                "yield_ratio": ratio,
                "yield_pct": round(ratio * 100, 2) if ratio is not None else None,
                "operations_count": int(row.ops or 0),
            }
        )
    items.sort(key=lambda x: (x["yield_ratio"] is None, x["yield_ratio"] or 0))

    # Agregado por etapa: combina todas las máquinas del tipo solicitado.
    aggregate = None
    if resolved_type is not None and items:
        tot_in = sum(i["quantity_in"] for i in items)
        tot_out = sum(i["quantity_out"] for i in items)
        agg_ratio = round(tot_out / tot_in, 4) if tot_in > 0 else None
        aggregate = {
            "operation_type": resolved_type.value,
            "quantity_in": tot_in,
            "quantity_out": tot_out,
            "yield_ratio": agg_ratio,
            "yield_pct": round(agg_ratio * 100, 2) if agg_ratio is not None else None,
            "machines_count": len(items),
        }

    bottleneck = items[0] if items and items[0].get("yield_ratio") is not None else None
    return {
        "days_back": days_back,
        "machine_code": machine_code,
        "operation_type": operation_type,
        "items": items,
        "aggregate": aggregate,
        "bottleneck": bottleneck,
    }


# -----------------------------------------------------------------------------
# Tool 8 — WIP (Work In Progress) en tiempo real
# -----------------------------------------------------------------------------
def get_wip_status(db: Session) -> Dict[str, Any]:
    """
    Snapshot de operaciones IN_PROGRESS y READY agrupadas por máquina, con
    unidades vivas en tránsito. Permite responder "¿cuántos sacos están en
    el piso ahora mismo?" o "¿qué máquina tiene cola?".
    """
    rows = db.execute(
        select(
            OrderOperation.machine_id,
            OrderOperation.status,
            func.count().label("cnt"),
            func.coalesce(func.sum(OrderOperation.quantity_in), 0).label("qin"),
            func.coalesce(func.sum(OrderOperation.quantity_out), 0).label("qout"),
        )
        .where(
            OrderOperation.status.in_(
                [OperationStatus.IN_PROGRESS, OperationStatus.READY]
            )
        )
        .group_by(OrderOperation.machine_id, OrderOperation.status)
    ).all()

    machines = list(db.scalars(select(Machine).order_by(Machine.code)))
    by_id = {m.id: m for m in machines}
    by_machine: Dict[int, Dict[str, Any]] = {}
    for row in rows:
        slot = by_machine.setdefault(
            row.machine_id,
            {"in_progress_ops": 0, "ready_ops": 0, "ip_units": 0, "ready_units": 0},
        )
        if row.status == OperationStatus.IN_PROGRESS:
            slot["in_progress_ops"] = int(row.cnt or 0)
            slot["ip_units"] = max(0, int(row.qin or 0) - int(row.qout or 0))
        else:
            slot["ready_ops"] = int(row.cnt or 0)
            slot["ready_units"] = int(row.qin or 0)

    items = []
    total_in_progress = 0
    total_ready = 0
    total_units = 0
    for m in machines:
        slot = by_machine.get(
            m.id,
            {"in_progress_ops": 0, "ready_ops": 0, "ip_units": 0, "ready_units": 0},
        )
        units = slot["ip_units"] + slot["ready_units"]
        total_in_progress += slot["in_progress_ops"]
        total_ready += slot["ready_ops"]
        total_units += units
        items.append(
            {
                "machine_code": m.code,
                "machine_type": m.type.value,
                "in_progress_operations": slot["in_progress_ops"],
                "ready_operations": slot["ready_ops"],
                "units_in_progress": slot["ip_units"],
                "units_ready": slot["ready_units"],
                "units_total": units,
            }
        )

    return {
        "machines": items,
        "total_in_progress_operations": total_in_progress,
        "total_ready_operations": total_ready,
        "total_units_in_line": total_units,
    }


# -----------------------------------------------------------------------------
# Tool 9 — Análisis de cuello de botella (throughput)
# -----------------------------------------------------------------------------
def get_bottleneck_analysis(db: Session, *, days_back: int = 6) -> Dict[str, Any]:
    """
    Identifica el cuello de botella de THROUGHPUT de la planta.

    A diferencia del "cuello de calidad" de get_yield_summary (la máquina que
    más rechaza), aquí buscamos la máquina que más ACUMULA trabajo en cola
    frente a su capacidad demostrada.

    Para cada máquina:
      · cola actual (snapshot) = operaciones PENDING + READY asignadas.
      · ready_units = sum(quantity_in) de las READY (las PENDING aún no tienen
        quantity_in poblado porque la etapa previa no ha cerrado).
      · completadas = operaciones COMPLETED con actual_end en la ventana
        (capacidad histórica demostrada).
      · backlog_ratio = cola / max(completadas, 1).

    El cuello es la máquina con mayor backlog_ratio: mucha cola frente a poca
    capacidad. Una máquina estancada (cola > 0 y 0 completadas) eleva su ratio
    al tamaño de la cola, lo que la delata aunque produzca poco en absoluto.
    """
    start_dt, end_dt = _date_window(days_back=days_back)

    # Cola actual (snapshot, SIN ventana temporal): PENDING + READY por máquina.
    queue_rows = db.execute(
        select(
            OrderOperation.machine_id,
            func.count().label("waiting"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            OrderOperation.status == OperationStatus.READY,
                            OrderOperation.quantity_in,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("ready_units"),
        )
        .where(
            OrderOperation.status.in_(
                [OperationStatus.PENDING, OperationStatus.READY]
            )
        )
        .group_by(OrderOperation.machine_id)
    ).all()

    # Operaciones completadas en la ventana (capacidad demostrada).
    done_rows = db.execute(
        select(OrderOperation.machine_id, func.count().label("done"))
        .where(OrderOperation.status == OperationStatus.COMPLETED)
        .where(OrderOperation.actual_end.is_not(None))
        .where(OrderOperation.actual_end >= start_dt)
        .where(OrderOperation.actual_end < end_dt)
        .group_by(OrderOperation.machine_id)
    ).all()

    queue_by_id = {r.machine_id: r for r in queue_rows}
    done_by_id = {r.machine_id: int(r.done or 0) for r in done_rows}

    machines = list(db.scalars(select(Machine).order_by(Machine.code)))
    items: List[Dict[str, Any]] = []
    for m in machines:
        q = queue_by_id.get(m.id)
        waiting = int(q.waiting) if q else 0
        ready_units = int(q.ready_units) if q else 0
        done = done_by_id.get(m.id, 0)
        backlog_ratio = round(waiting / max(done, 1), 3)
        items.append(
            {
                "machine_code": m.code,
                "machine_type": m.type.value,
                "waiting_operations": waiting,
                "ready_units": ready_units,
                "completed_operations": done,
                "backlog_ratio": backlog_ratio,
            }
        )

    # Mayor backlog_ratio primero; desempate por tamaño de cola.
    items.sort(
        key=lambda x: (x["backlog_ratio"], x["waiting_operations"]), reverse=True
    )

    # Sin cola no hay cuello: el bottleneck debe tener al menos una en espera.
    bottleneck = next((it for it in items if it["waiting_operations"] > 0), None)

    return {
        "days_back": days_back,
        "machines": items,
        "bottleneck": bottleneck,
    }


# -----------------------------------------------------------------------------
# Registro central + schemas para el LLM
# -----------------------------------------------------------------------------
TOOL_REGISTRY: Dict[str, Any] = {
    "get_production_stats": get_production_stats,
    "get_machine_status": get_machine_status,
    "get_order_info": get_order_info,
    "get_oee_data": get_oee_data,
    "get_alerts": get_alerts,
    "get_scrap_summary": get_scrap_summary,
    "get_yield_summary": get_yield_summary,
    "get_wip_status": get_wip_status,
    "get_bottleneck_analysis": get_bottleneck_analysis,
}

# Schemas en formato Anthropic tools / OpenAI function calling.
TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "name": "get_production_stats",
        "description": (
            "Estadísticas de producción (sacos producidos, órdenes completadas, "
            "tasa de cumplimiento) para una ventana temporal opcionalmente "
            "filtrada por máquina o producto."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "days_back": {
                    "type": "integer",
                    "description": "0=hoy, 1=ayer+hoy, 7=última semana",
                    "default": 0,
                },
                "machine_code": {"type": "string", "description": "TUB-01, IMP-02, etc."},
                "product_type": {"type": "string"},
            },
        },
    },
    {
        "name": "get_machine_status",
        "description": (
            "Estado actual de una o todas las máquinas, con conteo de paradas e "
            "incidencias en la ventana indicada. Devuelve la lista ORDENADA por "
            "número de paradas (más paradas primero) — útil para responder "
            "'¿qué máquina tiene más paradas hoy?'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "machine_code": {"type": "string"},
                "days_back_for_events": {"type": "integer", "default": 0},
            },
        },
    },
    {
        "name": "get_order_info",
        "description": (
            "Detalle de una orden de producción (estado, avance, tiempos, "
            "predicción de retraso si existe)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_number": {"type": "string", "description": "Ej. OP-2026-001234"},
                "order_id": {"type": "integer"},
            },
        },
    },
    {
        "name": "get_oee_data",
        "description": (
            "OEE (Disponibilidad × Rendimiento × Calidad) de planta o de una "
            "máquina específica, agregado en la ventana."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "machine_code": {"type": "string"},
                "days_back": {"type": "integer", "default": 0},
            },
        },
    },
    {
        "name": "get_alerts",
        "description": (
            "Órdenes con alta probabilidad de retraso según el modelo ML, "
            "ordenadas de más probable a menos."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "threshold": {"type": "number", "default": 0.6},
                "limit": {"type": "integer", "default": 5},
            },
        },
    },
    {
        "name": "get_scrap_summary",
        "description": (
            "Resumen de desperdicio (scrap_kg) por máquina y por razón "
            "(quality_defect, setup_loss, material_break, other). Devuelve "
            "Pareto: la máquina/razón que más merma genera aparece primero. "
            "Útil para 'cuál máquina genera más merma' o 'causa principal de scrap'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "days_back": {
                    "type": "integer",
                    "description": "0=hoy, 7=últimos 7 días, etc.",
                    "default": 0,
                },
                "machine_code": {"type": "string", "description": "Filtrar por una máquina."},
            },
        },
    },
    {
        "name": "get_yield_summary",
        "description": (
            "Yield (rendimiento) = quantity_out / quantity_in sobre operaciones "
            "cerradas en la ventana. Identifica cuellos de botella de CALIDAD: "
            "la máquina (o etapa) con yield más bajo es la que más rechaza. "
            "Filtra por máquina (machine_code) o por ETAPA de la ruta "
            "(operation_type: impresora/tubuladora/fondadora/empacadora), que "
            "agrega todas las máquinas de esa etapa. EMP da yield ≈ 1.0."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "days_back": {
                    "type": "integer",
                    "description": "Días hacia atrás (default 6 = última semana).",
                    "default": 6,
                },
                "machine_code": {"type": "string"},
                "operation_type": {
                    "type": "string",
                    "description": (
                        "Etapa de la ruta: impresora, tubuladora, fondadora o "
                        "empacadora. Agrega todas las máquinas de esa etapa."
                    ),
                    "enum": ["impresora", "tubuladora", "fondadora", "empacadora"],
                },
            },
        },
    },
    {
        "name": "get_bottleneck_analysis",
        "description": (
            "Cuello de botella de THROUGHPUT (no de calidad): la máquina que "
            "más acumula operaciones en cola (PENDING+READY) frente a su "
            "capacidad histórica demostrada (completadas en la ventana). "
            "Devuelve el ranking por backlog_ratio y la máquina cuello. Útil "
            "para '¿cuál es el cuello de botella de la planta?' o '¿qué máquina "
            "está más saturada / es la más lenta?'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "days_back": {
                    "type": "integer",
                    "description": "Ventana para la capacidad histórica (default 6).",
                    "default": 6,
                },
            },
        },
    },
    {
        "name": "get_wip_status",
        "description": (
            "Snapshot del Work-In-Progress: operaciones IN_PROGRESS y READY "
            "por máquina, con unidades vivas en tránsito. Responde a "
            "'cuántos sacos hay en el piso ahora' o 'qué máquina tiene cola'."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
]


__all__ = [
    "TOOL_REGISTRY",
    "TOOL_SCHEMAS",
    "get_production_stats",
    "get_machine_status",
    "get_order_info",
    "get_oee_data",
    "get_alerts",
    "get_scrap_summary",
    "get_yield_summary",
    "get_wip_status",
    "get_bottleneck_analysis",
]
