"""
Script de seed para SmartSack.

Genera datos realistas de una planta de sacos de papel para los últimos
6 meses (más 30 días de planificación futura). Pensado para desarrollo y
para entrenar el motor de ML.

Modelo de operaciones encadenadas (refactor 2026-05):
    Cada orden cabecera se descompone en 4 operaciones que recorren la
    línea: IMP → TUB → FON → EMP. Una orden vive en la "Línea A"
    (IMP-01, TUB-01, FON-01, EMP-01) o en la "Línea B" (IMP-02, ...).
    Cada operación tiene su propia entrada/salida en unidades y su
    desperdicio en kg (excepto EMP, que no genera scrap — solo compacta
    y reporta unidades buenas finales para inventario).

Catálogos fijos:
- 8 máquinas (2 líneas paralelas con la secuencia IMP→TUB→FON→EMP)
- 3 turnos (06:00-14:00, 14:00-22:00, 22:00-06:00)
- 5 productos típicos (sacos de cemento, harina, fertilizante, cal)

Volumetría aproximada:
- ~20 usuarios · ~800 órdenes (con 4 ops cada una = 3200 operaciones)
- ~10000-15000 eventos · ~4300 OEE diarios · materiales y calidad
- ~500 predicciones recientes

Ejecución (dentro del contenedor backend):
    docker compose exec backend python -m scripts.seed
    docker compose exec backend python -m scripts.seed --reset
"""

from __future__ import annotations

import argparse
import logging
import random
from datetime import date, datetime, time, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.auth_service import hash_password
from app.models import (
    EventType,
    Machine,
    MachineStatus,
    MachineType,
    Material,
    MLPrediction,
    OEERecord,
    OperationStatus,
    OrderOperation,
    OrderPriority,
    OrderStatus,
    ProductionEvent,
    ProductionOrder,
    QualityRecord,
    ScrapReason,
    Shift,
    ShiftName,
    User,
    UserRole,
)


# -----------------------------------------------------------------------------
# Configuración del seed
# -----------------------------------------------------------------------------
RANDOM_SEED = 42
MONTHS_OF_HISTORY = 6
FUTURE_DAYS = 30        # Órdenes planificadas a futuro (PENDING).
DEFAULT_PASSWORD = "smartsack123"  # Solo para desarrollo. Cambiar en prod.

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)s | seed | %(message)s"
)
log = logging.getLogger("seed")


# -----------------------------------------------------------------------------
# Catálogos de dominio
# -----------------------------------------------------------------------------
MACHINES_CATALOG: List[Tuple[str, str, MachineType, str]] = [
    # (code, name, type, location)
    ("IMP-01", "Impresora 1", MachineType.IMPRESORA, "Línea A"),
    ("TUB-01", "Tubuladora 1", MachineType.TUBULADORA, "Línea A"),
    ("FON-01", "Fondadora 1", MachineType.FONDADORA, "Línea A"),
    ("EMP-01", "Empacadora 1", MachineType.EMPACADORA, "Línea A"),
    ("IMP-02", "Impresora 2", MachineType.IMPRESORA, "Línea B"),
    ("TUB-02", "Tubuladora 2", MachineType.TUBULADORA, "Línea B"),
    ("FON-02", "Fondadora 2", MachineType.FONDADORA, "Línea B"),
    ("EMP-02", "Empacadora 2", MachineType.EMPACADORA, "Línea B"),
]

# Ruta canónica de fabricación. El sequence empieza en 1 (IMP) y termina
# en 4 (EMP). Si en el futuro un producto tuviera ruta especial (ej.
# saltarse impresión), bastaría con materializar otra ruta aquí.
ROUTE: List[MachineType] = [
    MachineType.IMPRESORA,   # 1 — imprime el papel/tubo
    MachineType.TUBULADORA,  # 2 — forma el tubo
    MachineType.FONDADORA,   # 3 — cierra el fondo
    MachineType.EMPACADORA,  # 4 — compacta y reporta unidades buenas
]

SHIFTS_CATALOG: List[Tuple[ShiftName, time, time]] = [
    (ShiftName.TURNO_1, time(6, 0), time(14, 0)),
    (ShiftName.TURNO_2, time(14, 0), time(22, 0)),
    (ShiftName.TURNO_3, time(22, 0), time(6, 0)),
]

# Catálogo de productos. `unit_weight_kg` es el peso de UN saco vacío
# (papel + tinta), permite estimar cuánto papel pesa el desperdicio.
PRODUCTS_CATALOG: List[Dict] = [
    {
        "type": "Saco cemento 50kg",
        "description": "Saco kraft multipliego para cemento gris, 50 kg.",
        "unit_weight_kg": 0.110,
        "materials": [("Papel kraft 80g", "kg"), ("Tinta gris", "kg"), ("Hilo cosido", "m")],
    },
    {
        "type": "Saco cemento 25kg",
        "description": "Saco kraft multipliego para cemento gris, 25 kg.",
        "unit_weight_kg": 0.075,
        "materials": [("Papel kraft 70g", "kg"), ("Tinta gris", "kg"), ("Hilo cosido", "m")],
    },
    {
        "type": "Saco harina 50kg",
        "description": "Saco multipliego para harina de trigo industrial, 50 kg.",
        "unit_weight_kg": 0.105,
        "materials": [("Papel kraft blanco 90g", "kg"), ("Tinta azul", "kg")],
    },
    {
        "type": "Saco fertilizante 25kg",
        "description": "Saco con barrera laminada para fertilizantes granulados, 25 kg.",
        "unit_weight_kg": 0.085,
        "materials": [
            ("Papel kraft 75g", "kg"),
            ("Lámina BOPP", "kg"),
            ("Tinta verde", "kg"),
        ],
    },
    {
        "type": "Saco cal 25kg",
        "description": "Saco multipliego para cal viva en polvo, 25 kg.",
        "unit_weight_kg": 0.080,
        "materials": [("Papel kraft 75g", "kg"), ("Tinta blanca", "kg"), ("Hilo cosido", "m")],
    },
]

# Tasa nominal de producción (sacos/hora) por tipo de máquina.
NOMINAL_RATE_PER_HOUR: Dict[MachineType, int] = {
    MachineType.IMPRESORA: 2400,
    MachineType.TUBULADORA: 1800,
    MachineType.FONDADORA: 1500,
    MachineType.EMPACADORA: 3000,
}

# Yield esperado por máquina (out/in). El complemento es desperdicio en
# unidades; al multiplicar por unit_weight_kg se obtiene scrap_kg.
NOMINAL_YIELD: Dict[MachineType, Tuple[float, float]] = {
    # (mínimo, máximo) — tasa de buenos sobre entrada
    MachineType.IMPRESORA:  (0.95, 0.99),  # poco scrap (defectos de tinta)
    MachineType.TUBULADORA: (0.93, 0.98),  # tubos malos por tensión/pegado
    MachineType.FONDADORA:  (0.94, 0.99),  # fondos defectuosos
    MachineType.EMPACADORA: (1.00, 1.00),  # no genera scrap
}


# -----------------------------------------------------------------------------
# Utilidades
# -----------------------------------------------------------------------------
HASHED_DEFAULT_PASSWORD = hash_password(DEFAULT_PASSWORD)


def now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


def determine_shift(start_dt: datetime) -> ShiftName:
    hour = start_dt.hour
    if 6 <= hour < 14:
        return ShiftName.TURNO_1
    if 14 <= hour < 22:
        return ShiftName.TURNO_2
    return ShiftName.TURNO_3


def reset_database(db: Session) -> None:
    """Vacía todas las tablas (manteniendo la estructura) en el orden seguro."""
    log.info("Eliminando datos existentes...")
    for model in (
        MLPrediction,
        OEERecord,
        QualityRecord,
        Material,
        ProductionEvent,
        OrderOperation,
    ):
        db.execute(delete(model))
    # Romper el ciclo machines.current_order_id → production_orders.id antes
    # de borrar órdenes.
    db.execute(Machine.__table__.update().values(current_order_id=None))
    db.execute(delete(ProductionOrder))
    db.execute(delete(User))
    db.execute(delete(Machine))
    db.execute(delete(Shift))
    db.commit()


# -----------------------------------------------------------------------------
# Pasos de seeding
# -----------------------------------------------------------------------------
def seed_shifts(db: Session) -> Dict[ShiftName, Shift]:
    log.info("Creando turnos...")
    shifts: Dict[ShiftName, Shift] = {}
    for name, start, end in SHIFTS_CATALOG:
        s = Shift(name=name, start_time=start, end_time=end)
        db.add(s)
        shifts[name] = s
    db.commit()
    return shifts


def seed_machines(db: Session) -> List[Machine]:
    log.info("Creando máquinas...")
    machines: List[Machine] = []
    for code, name, mtype, location in MACHINES_CATALOG:
        m = Machine(
            code=code, name=name, type=mtype, location=location, status=MachineStatus.IDLE
        )
        db.add(m)
        machines.append(m)
    db.commit()
    return machines


def seed_users(db: Session, machines: List[Machine]) -> List[User]:
    log.info("Creando usuarios (admin, supervisores, operarios)...")
    users: List[User] = [
        User(
            username="admin",
            full_name="Administrador del sistema",
            password_hash=HASHED_DEFAULT_PASSWORD,
            role=UserRole.ADMIN,
        ),
        User(
            username="supervisor1",
            full_name="Carmen López — Supervisora línea A",
            password_hash=HASHED_DEFAULT_PASSWORD,
            role=UserRole.SUPERVISOR,
        ),
        User(
            username="supervisor2",
            full_name="Andrés Rojas — Supervisor línea B",
            password_hash=HASHED_DEFAULT_PASSWORD,
            role=UserRole.SUPERVISOR,
        ),
        User(
            username="supervisor3",
            full_name="Diana Pérez — Supervisora turno noche",
            password_hash=HASHED_DEFAULT_PASSWORD,
            role=UserRole.SUPERVISOR,
        ),
    ]

    operator_first_names = [
        "Juan", "María", "Pedro", "Laura", "Carlos", "Sofía",
        "Luis", "Andrea", "Felipe", "Camila", "Ricardo", "Paula",
        "Javier", "Tatiana", "Manuel", "Valentina",
    ]
    # 2 operarios por máquina (cubre 2 de los 3 turnos cómodamente).
    for i, machine in enumerate(machines):
        for slot in range(2):
            idx = i * 2 + slot
            users.append(
                User(
                    username=f"op_{machine.code.lower()}_{slot + 1}",
                    full_name=(
                        f"{operator_first_names[idx % len(operator_first_names)]} "
                        f"— Operario {machine.name}"
                    ),
                    password_hash=HASHED_DEFAULT_PASSWORD,
                    role=UserRole.OPERATOR,
                    machine_id=machine.id,
                )
            )
    db.add_all(users)
    db.commit()
    return users


def _pick_scrap_reason() -> ScrapReason:
    """Distribución típica de razones de desperdicio."""
    return random.choices(
        [
            ScrapReason.QUALITY_DEFECT,
            ScrapReason.SETUP_LOSS,
            ScrapReason.MATERIAL_BREAK,
            ScrapReason.OTHER,
        ],
        weights=[55, 25, 15, 5],
    )[0]


def seed_orders_and_history(
    db: Session, machines: List[Machine], operators: List[User]
) -> None:
    """
    Genera 6 meses de órdenes con su ruta de 4 operaciones (IMP→TUB→FON→EMP),
    eventos por operación, scrap por máquina, calidad y materiales.

    Estrategia: para cada (línea A/B, día, turno) hay un ~75% de probabilidad
    de tener una orden. La cantidad y el rendimiento se aleatorizan dentro
    de rangos realistas y producen los registros derivados encadenados.
    """
    log.info("Generando órdenes con ruta IMP→TUB→FON→EMP...")
    now = now_utc()
    start_date = (now - timedelta(days=30 * MONTHS_OF_HISTORY)).date()
    end_date = now.date() + timedelta(days=FUTURE_DAYS)
    total_days = (end_date - start_date).days

    # Mapear máquinas por (línea, tipo) — el seed itera líneas A y B.
    by_line_type: Dict[Tuple[str, MachineType], Machine] = {}
    for m in machines:
        line = "A" if m.code.endswith("01") else "B"
        by_line_type[(line, m.type)] = m

    operators_by_machine: Dict[int, List[User]] = {}
    for op in operators:
        if op.machine_id is not None:
            operators_by_machine.setdefault(op.machine_id, []).append(op)

    orders: List[ProductionOrder] = []
    operations: List[OrderOperation] = []
    events: List[ProductionEvent] = []
    qualities: List[QualityRecord] = []
    materials: List[Material] = []

    order_counter = 1
    for day_offset in range(total_days):
        current_date = start_date + timedelta(days=day_offset)
        for line in ("A", "B"):
            for shift_name, shift_start, _shift_end in SHIFTS_CATALOG:
                if random.random() > 0.75:
                    continue

                planned_start = datetime.combine(
                    current_date, shift_start, tzinfo=timezone.utc
                )
                shift_hours = 8
                planned_end = planned_start + timedelta(hours=shift_hours)

                product = random.choice(PRODUCTS_CATALOG)
                qty_ordered = random.choice(
                    [5_000, 8_000, 10_000, 15_000, 20_000, 30_000, 50_000]
                )
                priority = random.choices(
                    [OrderPriority.LOW, OrderPriority.NORMAL, OrderPriority.HIGH, OrderPriority.URGENT],
                    weights=[10, 70, 15, 5],
                )[0]

                # Status de la orden cabecera según ubicación temporal.
                if planned_end < now:
                    order_status = random.choices(
                        [OrderStatus.COMPLETED, OrderStatus.DELAYED],
                        weights=[85, 15],
                    )[0]
                elif planned_start <= now <= planned_end:
                    order_status = OrderStatus.IN_PROGRESS
                else:
                    order_status = OrderStatus.PENDING

                order = ProductionOrder(
                    order_number=f"OP-{current_date.year}-{order_counter:06d}",
                    product_type=product["type"],
                    product_description=product["description"],
                    quantity_ordered=qty_ordered,
                    quantity_produced=0,
                    scrap_total_kg=0.0,
                    unit_weight_kg=product["unit_weight_kg"],
                    machine_id=None,  # se setea cuando hay operación running
                    status=order_status,
                    priority=priority,
                    planned_start=planned_start,
                    planned_end=planned_end,
                )
                orders.append(order)
                order_counter += 1

                # ---- Crear las 4 operaciones de la ruta ----
                # Distribuimos el shift en 4 sub-ventanas (una por operación).
                op_duration = timedelta(hours=shift_hours / len(ROUTE))

                # Para órdenes históricas (COMPLETED/DELAYED), simulamos toda
                # la cadena con yields realistas y scrap asociado.
                # Para IN_PROGRESS, alguna operación está corriendo y las
                # siguientes pendientes.
                # Para PENDING, todas las operaciones quedan pendientes
                # (la primera lista para iniciar).

                # Producción simulada por etapa (input → output). La cantidad
                # que entra a IMP es la pedida; cada etapa pierde un % por scrap.
                stage_in = qty_ordered
                op_models_for_order: List[OrderOperation] = []
                for seq, mtype in enumerate(ROUTE, start=1):
                    machine = by_line_type[(line, mtype)]
                    op_planned_start = planned_start + op_duration * (seq - 1)
                    op_planned_end = op_planned_start + op_duration

                    # Estado de la operación según el estado de la orden
                    # cabecera y la posición de la operación en la ruta.
                    op_status: OperationStatus
                    if order_status in (OrderStatus.COMPLETED, OrderStatus.DELAYED):
                        op_status = OperationStatus.COMPLETED
                    elif order_status == OrderStatus.IN_PROGRESS:
                        # Aleatoria: algunas operaciones ya completadas, la
                        # actual en curso, las siguientes pendientes/listas.
                        # Calculamos por progreso temporal proporcional.
                        op_progress_ratio = (now - op_planned_start) / op_duration
                        if op_progress_ratio >= 1.0:
                            op_status = OperationStatus.COMPLETED
                        elif op_progress_ratio >= 0.0:
                            op_status = OperationStatus.IN_PROGRESS
                        elif seq == 1 or (
                            op_models_for_order
                            and op_models_for_order[-1].status == OperationStatus.COMPLETED
                        ):
                            op_status = OperationStatus.READY
                        else:
                            op_status = OperationStatus.PENDING
                    else:  # PENDING (futura)
                        op_status = (
                            OperationStatus.READY if seq == 1 else OperationStatus.PENDING
                        )

                    # Yield y scrap por operación
                    if op_status == OperationStatus.COMPLETED:
                        ymin, ymax = NOMINAL_YIELD[mtype]
                        yield_ratio = random.uniform(ymin, ymax)
                        qty_in = stage_in
                        qty_out = int(qty_in * yield_ratio)
                        scrap_units = qty_in - qty_out
                        if mtype == MachineType.EMPACADORA:
                            # EMP no genera scrap; lo que entra es lo que sale.
                            qty_out = qty_in
                            scrap_units = 0
                            scrap_kg = 0.0
                            scrap_reason = None
                        else:
                            scrap_kg = round(
                                scrap_units * product["unit_weight_kg"], 3
                            )
                            scrap_reason = (
                                _pick_scrap_reason() if scrap_units > 0 else None
                            )
                        actual_start = op_planned_start + timedelta(
                            minutes=random.randint(-5, 15)
                        )
                        actual_end = actual_start + op_duration * random.uniform(
                            0.9, 1.15
                        )
                    elif op_status == OperationStatus.IN_PROGRESS:
                        ymin, ymax = NOMINAL_YIELD[mtype]
                        yield_ratio = random.uniform(ymin, ymax)
                        qty_in = stage_in
                        # Avance proporcional al tiempo transcurrido
                        progress = min(1.0, max(0.05, (now - op_planned_start) / op_duration))
                        qty_out = int(qty_in * yield_ratio * progress)
                        scrap_units = int(qty_in * (1 - yield_ratio) * progress)
                        if mtype == MachineType.EMPACADORA:
                            qty_out = int(qty_in * progress)
                            scrap_units = 0
                            scrap_kg = 0.0
                            scrap_reason = None
                        else:
                            scrap_kg = round(
                                scrap_units * product["unit_weight_kg"], 3
                            )
                            scrap_reason = (
                                _pick_scrap_reason() if scrap_units > 0 else None
                            )
                        actual_start = op_planned_start
                        actual_end = None
                    else:
                        # READY o PENDING: aún no se ha trabajado
                        qty_in = stage_in if op_status == OperationStatus.READY else 0
                        qty_out = 0
                        scrap_kg = 0.0
                        scrap_reason = None
                        actual_start = None
                        actual_end = None

                    ops = operators_by_machine.get(machine.id, [])
                    operator = random.choice(ops) if ops else None
                    shift = (
                        determine_shift(actual_start) if actual_start else None
                    )

                    operation = OrderOperation(
                        order=order,  # SQLAlchemy asocia y resuelve PK al flush
                        machine_id=machine.id,
                        sequence=seq,
                        status=op_status,
                        quantity_in=qty_in,
                        quantity_out=qty_out,
                        scrap_kg=scrap_kg,
                        scrap_reason=scrap_reason,
                        planned_start=op_planned_start,
                        planned_end=op_planned_end,
                        actual_start=actual_start,
                        actual_end=actual_end,
                        operator_id=operator.id if operator else None,
                        shift=shift,
                    )
                    operations.append(operation)
                    op_models_for_order.append(operation)

                    # La salida de esta operación es la entrada de la siguiente.
                    if op_status in (OperationStatus.COMPLETED, OperationStatus.IN_PROGRESS):
                        stage_in = qty_out
                    elif op_status == OperationStatus.READY:
                        stage_in = qty_in
                    else:
                        stage_in = 0

                    # Eventos por operación COMPLETED o IN_PROGRESS
                    if op_status in (OperationStatus.COMPLETED, OperationStatus.IN_PROGRESS):
                        events.append(
                            ProductionEvent(
                                machine_id=machine.id,
                                order_id=None,  # se rellena tras flush
                                operation=operation,
                                user_id=operator.id if operator else None,
                                event_type=EventType.START,
                                description=f"Inicio op{seq} ({machine.code})",
                                timestamp=actual_start,
                            )
                        )
                        # Reporte de producción cuando hay output significativo
                        if qty_out > 0:
                            events.append(
                                ProductionEvent(
                                    machine_id=machine.id,
                                    order_id=None,
                                    operation=operation,
                                    user_id=operator.id if operator else None,
                                    event_type=EventType.PRODUCTION_UPDATE,
                                    description=f"Reporte de producción op{seq}",
                                    timestamp=(actual_end or now)
                                    - timedelta(minutes=random.randint(5, 30)),
                                    quantity=qty_out,
                                    scrap_kg=scrap_kg if mtype != MachineType.EMPACADORA else None,
                                    scrap_reason=scrap_reason,
                                )
                            )
                        # Pausa eventual
                        if random.random() < 0.20:
                            events.append(
                                ProductionEvent(
                                    machine_id=machine.id,
                                    order_id=None,
                                    operation=operation,
                                    user_id=operator.id if operator else None,
                                    event_type=random.choice(
                                        [EventType.PAUSE, EventType.STOP]
                                    ),
                                    description=random.choice(
                                        [
                                            "Cambio de bobina",
                                            "Limpieza menor",
                                            "Atasco breve",
                                            "Espera de material",
                                        ]
                                    ),
                                    timestamp=actual_start
                                    + op_duration * random.uniform(0.2, 0.7),
                                )
                            )
                        # Incidencia ocasional (más frecuente si DELAYED)
                        incident_prob = (
                            0.25 if order_status == OrderStatus.DELAYED else 0.05
                        )
                        if random.random() < incident_prob:
                            events.append(
                                ProductionEvent(
                                    machine_id=machine.id,
                                    order_id=None,
                                    operation=operation,
                                    user_id=operator.id if operator else None,
                                    event_type=EventType.INCIDENT,
                                    description=random.choice(
                                        [
                                            "Falla en sensor de tensión",
                                            "Calidad fuera de rango",
                                            "Bobina defectuosa",
                                            "Paro eléctrico",
                                        ]
                                    ),
                                    timestamp=actual_start + op_duration * 0.5,
                                )
                            )
                        if op_status == OperationStatus.COMPLETED and actual_end:
                            events.append(
                                ProductionEvent(
                                    machine_id=machine.id,
                                    order_id=None,
                                    operation=operation,
                                    user_id=operator.id if operator else None,
                                    event_type=EventType.END,
                                    description=f"Fin op{seq}",
                                    timestamp=actual_end,
                                )
                            )

                # ---- Actualizar agregados de la orden cabecera ----
                last_op = op_models_for_order[-1]  # EMP
                if last_op.status == OperationStatus.COMPLETED:
                    order.quantity_produced = last_op.quantity_out
                elif last_op.status == OperationStatus.IN_PROGRESS:
                    order.quantity_produced = last_op.quantity_out
                # Suma scrap_kg de IMP+TUB+FON
                order.scrap_total_kg = round(
                    sum(op.scrap_kg for op in op_models_for_order), 3
                )
                # actual_start/end de la orden = primera y última operación
                first_started = next(
                    (op.actual_start for op in op_models_for_order if op.actual_start),
                    None,
                )
                if first_started:
                    order.actual_start = first_started
                if last_op.status == OperationStatus.COMPLETED:
                    order.actual_end = last_op.actual_end
                # Máquina actual = donde hay operación IN_PROGRESS
                running_op = next(
                    (op for op in op_models_for_order if op.status == OperationStatus.IN_PROGRESS),
                    None,
                )
                if running_op:
                    order.machine_id = running_op.machine_id

                # ---- Calidad (solo si hubo producción real) ----
                if order.quantity_produced > 0:
                    quality_ratio = random.uniform(0.96, 0.995)
                    good = int(order.quantity_produced * quality_ratio)
                    qualities.append(
                        QualityRecord(
                            order_id=None,  # se rellena tras flush
                            order=order,
                            total_produced=order.quantity_produced,
                            good_units=good,
                            defective_units=order.quantity_produced - good,
                            timestamp=(order.actual_end or now),
                        )
                    )

                # ---- Materiales ----
                for mat_name, unit in product["materials"]:
                    planned_qty = round(qty_ordered * random.uniform(0.05, 0.15), 2)
                    used_factor = (
                        random.uniform(0.95, 1.08)
                        if order_status != OrderStatus.PENDING
                        else 0.0
                    )
                    materials.append(
                        Material(
                            order=order,
                            material_type=mat_name,
                            unit=unit,
                            quantity_planned=planned_qty,
                            quantity_used=round(planned_qty * used_factor, 2),
                        )
                    )

    log.info("Insertando %d órdenes...", len(orders))
    db.add_all(orders)
    db.flush()

    log.info("Insertando %d operaciones, %d eventos, %d calidad, %d materiales...",
             len(operations), len(events), len(qualities), len(materials))
    db.add_all(operations)
    db.flush()

    # Rellenar order_id en eventos y qualities (relaciones se resolvieron en flush)
    for e in events:
        if e.operation is not None:
            e.order_id = e.operation.order_id
    db.add_all(events)
    db.add_all(qualities)
    db.add_all(materials)
    db.commit()

    # ---- Asignar current_order y status a las máquinas ----
    log.info("Asignando estado actual a las máquinas según operaciones IN_PROGRESS...")
    in_progress_ops = (
        db.execute(
            select(OrderOperation).where(
                OrderOperation.status == OperationStatus.IN_PROGRESS
            )
        )
        .scalars()
        .all()
    )
    by_machine: Dict[int, OrderOperation] = {}
    for op in in_progress_ops:
        by_machine.setdefault(op.machine_id, op)
    for machine in machines:
        if machine.id in by_machine:
            machine.current_order_id = by_machine[machine.id].order_id
            machine.status = MachineStatus.RUNNING
        else:
            machine.status = random.choices(
                [MachineStatus.IDLE, MachineStatus.STOPPED, MachineStatus.MAINTENANCE],
                weights=[70, 20, 10],
            )[0]
    db.commit()


def seed_oee(db: Session, machines: List[Machine], shifts: Dict[ShiftName, Shift]) -> None:
    """Genera un OEERecord por máquina, turno y día de los últimos 6 meses."""
    log.info("Generando registros OEE diarios...")
    today = date.today()
    start_date = today - timedelta(days=30 * MONTHS_OF_HISTORY)
    records: List[OEERecord] = []

    for day_offset in range((today - start_date).days + 1):
        current_date = start_date + timedelta(days=day_offset)
        for machine in machines:
            for shift_obj in shifts.values():
                availability = round(random.uniform(0.78, 0.96), 4)
                performance = round(random.uniform(0.74, 0.93), 4)
                quality = round(random.uniform(0.94, 0.995), 4)
                oee = round(availability * performance * quality, 4)
                records.append(
                    OEERecord(
                        machine_id=machine.id,
                        shift_id=shift_obj.id,
                        date=current_date,
                        availability=availability,
                        performance=performance,
                        quality=quality,
                        oee_value=oee,
                    )
                )

    log.info("Insertando %d registros de OEE...", len(records))
    db.bulk_save_objects(records)
    db.commit()


def seed_predictions(db: Session) -> None:
    """Crea predicciones ML simuladas para órdenes de los últimos 30 días."""
    log.info("Generando predicciones ML para órdenes recientes...")
    threshold = now_utc() - timedelta(days=30)

    recent_orders = (
        db.execute(
            select(ProductionOrder).where(ProductionOrder.planned_start >= threshold)
        )
        .scalars()
        .all()
    )

    predictions: List[MLPrediction] = []
    for order in recent_orders:
        if random.random() > 0.5:
            continue
        if order.status == OrderStatus.DELAYED:
            prob = round(random.uniform(0.6, 0.95), 3)
            hours = round(random.uniform(2.0, 8.0), 2)
        elif order.status == OrderStatus.COMPLETED:
            prob = round(random.uniform(0.05, 0.35), 3)
            hours = round(random.uniform(0.0, 1.5), 2)
        else:
            prob = round(random.uniform(0.1, 0.7), 3)
            hours = round(random.uniform(0.0, 4.0), 2)

        predictions.append(
            MLPrediction(
                order_id=order.id,
                delay_probability=prob,
                predicted_delay_hours=hours,
                features_json={
                    "priority": order.priority.value,
                    "quantity_ordered": order.quantity_ordered,
                    "machine_id": order.machine_id,
                    "product_type": order.product_type,
                },
                model_version="xgboost_v0.1.0",
                created_at=order.planned_start - timedelta(hours=2),
            )
        )

    log.info("Insertando %d predicciones ML...", len(predictions))
    db.bulk_save_objects(predictions)
    db.commit()


# -----------------------------------------------------------------------------
# Entrada principal
# -----------------------------------------------------------------------------
def main(reset: bool) -> None:
    random.seed(RANDOM_SEED)
    log.info("Iniciando seed de SmartSack (reset=%s)", reset)

    with SessionLocal() as db:
        if reset:
            reset_database(db)

        if not reset and db.scalar(select(Machine).limit(1)) is not None:
            log.warning("Ya existen datos. Usar --reset para reiniciar. Abortando.")
            return

        shifts = seed_shifts(db)
        machines = seed_machines(db)
        users = seed_users(db, machines)
        seed_orders_and_history(db, machines, users)
        seed_oee(db, machines, shifts)
        seed_predictions(db)

        log.info("Seed completado.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed de datos de SmartSack")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Vacía las tablas antes de insertar datos (úsalo en re-ejecuciones).",
    )
    args = parser.parse_args()
    main(reset=args.reset)
