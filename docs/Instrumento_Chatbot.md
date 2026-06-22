# Instrumento de evaluación del asistente conversacional

**Proyecto:** SmartSack · **Entregable:** E7 (validación con usuarios) ·
**Tipo:** protocolo de preguntas estandarizadas con evaluación binaria de acierto

Este instrumento mide la **tasa de respuesta correcta** del asistente
conversacional de SmartSack y contrasta el resultado con la hipótesis **H3** del
anteproyecto.

> **H3:** *El asistente conversacional con LLM responderá correctamente al menos
> el 85 % de las consultas en lenguaje natural sobre datos de producción
> incluidas en el protocolo de 50 preguntas estandarizadas.*

---

## 1. Objetivo

Cuantificar qué porcentaje de un conjunto fijo y representativo de consultas en
lenguaje natural sobre la operación de la planta es respondido correctamente por
el asistente, tanto en modo LLM (Claude vía *function-calling*) como —si se
desea— en modo *fallback* heurístico.

## 2. Variable e indicador

| Variable | Indicador | Instrumento |
|---|---|---|
| Exactitud del asistente | % de respuestas correctas sobre el protocolo de 50 preguntas | Evaluación binaria (1 acierto / 0 fallo) por pregunta |

## 3. Diseño del protocolo

Se define un **protocolo fijo de 50 preguntas** ([`plantillas/chatbot_respuestas_plantilla.csv`](./plantillas/chatbot_respuestas_plantilla.csv))
que cubre las capacidades reales del asistente (las herramientas de
`chat/tools.py`) más una categoría de control fuera de alcance. El protocolo es
**cerrado**: las mismas 50 preguntas se aplican siempre, lo que hace la medición
reproducible y comparable entre ejecuciones.

| Categoría | Preguntas | Qué evalúa |
|---|---|---|
| `produccion` | 7 | Conteos y totales de producción (turno, día, semana, mes) |
| `maquina` | 6 | Estado y disponibilidad de máquinas |
| `orden` | 6 | Estado, producto y planificación de órdenes concretas |
| `oee` | 6 | OEE, disponibilidad, rendimiento y calidad |
| `alertas` | 5 | Órdenes en riesgo y alertas de retraso (salida del modelo ML) |
| `scrap` | 5 | Desperdicio por máquina, total y causas |
| `yield` | 5 | Rendimiento de material por máquina, línea y producto |
| `cuello_botella` | 4 | Identificación de restricciones de la planta |
| `wip` | 4 | Trabajo en proceso |
| `fuera_alcance` | 2 | Preguntas que el asistente **debe** rechazar o redirigir |

La categoría `fuera_alcance` es deliberada: una respuesta es correcta cuando el
asistente **reconoce que la consulta está fuera de su dominio** (no inventa un
dato), lo que penaliza las alucinaciones.

## 4. Protocolo de aplicación

1. **Preparación:** stack en marcha con datos de demostración (`scripts.seed`) y,
   para evaluar el modo LLM, una `ANTHROPIC_API_KEY` válida configurada. Se parte
   de la ficha de captura ([`plantillas/chatbot_respuestas_plantilla.csv`](./plantillas/chatbot_respuestas_plantilla.csv)).
2. **Ejecución:** cada una de las 50 preguntas se formula al asistente desde la
   vista de chat (o vía `POST /api/chat`). Se observa la respuesta.
3. **Calificación:** un evaluador marca la columna `correcta` con **1** si la
   respuesta es factualmente correcta y pertinente, o **0** en caso contrario
   (dato erróneo, herramienta equivocada, alucinación, o no responder cuando
   debía). Se recomienda **doble evaluador** y resolver discrepancias por
   consenso.
4. **Repetición opcional:** para distinguir aciertos estables de respuestas
   sensibles a la aleatoriedad del LLM, el protocolo puede aplicarse en varias
   pasadas y promediar.

> Criterio de acierto para agregaciones: la respuesta se considera correcta si el
> **valor** coincide con el de una consulta directa a la base de datos (margen de
> redondeo razonable) y la **interpretación** de la pregunta es la adecuada.

## 5. Análisis y herramienta

Los datos se procesan con [`plantillas/chatbot_score.py`](./plantillas/chatbot_score.py)
(sin dependencias externas):

```bash
python3 docs/plantillas/chatbot_score.py docs/plantillas/chatbot_respuestas_ejemplo.csv
```

Calcula la exactitud global, la compara con la meta de H3 (≥ 85 %) y desglosa el
acierto por categoría para localizar dónde falla el asistente.

### 5.1. Ejemplo de salida (datos ilustrativos, no reales)

Con el archivo de ejemplo ([`plantillas/chatbot_respuestas_ejemplo.csv`](./plantillas/chatbot_respuestas_ejemplo.csv)):

```
EXACTITUD DEL ASISTENTE CONVERSACIONAL (H3)
============================================================
Preguntas evaluadas : 50
Aciertos            : 46
Exactitud global    : 92.0 %
Meta H3             : >= 85 %  ->  CUMPLE
------------------------------------------------------------
Por categoría:
  alertas                      5/5  (100 %)
  cuello_botella               3/4  (75 %)
  fuera_alcance                2/2  (100 %)
  maquina                      6/6  (100 %)
  oee                          5/6  (83 %)
  orden                        6/6  (100 %)
  produccion                   6/7  (86 %)
  scrap                        4/5  (80 %)
  wip                          4/4  (100 %)
  yield                        5/5  (100 %)
```

> Estos valores son ficticios y sirven para validar el instrumento y la
> calculadora. La exactitud real se obtendrá al aplicar el protocolo contra el
> asistente con datos de la planta.

## 6. Limitaciones

- La calificación de "correcta" tiene un componente de juicio del evaluador; el
  doble evaluador y el criterio de valor-contra-BD lo acotan, pero no lo
  eliminan.
- El modo *fallback* (sin `ANTHROPIC_API_KEY`) cubre un subconjunto de
  intenciones por heurística de palabras clave; su exactitud esperada es menor a
  la del modo LLM y debe reportarse por separado si se evalúa.
- El protocolo de 50 preguntas es representativo pero no exhaustivo del lenguaje
  natural posible; mide cobertura de las capacidades implementadas, no toda
  consulta concebible.

## 7. Reproducibilidad

El protocolo y la calculadora viven en [`docs/plantillas/`](./plantillas/). La
calculadora es determinista y no requiere instalación: basta el Python del
sistema (`python3`).
