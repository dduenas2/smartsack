"""
Generador de CSVs de ejemplo que simulan exportaciones reales de SAP.

Produce 4 archivos en `samples/` (relativo al working dir del comando) que
imitan los formatos típicos del módulo PP (Production Planning) de SAP:

  1. production_orders.csv  — Órdenes nuevas/modificadas
  2. confirmations.csv      — Confirmaciones de avance/cierre
  3. materials.csv          — Movimientos de material (consumo)
  4. shipments.csv          — Despachos (salidas a cliente)

Los archivos:
- Tienen separador "," y encabezado en la primera línea.
- Usan formato ISO 8601 para fechas (YYYY-MM-DDTHH:MM:SS).
- Incluyen INTENCIONALMENTE 2-3 filas con errores realistas
  (fechas inválidas, duplicados, tipos mal formateados) para
  ejercitar la validación del ETL.

Ejecución:
    docker compose exec backend python -m scripts.generate_sample_csvs
    docker compose exec backend python -m scripts.generate_sample_csvs --output /app/samples --count 50
"""

from __future__ import annotations

import argparse
import csv
import os
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

# Catálogos coherentes con el seed.
PRODUCT_TYPES = [
    "Saco cemento 50kg",
    "Saco cemento 25kg",
    "Saco cal 25kg",
    "Saco fertilizante 50kg",
    "Saco fertilizante 25kg",
    "Saco harina 25kg",
]
MACHINE_CODES = ["TUB-01", "TUB-02", "IMP-01", "IMP-02", "FON-01", "FON-02", "EMP-01", "EMP-02"]
PRIORITIES = ["low", "normal", "high", "urgent"]
MATERIALS = [
    ("PAPER-KRAFT-80", "Papel kraft 80g", "kg"),
    ("INK-CYAN-LX", "Tinta cian Lx", "L"),
    ("INK-MAGENTA-LX", "Tinta magenta Lx", "L"),
    ("GLUE-PVAC-25", "Pegamento PVAc 25kg", "kg"),
    ("THREAD-COTTON", "Hilo algodón", "m"),
]
DESTINATIONS = ["Bogotá CD", "Cali Plant", "Medellín DC", "Barranquilla Port", "Quito EC", "Lima PE"]


def _ts(dt: datetime) -> str:
    """ISO 8601 sin microsegundos — formato típico de extractores SAP."""
    return dt.replace(microsecond=0).isoformat()


def _gen_order_numbers(start_id: int, count: int) -> List[str]:
    """Genera códigos OP-2026-XXXXXX consecutivos a partir de start_id."""
    return [f"OP-2026-{(start_id + i):06d}" for i in range(count)]


def write_production_orders(out_dir: Path, count: int) -> Path:
    """Genera production_orders.csv con `count` filas + 2 errores intencionales."""
    path = out_dir / "production_orders.csv"
    base = datetime(2026, 5, 5, 6, 0, 0)
    order_numbers = _gen_order_numbers(900_000, count)

    rows = []
    for i, on in enumerate(order_numbers):
        planned_start = base + timedelta(hours=8 * i)
        duration_h = random.randint(4, 16)
        rows.append(
            {
                "order_number": on,
                "product_type": random.choice(PRODUCT_TYPES),
                "product_description": f"Lote {i + 1} de prueba ETL",
                "quantity_ordered": random.choice([5000, 10000, 12000, 15000, 20000]),
                "machine_code": random.choice(MACHINE_CODES),
                "planned_start": _ts(planned_start),
                "planned_end": _ts(planned_start + timedelta(hours=duration_h)),
                "priority": random.choice(PRIORITIES),
            }
        )

    # Errores intencionales:
    # - Fila duplicada del primer order_number (idempotencia → skipped/updated).
    rows.append(rows[0].copy())
    # - Fecha planned_end < planned_start (debe fallar la validación).
    rows.append(
        {
            "order_number": "OP-2026-999998",
            "product_type": "Saco cemento 50kg",
            "product_description": "Fila intencionalmente inválida",
            "quantity_ordered": 5000,
            "machine_code": "TUB-01",
            "planned_start": "2026-05-10T10:00:00",
            "planned_end": "2026-05-10T08:00:00",
            "priority": "normal",
        }
    )
    # - Cantidad no numérica.
    rows.append(
        {
            "order_number": "OP-2026-999999",
            "product_type": "Saco cal 25kg",
            "product_description": "Cantidad no numérica",
            "quantity_ordered": "ABC",
            "machine_code": "IMP-01",
            "planned_start": "2026-05-12T06:00:00",
            "planned_end": "2026-05-12T18:00:00",
            "priority": "normal",
        }
    )

    fieldnames = [
        "order_number",
        "product_type",
        "product_description",
        "quantity_ordered",
        "machine_code",
        "planned_start",
        "planned_end",
        "priority",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_confirmations(out_dir: Path, count: int) -> Path:
    """
    Confirmaciones de operaciones individuales (modelo MES post-refactor).

    Cada fila apunta a una operación concreta (order + machine_code) y
    representa su estado final declarativo: cantidad buena producida,
    desperdicio en kg, tiempos. EMP no acepta scrap > 0.
    """
    path = out_dir / "confirmations.csv"
    base = datetime(2026, 5, 5, 8, 0, 0)
    order_numbers = _gen_order_numbers(900_000, count)
    # Cada orden recorre la ruta IMP→TUB→FON→EMP en una de las 2 líneas
    routes = [
        ["IMP-01", "TUB-01", "FON-01", "EMP-01"],
        ["IMP-02", "TUB-02", "FON-02", "EMP-02"],
    ]
    scrap_reasons = ["quality_defect", "setup_loss", "material_break", "other"]

    rows = []
    for i, on in enumerate(order_numbers):
        route = random.choice(routes)
        for seq, machine_code in enumerate(route, start=1):
            stage_start = base + timedelta(hours=2 * (seq - 1) + 8 * i)
            duration_h = random.randint(2, 4)
            stage_end = stage_start + timedelta(hours=duration_h)
            # ~80% confirmaciones cerradas; resto sólo arrancadas
            is_complete = random.random() < 0.8
            qty_out = random.choice([4800, 9500, 11800, 14700, 19500])
            is_emp = machine_code.startswith("EMP")
            scrap_kg = 0 if is_emp else round(random.uniform(2, 25), 2)
            row = {
                "order_number": on,
                "machine_code": machine_code,
                "quantity_produced": qty_out,
                "actual_start": _ts(stage_start),
                "actual_end": _ts(stage_end) if is_complete else "",
                "scrap_kg": scrap_kg,
                "scrap_reason": random.choice(scrap_reasons) if scrap_kg > 0 else "",
            }
            rows.append(row)

    # Error intencional 1: orden inexistente
    rows.append(
        {
            "order_number": "OP-2026-000000",
            "machine_code": "IMP-01",
            "quantity_produced": 1000,
            "actual_start": "2026-05-10T06:00:00",
            "actual_end": "2026-05-10T10:00:00",
            "scrap_kg": 5,
            "scrap_reason": "quality_defect",
        }
    )
    # Error intencional 2: scrap > 0 en EMP (no permitido)
    if order_numbers:
        rows.append(
            {
                "order_number": order_numbers[0],
                "machine_code": "EMP-01",
                "quantity_produced": 5000,
                "actual_start": "2026-05-10T06:00:00",
                "actual_end": "2026-05-10T08:00:00",
                "scrap_kg": 5.5,
                "scrap_reason": "quality_defect",
            }
        )

    fieldnames = [
        "order_number",
        "machine_code",
        "quantity_produced",
        "actual_start",
        "actual_end",
        "scrap_kg",
        "scrap_reason",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_materials(out_dir: Path, count: int) -> Path:
    """Movimientos de material: 1-3 materiales por orden."""
    path = out_dir / "materials.csv"
    order_numbers = _gen_order_numbers(900_000, count)

    rows = []
    for on in order_numbers:
        for mat_code, mat_name, unit in random.sample(MATERIALS, k=random.randint(1, 3)):
            qty_planned = round(random.uniform(50, 500), 2)
            qty_used = round(qty_planned * random.uniform(0.92, 1.05), 2)
            rows.append(
                {
                    "order_number": on,
                    "material_code": mat_code,
                    "material_name": mat_name,
                    "unit": unit,
                    "quantity_planned": qty_planned,
                    "quantity_used": qty_used,
                }
            )

    # Error intencional: cantidad negativa.
    rows.append(
        {
            "order_number": order_numbers[0],
            "material_code": "PAPER-KRAFT-80",
            "material_name": "Papel kraft 80g",
            "unit": "kg",
            "quantity_planned": -10,
            "quantity_used": 0,
        }
    )

    fieldnames = [
        "order_number",
        "material_code",
        "material_name",
        "unit",
        "quantity_planned",
        "quantity_used",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_shipments(out_dir: Path, count: int) -> Path:
    """Despachos: salidas a cliente, una por orden completada."""
    path = out_dir / "shipments.csv"
    base = datetime(2026, 5, 6, 14, 0, 0)
    order_numbers = _gen_order_numbers(900_000, count)

    rows = []
    for i, on in enumerate(order_numbers):
        if random.random() < 0.6:  # No todas las órdenes se despachan inmediatamente.
            shipped_at = base + timedelta(hours=12 * i)
            rows.append(
                {
                    "order_number": on,
                    "shipped_at": _ts(shipped_at),
                    "destination": random.choice(DESTINATIONS),
                    "quantity_shipped": random.choice([4800, 9500, 11800, 14700, 19500]),
                    "carrier": random.choice(["TCC", "Servientrega", "Coordinadora", "DHL"]),
                }
            )

    # Error intencional: fecha mal formateada.
    rows.append(
        {
            "order_number": order_numbers[0],
            "shipped_at": "no-es-fecha",
            "destination": "Bogotá CD",
            "quantity_shipped": 5000,
            "carrier": "TCC",
        }
    )

    fieldnames = [
        "order_number",
        "shipped_at",
        "destination",
        "quantity_shipped",
        "carrier",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera CSVs de ejemplo del ETL")
    parser.add_argument(
        "--output",
        type=str,
        default="/app/samples",
        help="Directorio de salida (default /app/samples)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=30,
        help="Cantidad base de órdenes a generar (default 30)",
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    paths = [
        write_production_orders(out_dir, args.count),
        write_confirmations(out_dir, args.count),
        write_materials(out_dir, args.count),
        write_shipments(out_dir, args.count),
    ]
    print(f"Generados {len(paths)} CSVs en {out_dir}/:")
    for p in paths:
        print(f"  · {p.name:30s} ({os.path.getsize(p):>6} bytes)")


if __name__ == "__main__":
    main()
