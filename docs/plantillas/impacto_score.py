#!/usr/bin/env python3
"""
Calculadora del impacto operativo de SmartSack.

Mide la reducción del tiempo necesario para obtener información operativa
ANTES (método tradicional: ERP, teléfono, recorrido a planta) frente a
DESPUÉS (usando SmartSack), y resume una encuesta de satisfacción.

Uso:
    python3 docs/plantillas/impacto_score.py docs/plantillas/impacto_tiempos_ejemplo.csv \
        --satisfaccion docs/plantillas/impacto_satisfaccion_ejemplo.csv

Formato del CSV de tiempos (una fila por medición):
    tarea, rol, tiempo_antes_seg, tiempo_despues_seg

Formato del CSV de satisfacción (una fila por participante):
    participante, rol, S1, S2, S3, S4, S5    (Likert 1-5)

Sin dependencias externas; se ejecuta con el Python del sistema.
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

SAT_ITEMS = ("S1", "S2", "S3", "S4", "S5")


def _read_rows(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


# ---------------------------------------------------------------------------
# Impacto en tiempos
# ---------------------------------------------------------------------------
def analizar_tiempos(rows: List[Dict[str, str]]) -> Tuple[Dict[str, dict], dict]:
    """Agrupa por tarea y calcula medias antes/después y reducción."""
    by_task: Dict[str, List[Tuple[float, float]]] = defaultdict(list)
    for n, row in enumerate(rows, start=2):
        try:
            antes = float((row.get("tiempo_antes_seg") or "").strip())
            despues = float((row.get("tiempo_despues_seg") or "").strip())
        except ValueError:
            raise ValueError(f"fila {n}: tiempos no numéricos")
        if antes <= 0 or despues < 0:
            raise ValueError(f"fila {n}: tiempos fuera de rango")
        tarea = (row.get("tarea") or "—").strip()
        by_task[tarea].append((antes, despues))

    per_task: Dict[str, dict] = {}
    tot_antes: List[float] = []
    tot_despues: List[float] = []
    for tarea, pares in by_task.items():
        a = [p[0] for p in pares]
        d = [p[1] for p in pares]
        tot_antes.extend(a)
        tot_despues.extend(d)
        ma, md = statistics.mean(a), statistics.mean(d)
        per_task[tarea] = {
            "n": len(pares),
            "media_antes": ma,
            "media_despues": md,
            "reduccion_seg": ma - md,
            "reduccion_pct": (1 - md / ma) * 100 if ma else 0.0,
        }

    ga, gd = statistics.mean(tot_antes), statistics.mean(tot_despues)
    overall = {
        "n": len(tot_antes),
        "media_antes": ga,
        "media_despues": gd,
        "reduccion_seg": ga - gd,
        "reduccion_pct": (1 - gd / ga) * 100 if ga else 0.0,
        "factor": ga / gd if gd else float("inf"),
    }
    return per_task, overall


def imprimir_tiempos(per_task: Dict[str, dict], overall: dict) -> None:
    print("IMPACTO EN TIEMPO DE ACCESO A LA INFORMACIÓN")
    print("=" * 78)
    print(f"{'Tarea':<40}{'n':>3}{'Antes(s)':>10}{'Después(s)':>11}{'Reduc.':>8}")
    print("-" * 78)
    for tarea, m in per_task.items():
        print(
            f"{tarea[:39]:<40}{m['n']:>3}{m['media_antes']:>10.0f}"
            f"{m['media_despues']:>11.0f}{m['reduccion_pct']:>7.0f}%"
        )
    print("-" * 78)
    print(
        f"{'GLOBAL':<40}{overall['n']:>3}{overall['media_antes']:>10.0f}"
        f"{overall['media_despues']:>11.0f}{overall['reduccion_pct']:>7.0f}%"
    )
    print(
        f"\nReducción media del tiempo: {overall['reduccion_pct']:.0f}% "
        f"({overall['media_antes']:.0f}s → {overall['media_despues']:.0f}s, "
        f"≈ {overall['factor']:.0f}× más rápido)."
    )


# ---------------------------------------------------------------------------
# Satisfacción
# ---------------------------------------------------------------------------
def analizar_satisfaccion(rows: List[Dict[str, str]]) -> Tuple[Dict[str, float], float, int]:
    por_item: Dict[str, List[int]] = {s: [] for s in SAT_ITEMS}
    globales: List[float] = []
    for n, row in enumerate(rows, start=2):
        vals: List[int] = []
        for s in SAT_ITEMS:
            raw = (row.get(s) or "").strip()
            if not raw:
                raise ValueError(f"fila {n}: falta {s}")
            v = int(raw)
            if not 1 <= v <= 5:
                raise ValueError(f"fila {n}: {s}={v} fuera de rango (1-5)")
            por_item[s].append(v)
            vals.append(v)
        globales.append(statistics.mean(vals))
    medias = {s: statistics.mean(v) for s, v in por_item.items()}
    return medias, statistics.mean(globales), len(globales)


SAT_LABELS = {
    "S1": "Obtengo la información más rápido que antes",
    "S2": "La información es confiable y está actualizada",
    "S3": "Mejora la comunicación entre áreas",
    "S4": "El asistente conversacional es útil",
    "S5": "En general estoy satisfecho/a y lo recomendaría",
}


def imprimir_satisfaccion(medias: Dict[str, float], global_: float, n: int) -> None:
    print("\n\nSATISFACCIÓN PERCIBIDA (Likert 1-5)")
    print("=" * 78)
    print(f"N participantes: {n}")
    print("-" * 78)
    for s in SAT_ITEMS:
        print(f"  {s}  {medias[s]:.2f}/5   {SAT_LABELS[s]}")
    print("-" * 78)
    print(f"Satisfacción media global: {global_:.2f}/5 ({global_ / 5 * 100:.0f}%)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Impacto operativo de SmartSack")
    parser.add_argument("tiempos", help="CSV de tiempos (tarea, rol, antes, después)")
    parser.add_argument("--satisfaccion", help="CSV de satisfacción (opcional)")
    args = parser.parse_args()

    tpath = Path(args.tiempos)
    if not tpath.exists():
        print(f"ERROR: no existe {tpath}", file=sys.stderr)
        return 1
    try:
        per_task, overall = analizar_tiempos(_read_rows(tpath))
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    imprimir_tiempos(per_task, overall)

    if args.satisfaccion:
        spath = Path(args.satisfaccion)
        if not spath.exists():
            print(f"ERROR: no existe {spath}", file=sys.stderr)
            return 1
        try:
            medias, global_, n = analizar_satisfaccion(_read_rows(spath))
        except ValueError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1
        imprimir_satisfaccion(medias, global_, n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
