"""
Servicio del Dashboard de KPIs y OEE.

Concentra las consultas SQL agregadas que alimentan la página /dashboard.
Cada función devuelve un DTO listo para serializar (ver `app.schemas.dashboard`).

Decisiones de diseño:
- Las agregaciones de OEE se hacen sobre `oee_records` (granularidad: máquina ×
  turno × día). El "OEE de planta" es un promedio simple sobre los registros
  del día más reciente disponible — modelarlo como ponderado por horas de
  operación es trabajo del Step 7.
- "Producción del día" se calcula como la suma de `quantity_produced` sobre
  órdenes con `actual_start::date = hoy` ó `actual_end::date = hoy` ó
  `status = IN_PROGRESS`. Es un proxy razonable hasta que el ETL real entregue
  un timestamp por saco.
- Las alertas se sirven a partir de la última `MLPrediction` por orden cuya
  orden todavía no esté COMPLETED — así el panel sólo muestra órdenes vivas.
"""

from __future__ import annotations

from datetime import date as date_t, datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, case, desc, func, or_, select
from sqlalchemy.orm import Session

from app.models import (
    Machine,
    MachineType,
    MLPrediction,
    OEERecord,
    OperationStatus,
    OrderOperation,
    OrderStatus,
    ProductionOrder,
    Shift,
    ShiftName,
)
from app.schemas.dashboard import (
    AlertItem,
    AlertsResponse,
    MachineRankingItem,
    MachineRankingResponse,
    OEETrendPoint,
    OEETrendResponse,
    OrderFulfillmentPoint,
    OrderFulfillmentResponse,
    OverviewResponse,
    ProductionByShiftPoint,
    ProductionByShiftResponse,
    ScrapByMachineDayPoint,
    ScrapByMachineResponse,
    ScrapMachineTotal,
    WIPMachineSlot,
    WIPResponse,
    YieldByMachineItem,
    YieldByOperationResponse,
)


# -----------------------------------------------------------------------------
# Utilidades
# -----------------------------------------------------------------------------
def _today_utc() -> date_t:
    """Devuelve el día actual en UTC. Mantenerlo aislado facilita testearlo."""
    return datetime.now(tz=timezone.utc).date()


def _safe_avg(values: List[float]) -> Optional[float]:
    """Promedio simple seguro frente a listas vacías."""
    return sum(values) / len(values) if values else None


# -----------------------------------------------------------------------------
# /overview
# -----------------------------------------------------------------------------
def get_overview(db: Session) -> OverviewResponse:
    """
    Calcula los KPIs de cabecera de la planta.

    El "OEE de planta" se computa sobre el día más reciente con registros.
    Si no hay datos en absoluto se devuelven ceros para que el frontend pueda
    renderizar las tarjetas sin lógica condicional adicional.
    """
    # 1. Día más reciente con OEE (ref) y día anterior (yest) para delta vs ayer.
    ref_date = db.scalar(select(func.max(OEERecord.date)))

    plant_oee = avail = perf = qual = 0.0
    plant_oee_yesterday: Optional[float] = None

    if ref_date is not None:
        avg_today = db.execute(
            select(
                func.avg(OEERecord.oee_value),
                func.avg(OEERecord.availability),
                func.avg(OEERecord.performance),
                func.avg(OEERecord.quality),
            ).where(OEERecord.date == ref_date)
        ).one()
        plant_oee = float(avg_today[0] or 0.0)
        avail = float(avg_today[1] or 0.0)
        perf = float(avg_today[2] or 0.0)
        qual = float(avg_today[3] or 0.0)

        prev_date = db.scalar(
            select(func.max(OEERecord.date)).where(OEERecord.date < ref_date)
        )
        if prev_date is not None:
            yest = db.scalar(
                select(func.avg(OEERecord.oee_value)).where(OEERecord.date == prev_date)
            )
            plant_oee_yesterday = float(yest) if yest is not None else None

    # 2. Conteo de órdenes — "hoy" = órdenes que tocan el día de hoy.
    today = _today_utc()
    start_today = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)
    end_today = start_today + timedelta(days=1)

    orders_completed_today = db.scalar(
        select(func.count(ProductionOrder.id)).where(
            ProductionOrder.status == OrderStatus.COMPLETED,
            ProductionOrder.actual_end >= start_today,
            ProductionOrder.actual_end < end_today,
        )
    ) or 0
    orders_in_progress = db.scalar(
        select(func.count(ProductionOrder.id)).where(
            ProductionOrder.status == OrderStatus.IN_PROGRESS
        )
    ) or 0
    orders_pending = db.scalar(
        select(func.count(ProductionOrder.id)).where(
            ProductionOrder.status == OrderStatus.PENDING
        )
    ) or 0
    orders_delayed = db.scalar(
        select(func.count(ProductionOrder.id)).where(
            ProductionOrder.status == OrderStatus.DELAYED
        )
    ) or 0

    # 3. Producción y objetivo del día — órdenes activas hoy o terminadas hoy.
    prod_today_stmt = select(
        func.coalesce(func.sum(ProductionOrder.quantity_produced), 0),
        func.coalesce(func.sum(ProductionOrder.quantity_ordered), 0),
    ).where(
        or_(
            ProductionOrder.status == OrderStatus.IN_PROGRESS,
            and_(
                ProductionOrder.status == OrderStatus.COMPLETED,
                ProductionOrder.actual_end >= start_today,
                ProductionOrder.actual_end < end_today,
            ),
        )
    )
    production_today, production_target_today = db.execute(prod_today_stmt).one()

    # 4. Estado del parque de máquinas.
    total_machines = db.scalar(select(func.count(Machine.id))) or 0
    active_machines = db.scalar(
        select(func.count(Machine.id)).where(Machine.status == "running")
    ) or 0

    return OverviewResponse(
        plant_oee=round(plant_oee, 4),
        plant_oee_yesterday=round(plant_oee_yesterday, 4)
        if plant_oee_yesterday is not None
        else None,
        availability=round(avail, 4),
        performance=round(perf, 4),
        quality=round(qual, 4),
        orders_completed_today=int(orders_completed_today),
        orders_in_progress=int(orders_in_progress),
        orders_pending=int(orders_pending),
        orders_delayed=int(orders_delayed),
        production_today=int(production_today or 0),
        production_target_today=int(production_target_today or 0),
        active_machines=int(active_machines),
        total_machines=int(total_machines),
        reference_date=ref_date,
    )


# -----------------------------------------------------------------------------
# /oee-trend
# -----------------------------------------------------------------------------
def get_oee_trend(
    db: Session, *, days: int, machine_id: Optional[int] = None
) -> OEETrendResponse:
    """
    Devuelve la serie diaria de OEE (planta o por máquina) para los últimos N días.

    Cada punto es el promedio simple sobre los 3 turnos del día. Si una fecha
    no tiene registros, simplemente no aparece en la serie (no se rellenan ceros)
    para que Recharts dibuje un hueco realista en lugar de un valle artificial.
    """
    end_date = _today_utc()
    start_date = end_date - timedelta(days=days - 1)

    stmt = (
        select(
            OEERecord.date,
            func.avg(OEERecord.availability).label("avail"),
            func.avg(OEERecord.performance).label("perf"),
            func.avg(OEERecord.quality).label("qual"),
            func.avg(OEERecord.oee_value).label("oee"),
            func.count(OEERecord.id).label("n"),
        )
        .where(OEERecord.date >= start_date, OEERecord.date <= end_date)
        .group_by(OEERecord.date)
        .order_by(OEERecord.date.asc())
    )
    if machine_id is not None:
        stmt = stmt.where(OEERecord.machine_id == machine_id)

    rows = db.execute(stmt).all()
    points = [
        OEETrendPoint(
            date=row.date,
            availability=round(float(row.avail), 4),
            performance=round(float(row.perf), 4),
            quality=round(float(row.qual), 4),
            oee=round(float(row.oee), 4),
            sample_count=int(row.n),
        )
        for row in rows
    ]
    return OEETrendResponse(machine_id=machine_id, days=days, points=points)


# -----------------------------------------------------------------------------
# /production-by-shift
# -----------------------------------------------------------------------------
def get_production_by_shift(db: Session, *, days: int) -> ProductionByShiftResponse:
    """
    Producción agregada por día y turno para los últimos N días.

    Aproxima "producción de un turno" como la cantidad producida por las
    órdenes cuyo `actual_start` cae dentro de la franja horaria del turno.
    Es una aproximación razonable para el dashboard hasta que el ETL traiga
    eventos a nivel de saco con timestamp.
    """
    end_date = _today_utc()
    start_date = end_date - timedelta(days=days - 1)
    start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)

    # Lookup turnos → asume seed con turno_1=06-14, turno_2=14-22, turno_3=22-06.
    shifts: Dict[ShiftName, Shift] = {
        s.name: s for s in db.scalars(select(Shift)).all()
    }

    # Hour-of-day del actual_start, en UTC. Suficiente para asignar turno.
    hour = func.extract("hour", ProductionOrder.actual_start)

    def _shift_label_case():
        # turno_1: 06–14, turno_2: 14–22, turno_3: el resto (00–06 ó 22–24).
        return case(
            (and_(hour >= 6, hour < 14), "turno_1"),
            (and_(hour >= 14, hour < 22), "turno_2"),
            else_="turno_3",
        )

    stmt = (
        select(
            func.date(ProductionOrder.actual_start).label("d"),
            _shift_label_case().label("shift"),
            func.coalesce(func.sum(ProductionOrder.quantity_produced), 0).label("qty"),
        )
        .where(ProductionOrder.actual_start.is_not(None))
        .where(ProductionOrder.actual_start >= start_dt)
        .group_by("d", "shift")
        .order_by("d")
    )

    rows = db.execute(stmt).all()

    # Pivot en Python: filas (date, shift_label, qty) → dict por fecha.
    bucket: Dict[date_t, Dict[str, int]] = {}
    for row in rows:
        d = row.d if isinstance(row.d, date_t) else row.d
        bucket.setdefault(d, {"turno_1": 0, "turno_2": 0, "turno_3": 0})
        bucket[d][row.shift] += int(row.qty or 0)

    points: List[ProductionByShiftPoint] = []
    for d in sorted(bucket.keys()):
        b = bucket[d]
        total = b["turno_1"] + b["turno_2"] + b["turno_3"]
        points.append(
            ProductionByShiftPoint(
                date=d,
                turno_1=b["turno_1"],
                turno_2=b["turno_2"],
                turno_3=b["turno_3"],
                total=total,
            )
        )

    # Aprovecho el lookup de turnos para validar coherencia, pero no es obligatorio.
    _ = shifts  # noqa: F841 — futura extensión: ponderar por horas del turno.

    return ProductionByShiftResponse(days=days, points=points)


# -----------------------------------------------------------------------------
# /order-fulfillment
# -----------------------------------------------------------------------------
def get_order_fulfillment(db: Session, *, days: int) -> OrderFulfillmentResponse:
    """
    Conteo diario de órdenes por estado, agrupado sobre `planned_end::date`.

    El frontend lo dibuja como gráfico de área apilado. También se devuelven
    totales del rango para subtítulos del widget.
    """
    end_date = _today_utc()
    start_date = end_date - timedelta(days=days - 1)
    start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.combine(end_date + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)

    stmt = (
        select(
            func.date(ProductionOrder.planned_end).label("d"),
            ProductionOrder.status,
            func.count(ProductionOrder.id).label("n"),
        )
        .where(ProductionOrder.planned_end >= start_dt)
        .where(ProductionOrder.planned_end < end_dt)
        .group_by("d", ProductionOrder.status)
        .order_by("d")
    )
    rows = db.execute(stmt).all()

    bucket: Dict[date_t, Dict[str, int]] = {}
    totals = {"completed": 0, "in_progress": 0, "pending": 0, "delayed": 0}
    for row in rows:
        d = row.d
        bucket.setdefault(
            d, {"completed": 0, "in_progress": 0, "pending": 0, "delayed": 0}
        )
        key = row.status.value if hasattr(row.status, "value") else str(row.status)
        if key in bucket[d]:
            bucket[d][key] = int(row.n)
            totals[key] += int(row.n)

    points = [
        OrderFulfillmentPoint(date=d, **bucket[d])  # type: ignore[arg-type]
        for d in sorted(bucket.keys())
    ]

    return OrderFulfillmentResponse(
        days=days,
        points=points,
        total_completed=totals["completed"],
        total_delayed=totals["delayed"],
        total_pending=totals["pending"],
        total_in_progress=totals["in_progress"],
    )


# -----------------------------------------------------------------------------
# /machine-ranking
# -----------------------------------------------------------------------------
def get_machine_ranking(db: Session, *, days: int) -> MachineRankingResponse:
    """
    Ranking de máquinas por OEE promedio en los últimos N días.

    Incluye también A/P/Q promedio para que el frontend pueda mostrar el
    desglose en la fila expandida. Ordenado por OEE DESC, empates a favor
    del code alfabético.
    """
    end_date = _today_utc()
    start_date = end_date - timedelta(days=days - 1)

    stmt = (
        select(
            Machine.id,
            Machine.code,
            Machine.name,
            Machine.type,
            func.avg(OEERecord.oee_value).label("avg_oee"),
            func.avg(OEERecord.availability).label("avg_avail"),
            func.avg(OEERecord.performance).label("avg_perf"),
            func.avg(OEERecord.quality).label("avg_qual"),
            func.count(OEERecord.id).label("n"),
        )
        .select_from(Machine)
        .join(
            OEERecord,
            and_(
                OEERecord.machine_id == Machine.id,
                OEERecord.date >= start_date,
                OEERecord.date <= end_date,
            ),
            isouter=True,
        )
        .group_by(Machine.id, Machine.code, Machine.name, Machine.type)
        .order_by(desc("avg_oee"), Machine.code.asc())
    )
    rows = db.execute(stmt).all()
    items = [
        MachineRankingItem(
            machine_id=row.id,
            code=row.code,
            name=row.name,
            type=row.type,
            avg_oee=round(float(row.avg_oee), 4) if row.avg_oee is not None else None,
            avg_availability=round(float(row.avg_avail), 4)
            if row.avg_avail is not None
            else None,
            avg_performance=round(float(row.avg_perf), 4)
            if row.avg_perf is not None
            else None,
            avg_quality=round(float(row.avg_qual), 4)
            if row.avg_qual is not None
            else None,
            sample_count=int(row.n or 0),
        )
        for row in rows
    ]
    return MachineRankingResponse(days=days, items=items)


# -----------------------------------------------------------------------------
# /alerts
# -----------------------------------------------------------------------------
def get_alerts(db: Session, *, threshold: float, limit: int) -> AlertsResponse:
    """
    Devuelve órdenes activas con la última predicción de retraso por encima
    del umbral. "Activa" = status ∈ {PENDING, IN_PROGRESS, DELAYED}.

    Estrategia: subconsulta con `row_number()` por order_id para quedarse con
    la predicción más reciente, luego se filtra por probabilidad.
    """
    rn = (
        func.row_number()
        .over(
            partition_by=MLPrediction.order_id,
            order_by=desc(MLPrediction.created_at),
        )
        .label("rn")
    )
    pred_sub = select(
        MLPrediction.id.label("pred_id"),
        MLPrediction.order_id,
        MLPrediction.delay_probability,
        MLPrediction.predicted_delay_hours,
        MLPrediction.model_version,
        MLPrediction.created_at,
        rn,
    ).subquery("pred")

    stmt = (
        select(
            ProductionOrder.id.label("order_id"),
            ProductionOrder.order_number,
            ProductionOrder.product_type,
            ProductionOrder.status,
            ProductionOrder.planned_end,
            ProductionOrder.machine_id,
            Machine.code.label("machine_code"),
            Machine.name.label("machine_name"),
            pred_sub.c.delay_probability,
            pred_sub.c.predicted_delay_hours,
            pred_sub.c.model_version,
            pred_sub.c.created_at.label("predicted_at"),
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
        .order_by(desc(pred_sub.c.delay_probability), ProductionOrder.planned_end.asc())
        .limit(limit)
    )
    rows = db.execute(stmt).all()
    items = [
        AlertItem(
            order_id=row.order_id,
            order_number=row.order_number,
            product_type=row.product_type,
            machine_id=row.machine_id,
            machine_code=row.machine_code,
            machine_name=row.machine_name,
            status=row.status,
            delay_probability=round(float(row.delay_probability), 4),
            predicted_delay_hours=round(float(row.predicted_delay_hours), 2),
            planned_end=row.planned_end,
            model_version=row.model_version,
            predicted_at=row.predicted_at,
        )
        for row in rows
    ]
    return AlertsResponse(threshold=threshold, items=items)


# -----------------------------------------------------------------------------
# /scrap-by-machine — kg de desperdicio diario por máquina (Pareto + tendencia)
# -----------------------------------------------------------------------------
def get_scrap_by_machine(db: Session, *, days: int) -> ScrapByMachineResponse:
    """
    Suma `scrap_kg` de operaciones COMPLETED/IN_PROGRESS agrupadas por
    (día_de_actual_end, máquina). Útil para Pareto: ¿qué máquina genera
    más merma? ¿en qué día se disparó?
    """
    today = _today_utc()
    start_date = today - timedelta(days=days - 1)
    start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)

    machines = list(db.scalars(select(Machine).order_by(Machine.code)))

    # Tendencia diaria por máquina
    day_col = func.date(OrderOperation.actual_end).label("d")
    rows = db.execute(
        select(
            day_col,
            OrderOperation.machine_id,
            func.coalesce(func.sum(OrderOperation.scrap_kg), 0.0).label("scrap"),
        )
        .where(OrderOperation.actual_end.is_not(None))
        .where(OrderOperation.actual_end >= start_dt)
        .group_by(day_col, OrderOperation.machine_id)
    ).all()

    machines_by_id = {m.id: m for m in machines}
    points: List[ScrapByMachineDayPoint] = []
    for row in rows:
        m = machines_by_id.get(row.machine_id)
        if m is None:
            continue
        points.append(
            ScrapByMachineDayPoint(
                date=row.d,
                machine_id=m.id,
                machine_code=m.code,
                machine_type=m.type,
                scrap_kg=round(float(row.scrap), 3),
            )
        )

    # Acumulado por máquina (para gráfica de barras / Pareto)
    totals_rows = db.execute(
        select(
            OrderOperation.machine_id,
            func.coalesce(func.sum(OrderOperation.scrap_kg), 0.0).label("scrap"),
        )
        .where(OrderOperation.actual_end.is_not(None))
        .where(OrderOperation.actual_end >= start_dt)
        .group_by(OrderOperation.machine_id)
    ).all()
    totals_by_machine: List[ScrapMachineTotal] = []
    for row in totals_rows:
        m = machines_by_id.get(row.machine_id)
        if m is None:
            continue
        totals_by_machine.append(
            ScrapMachineTotal(
                machine_id=m.id,
                machine_code=m.code,
                machine_type=m.type,
                scrap_kg=round(float(row.scrap), 3),
            )
        )
    totals_by_machine.sort(key=lambda t: t.scrap_kg, reverse=True)

    return ScrapByMachineResponse(
        days=days,
        points=sorted(points, key=lambda p: (p.date, p.machine_code)),
        totals_by_machine=totals_by_machine,
    )


# -----------------------------------------------------------------------------
# /yield-by-operation — rendimiento out/in por máquina
# -----------------------------------------------------------------------------
def get_yield_by_operation(db: Session, *, days: int) -> YieldByOperationResponse:
    """
    Calcula yield = SUM(quantity_out) / SUM(quantity_in) por máquina sobre
    las operaciones cerradas en los últimos N días. Identifica cuellos de
    botella de calidad (la máquina con yield más bajo es la que más rechaza).

    EMP siempre da yield ≈ 1.0 (no genera scrap).
    """
    today = _today_utc()
    start_date = today - timedelta(days=days - 1)
    start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)

    rows = db.execute(
        select(
            OrderOperation.machine_id,
            func.coalesce(func.sum(OrderOperation.quantity_in), 0).label("qty_in"),
            func.coalesce(func.sum(OrderOperation.quantity_out), 0).label("qty_out"),
            func.count().label("ops_count"),
        )
        .where(OrderOperation.status == OperationStatus.COMPLETED)
        .where(OrderOperation.actual_end.is_not(None))
        .where(OrderOperation.actual_end >= start_dt)
        .group_by(OrderOperation.machine_id)
    ).all()

    machines = list(db.scalars(select(Machine).order_by(Machine.code)))
    by_id = {m.id: m for m in machines}
    items: List[YieldByMachineItem] = []
    for row in rows:
        m = by_id.get(row.machine_id)
        if m is None:
            continue
        qin = int(row.qty_in or 0)
        qout = int(row.qty_out or 0)
        yratio = round(qout / qin, 4) if qin > 0 else None
        items.append(
            YieldByMachineItem(
                machine_id=m.id,
                machine_code=m.code,
                machine_type=m.type,
                quantity_in_total=qin,
                quantity_out_total=qout,
                yield_ratio=yratio,
                operations_count=int(row.ops_count or 0),
            )
        )
    items.sort(key=lambda i: i.machine_code)
    return YieldByOperationResponse(days=days, items=items)


# -----------------------------------------------------------------------------
# /wip — Work In Progress en tiempo real
# -----------------------------------------------------------------------------
def get_wip(db: Session) -> WIPResponse:
    """
    Snapshot del WIP por máquina: operaciones in_progress y ready, con
    sus unidades acumuladas. Permite responder "¿cuántos sacos están
    en tránsito en este momento entre máquinas?".
    """
    machines = list(db.scalars(select(Machine).order_by(Machine.code)))

    rows = db.execute(
        select(
            OrderOperation.machine_id,
            OrderOperation.status,
            func.count().label("cnt"),
            func.coalesce(func.sum(OrderOperation.quantity_in), 0).label("qin"),
            func.coalesce(func.sum(OrderOperation.quantity_out), 0).label("qout"),
        )
        .where(OrderOperation.status.in_([OperationStatus.IN_PROGRESS, OperationStatus.READY]))
        .group_by(OrderOperation.machine_id, OrderOperation.status)
    ).all()

    by_machine: Dict[int, Dict[str, int]] = {}
    for row in rows:
        slot = by_machine.setdefault(
            row.machine_id,
            {"ip_count": 0, "ready_count": 0, "ip_units": 0, "ready_units": 0},
        )
        if row.status == OperationStatus.IN_PROGRESS:
            slot["ip_count"] = int(row.cnt or 0)
            # En IN_PROGRESS las unidades "vivas" son las que faltan por
            # producir = quantity_in - quantity_out.
            slot["ip_units"] = max(0, int(row.qin or 0) - int(row.qout or 0))
        else:
            slot["ready_count"] = int(row.cnt or 0)
            slot["ready_units"] = int(row.qin or 0)

    machines_payload: List[WIPMachineSlot] = []
    total_units = 0
    for m in machines:
        slot = by_machine.get(m.id, {"ip_count": 0, "ready_count": 0, "ip_units": 0, "ready_units": 0})
        machines_payload.append(
            WIPMachineSlot(
                machine_id=m.id,
                machine_code=m.code,
                machine_type=m.type,
                operations_in_progress=slot["ip_count"],
                operations_ready=slot["ready_count"],
                units_in_progress=slot["ip_units"],
                units_ready=slot["ready_units"],
            )
        )
        total_units += slot["ip_units"] + slot["ready_units"]

    return WIPResponse(machines=machines_payload, total_units_in_line=total_units)
