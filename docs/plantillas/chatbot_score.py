#!/usr/bin/env python3
"""
Calculadora de exactitud del asistente conversacional de SmartSack (hipótesis H3).

Evalúa el protocolo de 50 preguntas estandarizadas: para cada pregunta se marca
si el chatbot respondió correctamente (1) o no (0). Calcula la tasa de respuesta
correcta global y por categoría, y la contrasta con la meta de H3 (≥ 85 %).

Formato del CSV (una fila por pregunta):
    id, categoria, pregunta, correcta        (correcta = 1 acierto / 0 fallo)

Uso (Python del sistema, sin dependencias):
    python3 docs/plantillas/chatbot_score.py docs/plantillas/chatbot_respuestas_ejemplo.csv
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

META_H3 = 85.0  # umbral de la hipótesis H3 (% de respuestas correctas)


def _read_rows(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def main() -> int:
    parser = argparse.ArgumentParser(description="Exactitud del chatbot (H3)")
    parser.add_argument("csv", help="CSV de evaluación (id, categoria, pregunta, correcta)")
    args = parser.parse_args()

    path = Path(args.csv)
    if not path.exists():
        print(f"ERROR: no existe {path}", file=sys.stderr)
        return 1

    rows = _read_rows(path)
    answered = []
    by_cat: Dict[str, List[int]] = defaultdict(list)
    for n, row in enumerate(rows, start=2):
        raw = (row.get("correcta") or "").strip()
        if raw == "":
            continue  # pregunta aún sin evaluar
        try:
            v = int(raw)
        except ValueError:
            print(f"ERROR: fila {n}: 'correcta'='{raw}' no es 0/1", file=sys.stderr)
            return 1
        if v not in (0, 1):
            print(f"ERROR: fila {n}: 'correcta' debe ser 0 o 1", file=sys.stderr)
            return 1
        answered.append(v)
        by_cat[(row.get("categoria") or "—").strip()].append(v)

    if not answered:
        print("ERROR: ninguna pregunta evaluada (columna 'correcta' vacía)", file=sys.stderr)
        return 1

    acc = 100.0 * statistics.mean(answered)
    print("EXACTITUD DEL ASISTENTE CONVERSACIONAL (H3)")
    print("=" * 60)
    print(f"Preguntas evaluadas : {len(answered)}")
    print(f"Aciertos            : {sum(answered)}")
    print(f"Exactitud global    : {acc:.1f} %")
    print(f"Meta H3             : >= {META_H3:.0f} %  ->  {'CUMPLE' if acc >= META_H3 else 'NO CUMPLE'}")
    print("-" * 60)
    print("Por categoría:")
    for cat, vals in sorted(by_cat.items()):
        print(f"  {cat:<28} {sum(vals)}/{len(vals)}  ({100*statistics.mean(vals):.0f} %)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
