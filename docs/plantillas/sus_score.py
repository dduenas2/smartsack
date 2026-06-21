#!/usr/bin/env python3
"""
Calculadora del puntaje SUS (System Usability Scale) para SmartSack.

Lee un CSV de respuestas (una fila por participante) con las columnas:

    participante, rol, P1, P2, P3, P4, P5, P6, P7, P8, P9, P10

donde P1..P10 son respuestas Likert de 1 (Totalmente en desacuerdo) a 5
(Totalmente de acuerdo). Calcula el puntaje SUS de cada participante y un
resumen agregado (media, desviación, interpretación).

Regla de puntuación estándar (Brooke, 1996):
  · Ítems impares (1,3,5,7,9):  contribución = respuesta − 1
  · Ítems pares   (2,4,6,8,10): contribución = 5 − respuesta
  · SUS = (suma de las 10 contribuciones) × 2,5   → escala 0–100

No requiere dependencias externas; se ejecuta con el Python del sistema:

    python3 docs/plantillas/sus_score.py docs/plantillas/sus_respuestas_ejemplo.csv
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
from pathlib import Path
from typing import Dict, List, Tuple

ODD_ITEMS = (1, 3, 5, 7, 9)   # afirmaciones positivas
EVEN_ITEMS = (2, 4, 6, 8, 10)  # afirmaciones negativas


def sus_score(responses: Dict[int, int]) -> float:
    """Calcula el SUS (0–100) a partir de un dict {1..10: 1..5}."""
    total = 0
    for i in ODD_ITEMS:
        total += responses[i] - 1
    for i in EVEN_ITEMS:
        total += 5 - responses[i]
    return total * 2.5


def interpret(score: float) -> Tuple[str, str, str]:
    """Devuelve (adjetivo, aceptabilidad, grado) según escalas publicadas."""
    # Bangor, Kortum & Miller (2009) — escala de adjetivos.
    if score < 51:
        adjective = "Pobre"
    elif score < 68:
        adjective = "Aceptable (OK)"
    elif score < 80.3:
        adjective = "Bueno"
    else:
        adjective = "Excelente"

    # Rango de aceptabilidad.
    if score >= 70:
        acceptability = "Aceptable"
    elif score >= 50:
        acceptability = "Marginal"
    else:
        acceptability = "No aceptable"

    # Grado (Sauro & Lewis) aproximado por percentil.
    if score >= 80.3:
        grade = "A"
    elif score >= 74:
        grade = "B"
    elif score >= 68:
        grade = "C"
    elif score >= 51:
        grade = "D"
    else:
        grade = "F"
    return adjective, acceptability, grade


def _read_rows(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _parse_responses(row: Dict[str, str], line: int) -> Dict[int, int]:
    responses: Dict[int, int] = {}
    for i in range(1, 11):
        raw = (row.get(f"P{i}") or "").strip()
        if not raw:
            raise ValueError(f"fila {line}: falta la respuesta P{i}")
        val = int(raw)
        if not 1 <= val <= 5:
            raise ValueError(f"fila {line}: P{i}={val} fuera de rango (1-5)")
        responses[i] = val
    return responses


def main() -> int:
    parser = argparse.ArgumentParser(description="Calcula el puntaje SUS de SmartSack")
    parser.add_argument("csv", type=str, help="CSV de respuestas (participante, rol, P1..P10)")
    args = parser.parse_args()

    path = Path(args.csv)
    if not path.exists():
        print(f"ERROR: no existe el archivo {path}", file=sys.stderr)
        return 1

    rows = _read_rows(path)
    if not rows:
        print("ERROR: el CSV no tiene filas de respuestas", file=sys.stderr)
        return 1

    scores: List[float] = []
    by_role: Dict[str, List[float]] = {}

    print(f"{'Participante':<16}{'Rol':<14}{'SUS':>7}  Interpretación")
    print("-" * 60)
    for n, row in enumerate(rows, start=2):
        try:
            responses = _parse_responses(row, n)
        except ValueError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1
        s = sus_score(responses)
        scores.append(s)
        role = (row.get("rol") or "—").strip()
        by_role.setdefault(role, []).append(s)
        adjective, _accept, _grade = interpret(s)
        name = (row.get("participante") or f"P{n - 1}").strip()
        print(f"{name:<16}{role:<14}{s:>7.1f}  {adjective}")

    mean = statistics.mean(scores)
    adjective, acceptability, grade = interpret(mean)

    print("-" * 60)
    print(f"N participantes        : {len(scores)}")
    print(f"SUS promedio           : {mean:.1f}")
    if len(scores) > 1:
        print(f"Desviación estándar    : {statistics.stdev(scores):.1f}")
    print(f"Mínimo / Máximo        : {min(scores):.1f} / {max(scores):.1f}")
    print(f"Interpretación         : {adjective}  ·  {acceptability}  ·  grado {grade}")
    print(f"Referencia (media SUS) : 68,0 (percentil 50)")

    if len(by_role) > 1:
        print("\nPor rol:")
        for role, vals in sorted(by_role.items()):
            print(f"  {role:<14} n={len(vals):<3} SUS={statistics.mean(vals):.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
