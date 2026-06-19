"""
Servicio del chatbot conversacional de SmartSack.

Dos modos de operación:

  · **LLM mode** (cuando `ANTHROPIC_API_KEY` es válida): usa LangChain +
    `ChatAnthropic` con function calling. El modelo decide qué tool invocar,
    nosotros la ejecutamos contra la BD y devolvemos el resultado al modelo
    para que redacte la respuesta final en español.

  · **Fallback mode** (sin API key, o cuando el LLM falla): un router
    heurístico por palabras clave que mapea la pregunta a una tool y devuelve
    una respuesta pre-formateada en español. Suficiente para demos sin
    credenciales y como red de seguridad.

Decisiones:
- El servicio mantiene una conversación stateless: el frontend manda el
  `history` completo en cada llamada. Sencillo y testeable.
- Limitamos el número de iteraciones tool-calling a 4 para evitar bucles.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.chat.tools import TOOL_REGISTRY, TOOL_SCHEMAS
from app.config import settings


logger = logging.getLogger("smartsack.chat")

MAX_TOOL_ITERATIONS = 4
MAX_HISTORY_MESSAGES = 20

SYSTEM_PROMPT = """Eres SmartSack Assistant, un agente que ayuda a operarios y supervisores de una planta de sacos de papel.

REGLAS:
1. Responde SIEMPRE en español, en tono profesional pero cercano.
2. Usa las tools disponibles para responder con datos REALES de la BD operacional.
3. NO inventes números: si la tool no tiene un dato, dilo explícitamente.
4. Cuando devuelvas cifras, formatea con separador de miles ("12,345").
5. Después de invocar la tool, sintetiza la respuesta en máximo 4-5 frases.
6. Si te preguntan algo fuera del dominio (clima, política, tecnología no SmartSack), redirige amablemente.
7. Si la pregunta es ambigua, asume defaults razonables (ventana = hoy, todas las máquinas).

Contexto del dominio:
- Planta con 8 máquinas: TUB-01/02 (tubuladoras), IMP-01/02 (impresoras), FON-01/02 (fondadoras), EMP-01/02 (empacadoras).
- 3 turnos diarios (turno_1: 06-14, turno_2: 14-22, turno_3: 22-06).
- Productos típicos: sacos de cemento, cal, fertilizante, harina (25kg / 50kg).
- OEE = Disponibilidad × Rendimiento × Calidad. Benchmark mundial ≥ 85%.
"""


# -----------------------------------------------------------------------------
# DTOs
# -----------------------------------------------------------------------------
@dataclass
class ChatMessage:
    """Un turno del historial. role ∈ {'user','assistant'}."""

    role: str
    content: str


@dataclass
class ToolCall:
    """Registro de una invocación de tool durante la respuesta."""

    name: str
    arguments: Dict[str, Any]
    result_preview: str = ""


@dataclass
class ChatResponse:
    """Resultado del servicio. Mode indica qué ruta se tomó."""

    reply: str
    mode: str  # "llm" | "fallback"
    tool_calls: List[ToolCall] = field(default_factory=list)
    error: Optional[str] = None


# -----------------------------------------------------------------------------
# Detección de disponibilidad de la API
# -----------------------------------------------------------------------------
_PLACEHOLDER_KEYS = {
    "",
    "tu_api_key_de_anthropic_aqui",
    "your-anthropic-api-key",
    "sk-ant-xxx",
}


def is_llm_available() -> bool:
    """True si la key parece real (no placeholder y empieza con sk-ant)."""
    key = (settings.anthropic_api_key or "").strip()
    if key in _PLACEHOLDER_KEYS or len(key) < 20:
        return False
    return key.startswith("sk-ant-")


# -----------------------------------------------------------------------------
# Ejecutor compartido de tools
# -----------------------------------------------------------------------------
def _execute_tool(db: Session, name: str, arguments: Dict[str, Any]) -> Tuple[Any, str]:
    """
    Ejecuta la tool y devuelve (resultado, preview-recortado).
    Si la tool no existe, lanza ValueError (caller decide cómo manejar).
    """
    if name not in TOOL_REGISTRY:
        raise ValueError(f"Tool desconocida: {name}")
    fn = TOOL_REGISTRY[name]
    result = fn(db, **arguments)
    preview = json.dumps(result, ensure_ascii=False, default=str)
    if len(preview) > 200:
        preview = preview[:197] + "..."
    return result, preview


# -----------------------------------------------------------------------------
# LLM mode (LangChain + Claude)
# -----------------------------------------------------------------------------
def _llm_chat(db: Session, history: List[ChatMessage], message: str) -> ChatResponse:
    """
    Conversación con tool-calling vía langchain_anthropic.

    Bucle:
      - Mandar mensajes al modelo con `tools=TOOL_SCHEMAS`.
      - Si responde con `tool_use`, ejecutar y volver a llamar con el `tool_result`.
      - Si responde texto, devolverlo.
    """
    from langchain_anthropic import ChatAnthropic
    from langchain_core.messages import (
        AIMessage,
        HumanMessage,
        SystemMessage,
        ToolMessage,
    )

    # Convertir nuestros TOOL_SCHEMAS al formato Anthropic-native que ChatAnthropic acepta
    # (se le pueden pasar dicts directamente con `bind_tools` desde 0.3+).
    llm = ChatAnthropic(
        model=settings.anthropic_model,
        api_key=settings.anthropic_api_key,
        temperature=0.2,
        max_tokens=1024,
        timeout=30,
    ).bind_tools(TOOL_SCHEMAS)

    messages: List[Any] = [SystemMessage(content=SYSTEM_PROMPT)]
    for m in history[-MAX_HISTORY_MESSAGES:]:
        if m.role == "user":
            messages.append(HumanMessage(content=m.content))
        elif m.role == "assistant":
            messages.append(AIMessage(content=m.content))
    messages.append(HumanMessage(content=message))

    tool_calls_used: List[ToolCall] = []

    for _ in range(MAX_TOOL_ITERATIONS):
        ai = llm.invoke(messages)
        messages.append(ai)

        calls = getattr(ai, "tool_calls", None) or []
        if not calls:
            text = ai.content if isinstance(ai.content, str) else "".join(
                blk.get("text", "") for blk in ai.content if isinstance(blk, dict)
            )
            return ChatResponse(reply=text or "(respuesta vacía)", mode="llm", tool_calls=tool_calls_used)

        # Ejecutar cada tool_call y añadir ToolMessage con el resultado.
        for tc in calls:
            tool_name = tc.get("name") if isinstance(tc, dict) else tc.name
            tool_args = tc.get("args") if isinstance(tc, dict) else tc.args
            tool_id = tc.get("id") if isinstance(tc, dict) else tc.id
            try:
                result, preview = _execute_tool(db, tool_name, tool_args or {})
            except Exception as exc:  # noqa: BLE001
                result = {"error": str(exc)}
                preview = f"error: {exc}"
            tool_calls_used.append(
                ToolCall(name=tool_name, arguments=tool_args or {}, result_preview=preview)
            )
            messages.append(
                ToolMessage(
                    content=json.dumps(result, ensure_ascii=False, default=str),
                    tool_call_id=tool_id,
                )
            )

    return ChatResponse(
        reply=(
            "Lo siento, di varias vueltas sin llegar a una respuesta concluyente. "
            "Intenta reformular la pregunta o sé más específico (máquina, fecha)."
        ),
        mode="llm",
        tool_calls=tool_calls_used,
    )


# -----------------------------------------------------------------------------
# Fallback por keywords
# -----------------------------------------------------------------------------
_KEYWORD_RULES: List[Tuple[List[str], str]] = [
    (["alerta", "alertas", "riesgo", "retraso", "retrasos", "se va a retrasar"], "get_alerts"),
    (["scrap", "desperdicio", "merma", "rechazos", "defecto", "defectos"], "get_scrap_summary"),
    (["yield", "rendimiento por máquina", "rendimiento por maquina", "eficiencia por máquina", "eficiencia por maquina", "cuello de botella", "out/in"], "get_yield_summary"),
    (["wip", "trabajo en proceso", "en tránsito", "en transito", "en cola", "cola", "en el piso"], "get_wip_status"),
    (["oee", "disponibilidad", "calidad", "eficiencia global"], "get_oee_data"),
    (["paradas", "parada", "incidencia", "incidencias", "stops"], "get_machine_status"),
    (["máquina", "maquina", "estación", "estacion"], "get_machine_status"),
    (["orden", "op-"], "get_order_info"),
    (["produj", "producid", "producción", "produccion", "sacos", "cumplimiento"], "get_production_stats"),
]


def _detect_machine_code(text: str) -> Optional[str]:
    m = re.search(r"\b(TUB|IMP|FON|EMP)-?(\d{1,2})\b", text, re.IGNORECASE)
    if not m:
        return None
    prefix = m.group(1).upper()
    num = m.group(2).zfill(2)
    return f"{prefix}-{num}"


def _detect_order_number(text: str) -> Optional[str]:
    m = re.search(r"\bOP-?\d{4}-?\d{4,6}\b", text, re.IGNORECASE)
    if not m:
        return None
    raw = m.group(0).upper().replace(" ", "")
    # Normalizar a OP-YYYY-NNNNNN
    digits = re.sub(r"\D", "", raw)
    if len(digits) >= 10:
        year = digits[:4]
        seq = digits[4:].rjust(6, "0")
        return f"OP-{year}-{seq}"
    return raw


def _detect_days_back(text: str) -> int:
    """Mapea expresiones temporales en español a `days_back`."""
    t = text.lower()
    if "ayer" in t:
        return 1
    if "última semana" in t or "ultima semana" in t or "semana" in t:
        return 7
    if "mes" in t:
        return 30
    if re.search(r"hoy|actual", t):
        return 0
    m = re.search(r"últim[ao]s?\s+(\d+)\s+d[ií]as", t)
    if m:
        return int(m.group(1))
    return 0


def _route_keywords(text: str) -> str:
    t = text.lower()
    for keywords, tool in _KEYWORD_RULES:
        if any(k in t for k in keywords):
            return tool
    # Default: producción.
    return "get_production_stats"


def _format_fallback_reply(tool: str, args: Dict[str, Any], result: Any) -> str:
    """Genera una respuesta natural a partir del resultado de la tool."""
    if isinstance(result, dict) and result.get("error"):
        return f"No pude responder: {result['error']}."

    if tool == "get_production_stats":
        r = result
        return (
            f"En {r['window']}, se completaron {r['completed_orders']} órdenes "
            f"({r['produced_units']:,} sacos producidos sobre {r['ordered_units']:,} planificados, "
            f"cumplimiento {r['fulfillment_rate'] * 100:.1f}%). "
            f"Hay {r['in_progress_orders']} órdenes en curso y {r['delayed_orders']} retrasadas."
        )
    if tool == "get_machine_status":
        machines = result.get("machines", [])
        if not machines:
            return "No encontré máquinas que coincidan con la consulta."
        if args.get("machine_code"):
            m = machines[0]
            co = m.get("current_order")
            co_str = f" Está en {co['order_number']} ({co['product_type']}, {co['progress']*100:.0f}% avance)." if co else ""
            return (
                f"{m['name']} ({m['code']}) está en estado **{m['status']}**, "
                f"con {m['stops_count']} paradas y {m['incidents_count']} incidencias en {result['window']}.{co_str}"
            )
        # Top global
        top = machines[0]
        running = sum(1 for m in machines if m["status"] == "running")
        return (
            f"{result['window']}: {running}/{len(machines)} máquinas en operación. "
            f"La que más paradas registra es **{top['code']}** ({top['name']}) con "
            f"{top['stops_count']} paradas y {top['incidents_count']} incidencias."
        )
    if tool == "get_order_info":
        if "error" in result:
            return f"No pude encontrar esa orden: {result['error']}."
        prog = result["progress"] * 100
        delay_str = ""
        if result.get("delay_prediction"):
            dp = result["delay_prediction"]
            delay_str = (
                f" El modelo {dp['model_version']} estima {dp['probability']*100:.0f}% "
                f"de probabilidad de retraso (≈{dp['predicted_delay_hours']}h)."
            )
        return (
            f"Orden **{result['order_number']}** ({result['product_type']}) en máquina "
            f"{result.get('machine_code') or '—'}. Estado: {result['status']}, prioridad {result['priority']}. "
            f"Avance: {result['quantity_produced']:,}/{result['quantity_ordered']:,} sacos ({prog:.1f}%).{delay_str}"
        )
    if tool == "get_oee_data":
        scope = result["scope"]
        oee_pct = result["oee"] * 100
        if scope == "planta" and result.get("by_machine"):
            # Filtrar máquinas sin datos (oee None) — pueden aparecer si fueron
            # añadidas recientemente y aún no tienen oee_records.
            top = next(
                (m for m in result["by_machine"] if m.get("oee") is not None),
                None,
            )
            top_str = (
                f" La máquina con mejor OEE es {top['machine_code']} ({top['oee']*100:.1f}%)."
                if top
                else ""
            )
            return (
                f"OEE de planta en {result['window']}: **{oee_pct:.1f}%** "
                f"(Disponibilidad {result['availability']*100:.1f}%, "
                f"Rendimiento {result['performance']*100:.1f}%, "
                f"Calidad {result['quality']*100:.1f}%).{top_str}"
            )
        return (
            f"OEE de {scope} en {result['window']}: **{oee_pct:.1f}%** "
            f"(A {result['availability']*100:.1f}% · P {result['performance']*100:.1f}% · Q {result['quality']*100:.1f}%)."
        )
    if tool == "get_alerts":
        alerts = result.get("alerts", [])
        if not alerts:
            return f"No hay órdenes con probabilidad de retraso ≥ {result['threshold']*100:.0f}%."
        lines = [
            f"- {a['order_number']} ({a['product_type']}, {a['machine_code'] or '—'}): "
            f"{a['delay_probability']*100:.0f}% prob. de retraso (~{a['predicted_delay_hours']}h)"
            for a in alerts
        ]
        return (
            f"Tengo {result['count']} alerta(s) por encima del umbral {result['threshold']*100:.0f}%:\n"
            + "\n".join(lines)
        )
    if tool == "get_scrap_summary":
        total = result.get("total_scrap_kg", 0.0)
        by_machine = result.get("by_machine", [])
        by_reason = result.get("by_reason", [])
        if not by_machine:
            return "No registré scrap en la ventana consultada."
        top = by_machine[0]
        reason_str = ""
        if by_reason:
            r = by_reason[0]
            reason_str = (
                f" La causa principal fue **{r['reason']}** ({r['scrap_kg']:.1f} kg)."
            )
        return (
            f"Scrap total en la ventana: **{total:.1f} kg**. "
            f"La máquina con más merma fue **{top['machine_code']}** "
            f"({top['scrap_kg']:.1f} kg en {top['operations_completed']} operaciones)."
            + reason_str
        )
    if tool == "get_yield_summary":
        items = result.get("items", [])
        if not items:
            return "No hay operaciones cerradas en la ventana para calcular yield."
        bottleneck = result.get("bottleneck")
        head_lines = [
            f"- {i['machine_code']}: {i['yield_pct']:.2f}% "
            f"({i['quantity_out']:,}/{i['quantity_in']:,} ud)"
            for i in items[:4]
            if i.get("yield_pct") is not None
        ]
        bn_str = ""
        if bottleneck:
            bn_str = (
                f" Cuello de botella: **{bottleneck['machine_code']}** "
                f"con yield {bottleneck['yield_pct']:.2f}%."
            )
        return (
            "Yield (out/in) por máquina:\n" + "\n".join(head_lines) + bn_str
        )
    if tool == "get_wip_status":
        total_units = result.get("total_units_in_line", 0)
        in_progress = result.get("total_in_progress_operations", 0)
        ready = result.get("total_ready_operations", 0)
        machines = result.get("machines", [])
        non_empty = [m for m in machines if m["units_total"] > 0]
        if not non_empty:
            return "No hay operaciones activas en la planta ahora mismo."
        non_empty.sort(key=lambda m: m["units_total"], reverse=True)
        head = non_empty[0]
        return (
            f"WIP actual: **{total_units:,} sacos** en línea "
            f"({in_progress} operaciones corriendo, {ready} en cola). "
            f"La máquina más cargada es **{head['machine_code']}** "
            f"con {head['units_total']:,} unidades."
        )
    return f"Resultado de {tool}:\n{json.dumps(result, ensure_ascii=False, indent=2, default=str)[:500]}"


def _fallback_chat(db: Session, message: str) -> ChatResponse:
    """Modo sin LLM: heurística por palabras clave."""
    tool = _route_keywords(message)
    args: Dict[str, Any] = {}

    machine = _detect_machine_code(message)
    order_number = _detect_order_number(message)
    days = _detect_days_back(message)

    if tool == "get_order_info" and order_number:
        args = {"order_number": order_number}
    elif tool == "get_order_info":
        # Reroute si no detectamos número.
        tool = "get_production_stats"

    if tool == "get_production_stats":
        args = {"days_back": days}
        if machine:
            args["machine_code"] = machine
    elif tool == "get_machine_status":
        args = {"days_back_for_events": days}
        if machine:
            args["machine_code"] = machine
    elif tool == "get_oee_data":
        args = {"days_back": max(days, 0)}
        if machine:
            args["machine_code"] = machine
    elif tool == "get_alerts":
        args = {"threshold": 0.6, "limit": 5}
    elif tool == "get_scrap_summary":
        args = {"days_back": days}
        if machine:
            args["machine_code"] = machine
    elif tool == "get_yield_summary":
        # Para yield la ventana razonable es semana, salvo que el usuario diga otra cosa.
        args = {"days_back": days if days > 0 else 6}
        if machine:
            args["machine_code"] = machine
    elif tool == "get_wip_status":
        args = {}

    try:
        result, preview = _execute_tool(db, tool, args)
    except Exception as exc:  # noqa: BLE001
        return ChatResponse(
            reply=f"Hubo un error ejecutando la consulta: {exc}",
            mode="fallback",
            tool_calls=[],
            error=str(exc),
        )

    reply = _format_fallback_reply(tool, args, result)
    return ChatResponse(
        reply=reply,
        mode="fallback",
        tool_calls=[ToolCall(name=tool, arguments=args, result_preview=preview)],
    )


# -----------------------------------------------------------------------------
# API pública
# -----------------------------------------------------------------------------
def chat(
    db: Session, *, message: str, history: Optional[List[ChatMessage]] = None
) -> ChatResponse:
    """
    Procesa un mensaje del usuario y devuelve la respuesta del asistente.

    - Si hay API key válida → ruta LLM (LangChain + Claude function calling).
    - Si no, o si el LLM falla con excepción de red/auth → fallback por keywords.
    """
    history = history or []
    if not message.strip():
        return ChatResponse(reply="Hazme una pregunta sobre la planta para empezar.", mode="fallback")

    if is_llm_available():
        try:
            return _llm_chat(db, history, message)
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM falló, usando fallback: %r", exc)
            resp = _fallback_chat(db, message)
            resp.error = f"LLM error: {type(exc).__name__}"
            return resp

    return _fallback_chat(db, message)
