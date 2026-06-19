"""
Servicio ETL — parser e ingestión de CSVs del ERP (SAP).

Cuatro tipos de archivo soportados (`ETLLoadKind`):

  · production_orders : crea/actualiza órdenes de producción.
  · confirmations     : actualiza qty_produced + actual_start/end de órdenes existentes.
  · materials         : inserta líneas de consumo de material por orden (idempotente
                         por (order_number, material_code)).
  · shipments         : registra despachos (eventos tipo END en la orden y log de envío).

Estrategia de procesamiento:
  1. Leer el CSV con Pandas y validar columnas requeridas.
  2. Iterar fila por fila: validar tipos, capturar errores SIN abortar el batch.
  3. Aplicar upsert/update con SQLAlchemy. Las filas problemáticas se descartan
     y quedan registradas en `error_log` del ETLLoad.
  4. Resumen final → ETLLoadStatus (success / partial / failed) y contadores.

El modelo ProductionEvent se usa para registrar shipments como evento END
con prefijo "[ETL]" en la descripción (auditable + visible en el ticker).
"""

from __future__ import annotations

import io
import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ETLLoad,
    ETLLoadKind,
    ETLLoadStatus,
    EventType,
    Machine,
    MachineType,
    Material,
    OperationStatus,
    OrderOperation,
    OrderPriority,
    OrderStatus,
    ProductionEvent,
    ProductionOrder,
    ScrapReason,
)


logger = logging.getLogger("smartsack.etl")

# Hasta 50 errores por fila se persisten en JSON (suficiente para diagnóstico).
MAX_ROW_ERRORS_PERSISTED = 50

# Columnas requeridas por cada tipo de CSV.
REQUIRED_COLUMNS: Dict[ETLLoadKind, List[str]] = {
    ETLLoadKind.PRODUCTION_ORDERS: [
        "order_number",
        "product_type",
        "quantity_ordered",
        "machine_code",
        "planned_start",
        "planned_end",
    ],
    ETLLoadKind.CONFIRMATIONS: [
        "order_number",
        "machine_code",
        "quantity_produced",
        "actual_start",
    ],
    ETLLoadKind.MATERIALS: [
        "order_number",
        "material_code",
        "material_name",
        "quantity_planned",
    ],
    ETLLoadKind.SHIPMENTS: [
        "order_number",
        "shipped_at",
        "destination",
        "quantity_shipped",
    ],
}


# -----------------------------------------------------------------------------
# Excepciones internas
# -----------------------------------------------------------------------------
class ETLValidationError(Exception):
    """Error de validación a nivel de fila (no aborta el batch)."""


# -----------------------------------------------------------------------------
# Utilidades de parseo
# -----------------------------------------------------------------------------
def _parse_dt(value: Any, field: str) -> datetime:
    """Convierte un valor a datetime tz-aware (UTC). Lanza ETLValidationError."""
    if value is None or (isinstance(value, float) and pd.isna(value)) or value == "":
        raise ETLValidationError(f"{field}: valor vacío")
    try:
        ts = pd.to_datetime(value, errors="raise")
    except Exception as exc:
        raise ETLValidationError(f"{field}: '{value}' no es una fecha válida") from exc
    py_dt = ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts
    if py_dt.tzinfo is None:
        py_dt = py_dt.replace(tzinfo=timezone.utc)
    return py_dt


def _parse_int(value: Any, field: str, *, min_value: Optional[int] = None) -> int:
    if value is None or (isinstance(value, float) and pd.isna(value)) or value == "":
        raise ETLValidationError(f"{field}: valor vacío")
    try:
        n = int(float(value))
    except (TypeError, ValueError) as exc:
        raise ETLValidationError(f"{field}: '{value}' no es entero") from exc
    if min_value is not None and n < min_value:
        raise ETLValidationError(f"{field}: {n} < mínimo {min_value}")
    return n


def _parse_float(value: Any, field: str, *, min_value: Optional[float] = None) -> float:
    if value is None or (isinstance(value, float) and pd.isna(value)) or value == "":
        raise ETLValidationError(f"{field}: valor vacío")
    try:
        f = float(value)
    except (TypeError, ValueError) as exc:
        raise ETLValidationError(f"{field}: '{value}' no es numérico") from exc
    if min_value is not None and f < min_value:
        raise ETLValidationError(f"{field}: {f} < mínimo {min_value}")
    return f


def _parse_str(value: Any, field: str, *, max_length: Optional[int] = None) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        raise ETLValidationError(f"{field}: valor vacío")
    s = str(value).strip()
    if not s:
        raise ETLValidationError(f"{field}: valor vacío")
    if max_length is not None and len(s) > max_length:
        raise ETLValidationError(f"{field}: longitud {len(s)} > máximo {max_length}")
    return s


def _parse_optional_str(value: Any) -> Optional[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = str(value).strip()
    return s or None


def _machine_id_for(db: Session, code: str, cache: Dict[str, int]) -> int:
    """Devuelve el id de la máquina con `code`, cacheando entre filas."""
    if code in cache:
        return cache[code]
    machine = db.scalar(select(Machine).where(Machine.code == code))
    if machine is None:
        raise ETLValidationError(f"machine_code: '{code}' no existe")
    cache[code] = machine.id
    return machine.id


def _order_for(db: Session, number: str, cache: Dict[str, ProductionOrder]) -> ProductionOrder:
    """Devuelve la orden con `order_number`, cacheando entre filas."""
    if number in cache:
        return cache[number]
    order = db.scalar(select(ProductionOrder).where(ProductionOrder.order_number == number))
    if order is None:
        raise ETLValidationError(f"order_number: '{number}' no existe")
    cache[number] = order
    return order


# Ruta de la planta: las 4 etapas en orden secuencial.
_ROUTE: List[MachineType] = [
    MachineType.IMPRESORA,
    MachineType.TUBULADORA,
    MachineType.FONDADORA,
    MachineType.EMPACADORA,
]


def _resolve_standard_line(
    db: Session, anchor_machine: Machine
) -> Optional[Dict[MachineType, Machine]]:
    """
    Si el anchor pertenece a una línea estándar completa (sufijo -01 o -02
    con las 4 etapas IMP/TUB/FON/EMP), devuelve el mapa tipo→máquina.
    En cualquier otro caso devuelve None y el caller debe usar fallback.
    """
    suffix = anchor_machine.code.split("-")[-1] if "-" in anchor_machine.code else ""
    if suffix not in ("01", "02"):
        return None
    line_machines = list(
        db.scalars(select(Machine).where(Machine.code.like(f"%-{suffix}")))
    )
    by_type: Dict[MachineType, Machine] = {m.type: m for m in line_machines}
    if any(t not in by_type for t in _ROUTE):
        return None
    return by_type


def create_operations_for_order(
    db: Session, order: ProductionOrder, anchor_machine: Machine
) -> int:
    """
    Crea operaciones para una orden recién insertada y devuelve cuántas creó.

    - Si la `anchor_machine` pertenece a una línea estándar completa
      (`-01`/`-02` con las 4 etapas IMP/TUB/FON/EMP), crea las 4 operaciones
      encadenadas con la primera READY y el resto PENDING.
    - En otro caso (máquina suelta, ej. una IMP-03 creada por el admin para
      un piloto), crea UNA sola operación sobre el propio anchor con status
      READY, así el operario asignado a esa máquina la ve disponible en su
      cola al instante.
    """
    line = _resolve_standard_line(db, anchor_machine)

    if line is not None:
        span = order.planned_end - order.planned_start
        sub = span / len(_ROUTE)
        for seq, mtype in enumerate(_ROUTE, start=1):
            machine = line[mtype]
            op_start = order.planned_start + sub * (seq - 1)
            op_end = order.planned_start + sub * seq
            db.add(
                OrderOperation(
                    order=order,
                    machine_id=machine.id,
                    sequence=seq,
                    status=OperationStatus.READY if seq == 1 else OperationStatus.PENDING,
                    quantity_in=order.quantity_ordered if seq == 1 else 0,
                    quantity_out=0,
                    scrap_kg=0.0,
                    planned_start=op_start,
                    planned_end=op_end,
                )
            )
        return len(_ROUTE)

    # Fallback: máquina aislada → una sola operación lista para tomar.
    db.add(
        OrderOperation(
            order=order,
            machine_id=anchor_machine.id,
            sequence=1,
            status=OperationStatus.READY,
            quantity_in=order.quantity_ordered,
            quantity_out=0,
            scrap_kg=0.0,
            planned_start=order.planned_start,
            planned_end=order.planned_end,
        )
    )
    return 1


def _create_operations_for_order(
    db: Session, order: ProductionOrder, anchor_machine: Machine
) -> None:
    """Alias del helper público — usado por el ETL existente sin tocar más sitios."""
    create_operations_for_order(db, order, anchor_machine)


# -----------------------------------------------------------------------------
# Lectura del CSV → DataFrame con validación de columnas
# -----------------------------------------------------------------------------
def _read_csv(content: bytes, kind: ETLLoadKind) -> pd.DataFrame:
    """
    Carga el CSV en un DataFrame validando columnas requeridas.

    Lanza ValueError (capturado por el caller como error global) si el
    archivo no se puede parsear o falta alguna columna obligatoria.
    """
    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as exc:
        raise ValueError(f"No se pudo leer el CSV: {exc}") from exc
    if df.empty:
        raise ValueError("El CSV está vacío (sin filas)")
    missing = [c for c in REQUIRED_COLUMNS[kind] if c not in df.columns]
    if missing:
        raise ValueError(f"Faltan columnas requeridas: {missing}")
    return df


# -----------------------------------------------------------------------------
# Procesadores por tipo
# -----------------------------------------------------------------------------
def _process_production_orders(
    db: Session, df: pd.DataFrame
) -> Tuple[int, int, int, int, List[Dict[str, Any]]]:
    """
    Crea o actualiza órdenes. Idempotente por order_number.

    Detección de duplicados *intra-archivo*: si una misma `order_number`
    aparece dos veces, la segunda se cuenta como `skipped`.
    """
    inserted = updated = skipped = failed = 0
    errors: List[Dict[str, Any]] = []
    machine_cache: Dict[str, int] = {}
    seen_in_batch: set[str] = set()

    valid_priorities = {p.value for p in OrderPriority}

    for idx, row in df.iterrows():
        row_no = int(idx) + 2  # +2: cabecera (1) + 1-indexed
        try:
            order_number = _parse_str(row.get("order_number"), "order_number", max_length=32)
            if order_number in seen_in_batch:
                skipped += 1
                continue
            seen_in_batch.add(order_number)

            product_type = _parse_str(row.get("product_type"), "product_type", max_length=64)
            quantity = _parse_int(row.get("quantity_ordered"), "quantity_ordered", min_value=1)
            machine_code = _parse_str(row.get("machine_code"), "machine_code", max_length=32)
            anchor_machine = db.scalar(select(Machine).where(Machine.code == machine_code))
            if anchor_machine is None:
                raise ETLValidationError(f"machine_code: '{machine_code}' no existe")
            machine_cache[machine_code] = anchor_machine.id
            machine_id = anchor_machine.id

            planned_start = _parse_dt(row.get("planned_start"), "planned_start")
            planned_end = _parse_dt(row.get("planned_end"), "planned_end")
            if planned_end <= planned_start:
                raise ETLValidationError("planned_end debe ser posterior a planned_start")

            priority_raw = _parse_optional_str(row.get("priority")) or "normal"
            if priority_raw not in valid_priorities:
                raise ETLValidationError(
                    f"priority: '{priority_raw}' inválido (válidos: {sorted(valid_priorities)})"
                )

            description = _parse_optional_str(row.get("product_description"))
            if description and len(description) > 255:
                description = description[:255]

            existing = db.scalar(
                select(ProductionOrder).where(ProductionOrder.order_number == order_number)
            )
            if existing is None:
                new_order = ProductionOrder(
                    order_number=order_number,
                    product_type=product_type,
                    product_description=description,
                    quantity_ordered=quantity,
                    machine_id=machine_id,
                    priority=OrderPriority(priority_raw),
                    planned_start=planned_start,
                    planned_end=planned_end,
                    status=OrderStatus.PENDING,
                )
                db.add(new_order)
                _create_operations_for_order(db, new_order, anchor_machine)
                inserted += 1
            else:
                existing.product_type = product_type
                existing.product_description = description
                existing.quantity_ordered = quantity
                existing.machine_id = machine_id
                existing.priority = OrderPriority(priority_raw)
                existing.planned_start = planned_start
                existing.planned_end = planned_end
                updated += 1
        except ETLValidationError as exc:
            failed += 1
            if len(errors) < MAX_ROW_ERRORS_PERSISTED:
                errors.append(
                    {
                        "row": row_no,
                        "order_number": _parse_optional_str(row.get("order_number")),
                        "error": str(exc),
                    }
                )
        except Exception as exc:  # noqa: BLE001 — captura errores no anticipados.
            logger.exception("ETL row %s falla inesperada", row_no)
            failed += 1
            if len(errors) < MAX_ROW_ERRORS_PERSISTED:
                errors.append({"row": row_no, "error": f"unexpected: {exc!r}"})

    return inserted, updated, skipped, failed, errors


def _upsert_confirmation_event(
    db: Session,
    *,
    order: ProductionOrder,
    machine: Machine,
    operation: OrderOperation,
    quantity_out: int,
    scrap_kg: float,
    scrap_reason: Optional[ScrapReason],
    timestamp: datetime,
) -> None:
    """
    Crea (o actualiza) el evento `production_update` de una confirmación ETL.

    Mantiene a lo sumo UN evento con prefijo "[ETL]" por operación para
    preservar la idempotencia del loader: si el mismo archivo se recarga, el
    evento existente se actualiza en lugar de duplicarse.

    El scrap se guarda como NULL cuando es 0 (coherente con la regla del
    modelo: la empacadora nunca lleva scrap).
    """
    descripcion = f"[ETL][CONF] {machine.code}: {quantity_out:,} u"
    if scrap_kg > 0:
        motivo = scrap_reason.value if scrap_reason is not None else "—"
        descripcion += f", scrap {scrap_kg:g} kg ({motivo})"

    existing = db.scalar(
        select(ProductionEvent)
        .where(ProductionEvent.operation_id == operation.id)
        .where(ProductionEvent.event_type == EventType.PRODUCTION_UPDATE)
        .where(ProductionEvent.description.like("[ETL]%"))
    )

    scrap_value = scrap_kg if scrap_kg > 0 else None
    if existing is None:
        db.add(
            ProductionEvent(
                machine_id=machine.id,
                order_id=order.id,
                operation_id=operation.id,
                user_id=None,  # originado por ETL, sin operario.
                event_type=EventType.PRODUCTION_UPDATE,
                description=descripcion,
                quantity=quantity_out,
                scrap_kg=scrap_value,
                scrap_reason=scrap_reason,
                timestamp=timestamp,
            )
        )
    else:
        existing.machine_id = machine.id
        existing.order_id = order.id
        existing.description = descripcion
        existing.quantity = quantity_out
        existing.scrap_kg = scrap_value
        existing.scrap_reason = scrap_reason
        existing.timestamp = timestamp


def _process_confirmations(
    db: Session, df: pd.DataFrame
) -> Tuple[int, int, int, int, List[Dict[str, Any]]]:
    """
    Procesa confirmaciones de producción a nivel de OPERACIÓN.

    Cada fila representa el estado final de una operación dentro de la ruta
    IMP→TUB→FON→EMP, identificada por la pareja (order_number, machine_code).
    Es declarativo e idempotente: cargar el mismo archivo dos veces deja
    el sistema en el mismo estado.

    Columnas:
      · order_number       (req) — la orden cabecera
      · machine_code       (req) — qué operación dentro de la ruta
      · quantity_produced  (req) — unidades buenas que salieron de la operación
      · actual_start       (req) — timestamp de inicio
      · actual_end         (opt) — si se llenó, la operación queda COMPLETED
                                    y promueve la siguiente a READY
      · scrap_kg           (opt) — desperdicio en kg (0 forzado en EMP)
      · scrap_reason       (opt) — quality_defect / setup_loss / material_break / other

    Reglas:
      - Si la operación estaba PENDING/READY: pasa a IN_PROGRESS al setear actual_start.
      - Si llega actual_end: pasa a COMPLETED, se promueve la siguiente y
        (si era EMP) se actualiza order.quantity_produced + status COMPLETED.
      - EMP no acepta scrap_kg > 0 (se rechaza la fila).
      - Cada confirmación deja una traza `production_update` vinculada a la
        operación (auditable, alimenta OEE/ML). Para no romper la idempotencia
        del loader, se mantiene a lo sumo UN evento "[ETL]" por operación: la
        recarga del mismo archivo actualiza ese evento en vez de duplicarlo.
    """
    inserted = updated = skipped = failed = 0
    errors: List[Dict[str, Any]] = []
    order_cache: Dict[str, ProductionOrder] = {}
    machine_cache: Dict[str, int] = {}
    valid_scrap = {r.value for r in ScrapReason}

    # Cache de objetos Machine completos (necesitamos el .type para validar EMP).
    machines_by_code: Dict[str, Machine] = {}

    for idx, row in df.iterrows():
        row_no = int(idx) + 2
        try:
            order_number = _parse_str(row.get("order_number"), "order_number", max_length=32)
            order = _order_for(db, order_number, order_cache)
            machine_code = _parse_str(row.get("machine_code"), "machine_code", max_length=32)
            if machine_code not in machines_by_code:
                m = db.scalar(select(Machine).where(Machine.code == machine_code))
                if m is None:
                    raise ETLValidationError(f"machine_code: '{machine_code}' no existe")
                machines_by_code[machine_code] = m
                machine_cache[machine_code] = m.id
            machine = machines_by_code[machine_code]

            # Localizar la operación de esa orden en esa máquina
            operation = db.scalar(
                select(OrderOperation)
                .where(OrderOperation.order_id == order.id)
                .where(OrderOperation.machine_id == machine.id)
            )
            if operation is None:
                raise ETLValidationError(
                    f"No existe operación para order={order_number} machine={machine_code}"
                )

            qty_out = _parse_int(
                row.get("quantity_produced"), "quantity_produced", min_value=0
            )
            actual_start = _parse_dt(row.get("actual_start"), "actual_start")

            actual_end_raw = row.get("actual_end") if "actual_end" in row.index else None
            actual_end: Optional[datetime] = None
            if actual_end_raw not in (None, "") and not (
                isinstance(actual_end_raw, float) and pd.isna(actual_end_raw)
            ):
                actual_end = _parse_dt(actual_end_raw, "actual_end")
                if actual_end <= actual_start:
                    raise ETLValidationError("actual_end debe ser posterior a actual_start")

            # Scrap (opcional; obligatorio 0 en EMP)
            scrap_kg = 0.0
            if "scrap_kg" in row.index and row.get("scrap_kg") not in (None, "") and not (
                isinstance(row.get("scrap_kg"), float) and pd.isna(row.get("scrap_kg"))
            ):
                scrap_kg = _parse_float(row.get("scrap_kg"), "scrap_kg", min_value=0.0)
            if machine.type == MachineType.EMPACADORA and scrap_kg > 0:
                raise ETLValidationError(
                    "La empacadora no genera desperdicio: scrap_kg debe ser 0"
                )

            scrap_reason: Optional[ScrapReason] = None
            scrap_reason_raw = _parse_optional_str(row.get("scrap_reason"))
            if scrap_reason_raw is not None:
                if scrap_reason_raw not in valid_scrap:
                    raise ETLValidationError(
                        f"scrap_reason: '{scrap_reason_raw}' inválido "
                        f"(válidos: {sorted(valid_scrap)})"
                    )
                scrap_reason = ScrapReason(scrap_reason_raw)
            if scrap_kg > 0 and scrap_reason is None:
                raise ETLValidationError("scrap_reason es obligatorio cuando scrap_kg > 0")

            # ---- Aplicar el estado declarativo a la operación ----
            operation.quantity_out = qty_out
            operation.scrap_kg = scrap_kg
            if scrap_reason is not None:
                operation.scrap_reason = scrap_reason
            operation.actual_start = actual_start
            if actual_end is not None:
                operation.actual_end = actual_end
                operation.status = OperationStatus.COMPLETED
            elif operation.status in (OperationStatus.PENDING, OperationStatus.READY):
                operation.status = OperationStatus.IN_PROGRESS

            # ---- Cascada: promover siguiente y actualizar orden ----
            if operation.status == OperationStatus.COMPLETED:
                next_op = db.scalar(
                    select(OrderOperation)
                    .where(OrderOperation.order_id == order.id)
                    .where(OrderOperation.sequence == operation.sequence + 1)
                )
                if next_op is not None and next_op.status == OperationStatus.PENDING:
                    next_op.status = OperationStatus.READY
                    next_op.quantity_in = operation.quantity_out

                # Si era EMP (última de la ruta), cerrar la orden
                if next_op is None:
                    order.status = OrderStatus.COMPLETED
                    if order.actual_end is None or (
                        actual_end and actual_end > order.actual_end
                    ):
                        order.actual_end = actual_end
                    if machine.type == MachineType.EMPACADORA:
                        order.quantity_produced = qty_out

            # Recalcular agregados de la orden (scrap_total_kg)
            all_ops = list(
                db.scalars(
                    select(OrderOperation).where(OrderOperation.order_id == order.id)
                )
            )
            order.scrap_total_kg = round(sum(op.scrap_kg for op in all_ops), 3)
            if order.actual_start is None or actual_start < order.actual_start:
                order.actual_start = actual_start
            if order.status == OrderStatus.PENDING:
                order.status = OrderStatus.IN_PROGRESS

            # ---- Traza production_update vinculada a la operación ----
            # Auditable y consumible por OEE/ML. Idempotente: a lo sumo un
            # evento "[ETL]" por operación; recargar el archivo lo actualiza.
            _upsert_confirmation_event(
                db,
                order=order,
                machine=machine,
                operation=operation,
                quantity_out=qty_out,
                scrap_kg=scrap_kg,
                scrap_reason=scrap_reason,
                timestamp=actual_end or actual_start,
            )

            updated += 1
        except ETLValidationError as exc:
            failed += 1
            if len(errors) < MAX_ROW_ERRORS_PERSISTED:
                errors.append(
                    {
                        "row": row_no,
                        "order_number": _parse_optional_str(row.get("order_number")),
                        "machine_code": _parse_optional_str(row.get("machine_code")),
                        "error": str(exc),
                    }
                )
        except Exception as exc:  # noqa: BLE001
            logger.exception("ETL row %s falla inesperada", row_no)
            failed += 1
            if len(errors) < MAX_ROW_ERRORS_PERSISTED:
                errors.append({"row": row_no, "error": f"unexpected: {exc!r}"})

    return inserted, updated, skipped, failed, errors


def _process_materials(
    db: Session, df: pd.DataFrame
) -> Tuple[int, int, int, int, List[Dict[str, Any]]]:
    """
    Inserta o actualiza Material por orden. Idempotente por (order_id, material_type).

    El `material_type` del modelo agrupa código + nombre legible:
        "PAPER-KRAFT-80 · Papel kraft 80g"
    así una segunda carga que renombre el material no inserta duplicados.
    """
    inserted = updated = skipped = failed = 0
    errors: List[Dict[str, Any]] = []
    order_cache: Dict[str, ProductionOrder] = {}
    seen: set[Tuple[int, str]] = set()

    for idx, row in df.iterrows():
        row_no = int(idx) + 2
        try:
            order_number = _parse_str(row.get("order_number"), "order_number", max_length=32)
            order = _order_for(db, order_number, order_cache)
            mat_code = _parse_str(row.get("material_code"), "material_code", max_length=32)
            mat_name = _parse_str(row.get("material_name"), "material_name", max_length=64)
            unit = _parse_optional_str(row.get("unit")) or "kg"
            qty_planned = _parse_float(
                row.get("quantity_planned"), "quantity_planned", min_value=0.0
            )
            qty_used = _parse_float(
                row.get("quantity_used"), "quantity_used", min_value=0.0
            ) if "quantity_used" in row.index and not (
                isinstance(row.get("quantity_used"), float)
                and pd.isna(row.get("quantity_used"))
            ) else 0.0

            material_type_label = f"{mat_code} · {mat_name}"
            key = (order.id, material_type_label)
            if key in seen:
                skipped += 1
                continue
            seen.add(key)

            existing = db.scalar(
                select(Material).where(
                    Material.order_id == order.id,
                    Material.material_type == material_type_label,
                )
            )
            if existing is None:
                db.add(
                    Material(
                        order_id=order.id,
                        material_type=material_type_label,
                        unit=unit,
                        quantity_planned=qty_planned,
                        quantity_used=qty_used,
                    )
                )
                inserted += 1
            else:
                existing.unit = unit
                existing.quantity_planned = qty_planned
                existing.quantity_used = qty_used
                updated += 1
        except ETLValidationError as exc:
            failed += 1
            if len(errors) < MAX_ROW_ERRORS_PERSISTED:
                errors.append(
                    {
                        "row": row_no,
                        "order_number": _parse_optional_str(row.get("order_number")),
                        "material_code": _parse_optional_str(row.get("material_code")),
                        "error": str(exc),
                    }
                )
        except Exception as exc:  # noqa: BLE001
            logger.exception("ETL row %s falla inesperada", row_no)
            failed += 1
            if len(errors) < MAX_ROW_ERRORS_PERSISTED:
                errors.append({"row": row_no, "error": f"unexpected: {exc!r}"})

    return inserted, updated, skipped, failed, errors


def _process_shipments(
    db: Session, df: pd.DataFrame
) -> Tuple[int, int, int, int, List[Dict[str, Any]]]:
    """
    Registra despachos como ProductionEvent tipo END con prefijo "[ETL][SHIP]".

    Idempotencia: si ya existe un evento END para esa orden con la misma
    timestamp y descripción "[ETL][SHIP]", se omite.
    """
    inserted = skipped = failed = 0
    updated = 0
    errors: List[Dict[str, Any]] = []
    order_cache: Dict[str, ProductionOrder] = {}

    for idx, row in df.iterrows():
        row_no = int(idx) + 2
        try:
            order_number = _parse_str(row.get("order_number"), "order_number", max_length=32)
            order = _order_for(db, order_number, order_cache)
            shipped_at = _parse_dt(row.get("shipped_at"), "shipped_at")
            destination = _parse_str(row.get("destination"), "destination", max_length=64)
            qty_shipped = _parse_int(
                row.get("quantity_shipped"), "quantity_shipped", min_value=1
            )
            carrier = _parse_optional_str(row.get("carrier")) or "—"

            description = (
                f"[ETL][SHIP] {qty_shipped} u → {destination} (transp.: {carrier})"
            )
            existing = db.scalar(
                select(ProductionEvent).where(
                    ProductionEvent.order_id == order.id,
                    ProductionEvent.event_type == EventType.END,
                    ProductionEvent.timestamp == shipped_at,
                    ProductionEvent.description == description,
                )
            )
            if existing is not None:
                skipped += 1
                continue

            db.add(
                ProductionEvent(
                    machine_id=order.machine_id,
                    order_id=order.id,
                    user_id=None,
                    event_type=EventType.END,
                    description=description,
                    timestamp=shipped_at,
                )
            )
            inserted += 1
        except ETLValidationError as exc:
            failed += 1
            if len(errors) < MAX_ROW_ERRORS_PERSISTED:
                errors.append(
                    {
                        "row": row_no,
                        "order_number": _parse_optional_str(row.get("order_number")),
                        "error": str(exc),
                    }
                )
        except Exception as exc:  # noqa: BLE001
            logger.exception("ETL row %s falla inesperada", row_no)
            failed += 1
            if len(errors) < MAX_ROW_ERRORS_PERSISTED:
                errors.append({"row": row_no, "error": f"unexpected: {exc!r}"})

    return inserted, updated, skipped, failed, errors


PROCESSORS: Dict[ETLLoadKind, Callable[[Session, pd.DataFrame], Tuple[int, int, int, int, List[Dict[str, Any]]]]] = {
    ETLLoadKind.PRODUCTION_ORDERS: _process_production_orders,
    ETLLoadKind.CONFIRMATIONS: _process_confirmations,
    ETLLoadKind.MATERIALS: _process_materials,
    ETLLoadKind.SHIPMENTS: _process_shipments,
}


# -----------------------------------------------------------------------------
# Entry point público del servicio
# -----------------------------------------------------------------------------
def process_upload(
    db: Session,
    *,
    content: bytes,
    filename: str,
    kind: ETLLoadKind,
    uploaded_by_id: Optional[int],
) -> ETLLoad:
    """
    Procesa el contenido `content` de un CSV de tipo `kind` y persiste el
    resumen en `etl_loads`. Devuelve la fila creada (ya commiteada).

    El commit es atómico: si el batch entero falla por error global (CSV
    ilegible, columnas faltantes), no se persisten cambios en las tablas
    de negocio, pero SÍ se registra el ETLLoad con status=FAILED.
    """
    started = time.monotonic()
    load = ETLLoad(
        filename=filename,
        kind=kind,
        status=ETLLoadStatus.PENDING,
        uploaded_by_id=uploaded_by_id,
    )
    db.add(load)
    db.flush()  # asigna id sin commitear todavía.

    global_errors: List[str] = []
    inserted = updated = skipped = failed = 0
    rows_total = 0
    row_errors: List[Dict[str, Any]] = []

    try:
        df = _read_csv(content, kind)
        rows_total = int(len(df))
        processor = PROCESSORS[kind]
        inserted, updated, skipped, failed, row_errors = processor(db, df)
    except ValueError as exc:
        global_errors.append(str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error global procesando ETL")
        global_errors.append(f"unexpected: {exc!r}")

    duration_ms = int((time.monotonic() - started) * 1000)

    load.rows_total = rows_total
    load.rows_inserted = inserted
    load.rows_updated = updated
    load.rows_skipped = skipped
    load.rows_failed = failed
    load.duration_ms = duration_ms
    load.error_log = (
        {"global": global_errors, "rows": row_errors}
        if global_errors or row_errors
        else None
    )

    if global_errors:
        load.status = ETLLoadStatus.FAILED
        # Revertir cambios sobre las tablas de negocio antes de re-persistir el ETLLoad.
        db.rollback()
        # Re-attach el load: tras rollback, perdemos la fila pendiente; la re-creamos.
        load = ETLLoad(
            filename=filename,
            kind=kind,
            status=ETLLoadStatus.FAILED,
            uploaded_by_id=uploaded_by_id,
            rows_total=rows_total,
            rows_inserted=0,
            rows_updated=0,
            rows_skipped=0,
            rows_failed=0,
            duration_ms=duration_ms,
            error_log={"global": global_errors, "rows": row_errors},
        )
        db.add(load)
        db.commit()
        db.refresh(load)
        return load

    if failed > 0:
        load.status = ETLLoadStatus.PARTIAL
    else:
        load.status = ETLLoadStatus.SUCCESS

    db.commit()
    db.refresh(load)
    return load
