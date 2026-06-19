"""
Demo: simula 2 operarios trabajando operaciones en paralelo durante N segundos.

Cada operario consume operaciones READY de su máquina (modelo MES post-refactor):
1) Lista operaciones READY/IN_PROGRESS de su máquina.
2) Si hay una IN_PROGRESS, sigue reportando producción/scrap y al final la cierra.
3) Si no, toma la primera READY (start_operation), reporta producción
   incrementalmente y la cierra (lo que auto-promueve la siguiente máquina).

Útil para ver la vista supervisor reaccionando en tiempo real con tráfico
realista (eventos start, production_update, end + machine_update + operation
promoted) y confirmar que el WebSocket entrega broadcasts.

Ejecutar (dentro del contenedor backend):

    docker compose exec backend python -m scripts.demo_two_operators
    docker compose exec backend python -m scripts.demo_two_operators --duration 90 --interval 3

Operarios usados:
  · op_imp-01_1 → IMP-01 (línea A, primera etapa)
  · op_imp-02_1 → IMP-02 (línea B, primera etapa)

Ambos arrancan en IMP porque es la única operación que queda READY al
crearse la orden; al cerrarla, la siguiente máquina (TUB) queda READY,
pero ese operario no está corriendo en este demo (lo verás en la vista
supervisor como una operación lista para tomar).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

# Dentro del contenedor backend, hablamos con Nginx por su nombre de servicio.
BASE_HTTP = "http://nginx:80"

SCRAP_REASONS = ["quality_defect", "setup_loss", "material_break", "other"]


def post_form(path: str, fields: dict) -> dict:
    body = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(
        f"{BASE_HTTP}{path}",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    return json.load(urllib.request.urlopen(req))


def post_json(path: str, payload: dict, token: str) -> dict:
    req = urllib.request.Request(
        f"{BASE_HTTP}{path}",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    return json.load(urllib.request.urlopen(req))


def get_json(path: str, token: str, params: Optional[dict] = None) -> Any:
    if params:
        # Soportar listas (ej. status=[ready,in_progress])
        flat: List[tuple] = []
        for k, v in params.items():
            if isinstance(v, (list, tuple)):
                for item in v:
                    flat.append((k, item))
            else:
                flat.append((k, v))
        path = f"{path}?{urllib.parse.urlencode(flat)}"
    req = urllib.request.Request(
        f"{BASE_HTTP}{path}",
        headers={"Authorization": f"Bearer {token}"},
    )
    return json.load(urllib.request.urlopen(req))


def list_operations_for_machine(token: str, machine_id: int) -> List[Dict[str, Any]]:
    return get_json(
        "/api/operations",
        token,
        {"machine_id": machine_id, "status": ["ready", "in_progress"], "limit": 5},
    )


def pick_next_op(ops: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Prefiere la IN_PROGRESS si existe; si no, la primera READY."""
    for op in ops:
        if op.get("status") == "in_progress":
            return op
    for op in ops:
        if op.get("status") == "ready":
            return op
    return None


async def operator_loop(
    name: str, username: str, interval: float, stop_at: datetime
) -> None:
    """Bucle de un operario virtual: trabaja operaciones reales hasta `stop_at`."""
    token = post_form(
        "/api/auth/login",
        {"username": username, "password": "smartsack123"},
    )["access_token"]
    me = get_json("/api/auth/me", token)
    machine_id = me.get("machine_id")
    if machine_id is None:
        print(f"[{name}] usuario sin máquina asignada, abortando")
        return

    print(f"[{name}] activo en machine_id={machine_id}")

    while datetime.now() < stop_at:
        try:
            ops = list_operations_for_machine(token, machine_id)
        except Exception as exc:  # noqa: BLE001
            print(f"[{name}] error listando operaciones: {exc}")
            await asyncio.sleep(interval)
            continue

        op = pick_next_op(ops)
        if op is None:
            print(f"[{name}] sin operaciones disponibles ahora; reintenta en {interval}s")
            await asyncio.sleep(interval)
            continue

        op_id = op["id"]
        order_number = (op.get("order") or {}).get("order_number") or "?"

        # 1) Si la operación está READY, la inicio.
        if op["status"] == "ready":
            try:
                op = post_json(f"/api/operations/{op_id}/start", {}, token)
                print(
                    f"[{name}] start op#{op_id} (orden {order_number}, "
                    f"qty_in={op.get('quantity_in', 0)})"
                )
            except Exception as exc:  # noqa: BLE001
                print(f"[{name}] no pude iniciar op#{op_id}: {exc}")
                await asyncio.sleep(interval)
                continue

        # 2) Reportar producción incremental hasta llegar a quantity_in (o cerca).
        qty_in = max(op.get("quantity_in", 0), 1)
        # Repartimos el lote en 3-5 reportes parciales.
        chunks = random.randint(3, 5)
        per_chunk = max(1, qty_in // chunks)

        for i in range(chunks):
            if datetime.now() >= stop_at:
                break
            quantity = per_chunk
            scrap_kg = 0
            scrap_reason = None
            # Solo no-EMP genera scrap; las EMP en este demo no aparecerán
            # porque el operador es de IMP, pero protegemos por si acaso.
            if not op.get("machine_code", "").startswith("EMP") and random.random() < 0.4:
                scrap_kg = round(random.uniform(0.5, 3.0), 2)
                scrap_reason = random.choice(SCRAP_REASONS)
            payload = {"quantity": quantity}
            if scrap_kg:
                payload["scrap_kg"] = scrap_kg
                payload["scrap_reason"] = scrap_reason
            try:
                op = post_json(f"/api/operations/{op_id}/report", payload, token)
                ts = datetime.now().strftime("%H:%M:%S")
                scrap_str = f" · scrap={scrap_kg}kg ({scrap_reason})" if scrap_kg else ""
                print(
                    f"[{name} @ {ts}] report op#{op_id} +{quantity} ud "
                    f"(out={op.get('quantity_out', 0)}/{qty_in}){scrap_str}"
                )
            except Exception as exc:  # noqa: BLE001
                print(f"[{name}] error reporte op#{op_id}: {exc}")
            await asyncio.sleep(interval + random.uniform(-0.5, 0.5))

        # 3) Cerrar la operación → auto-promueve la siguiente máquina a READY.
        try:
            op = post_json(f"/api/operations/{op_id}/complete", {}, token)
            print(
                f"[{name}] complete op#{op_id} (orden {order_number}, "
                f"out={op.get('quantity_out', 0)})"
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[{name}] error cerrando op#{op_id}: {exc}")
        await asyncio.sleep(interval)


async def main(duration: int, interval: float) -> None:
    stop_at = datetime.now().replace(microsecond=0) + timedelta(seconds=duration)

    print(f"=== Demo de 2 operarios trabajando operaciones durante {duration}s ===")
    print(
        "    Abre la vista supervisor (admin / smartsack123) para ver, en vivo,\n"
        "    eventos start/production_update/end y promociones automáticas\n"
        "    de operaciones cuando se cierra IMP-01 / IMP-02.\n"
    )

    await asyncio.gather(
        operator_loop("OP-A · IMP-01", "op_imp-01_1", interval, stop_at),
        operator_loop("OP-B · IMP-02", "op_imp-02_1", interval, stop_at),
    )

    print("\n=== Demo terminada ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Demo de dos operarios trabajando operaciones")
    parser.add_argument(
        "--duration", type=int, default=60, help="Duración total en segundos (default 60)"
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=3.0,
        help="Segundos entre reportes parciales (default 3)",
    )
    args = parser.parse_args()
    asyncio.run(main(args.duration, args.interval))
