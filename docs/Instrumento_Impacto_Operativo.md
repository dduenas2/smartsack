# Instrumento de evaluación de impacto operativo

**Proyecto:** SmartSack · **Entregable:** E7 (validación con usuarios) ·
**Tipo:** medición pre/post intra-sujeto + encuesta de satisfacción

Este instrumento mide el **impacto operativo** de SmartSack: cuánto se reduce el
tiempo necesario para obtener información de producción frente al método
tradicional, y qué tan satisfechos quedan los usuarios.

---

## 1. Objetivo

Cuantificar la mejora que aporta SmartSack en la **rapidez de acceso a la
información operativa** y en la **satisfacción** de operarios y supervisores,
comparando el método tradicional (ERP transaccional, llamadas telefónicas,
recorrido físico a la planta) con el uso de SmartSack (Digital Twin, dashboard
de KPIs y asistente conversacional).

## 2. Variables e indicadores

| Variable | Indicador | Instrumento |
|---|---|---|
| Tiempo de acceso a la información | Segundos para obtener un dato operativo | Cronometraje pre/post por tarea |
| Eficiencia operativa | Reducción porcentual del tiempo (antes → después) | Cálculo derivado |
| Satisfacción del usuario | Puntaje Likert 1–5 sobre utilidad e impacto percibidos | Encuesta de satisfacción |

## 3. Diseño de la medición

Se emplea un diseño **pre/post intra-sujeto** (cada participante es su propio
control): para cada tarea representativa se mide el tiempo con el método
tradicional ("antes") y con SmartSack ("después"). Esto aísla el efecto de la
herramienta y reduce la variabilidad entre personas.

Se recomienda **al menos 3 mediciones por tarea** (distintos participantes o
repeticiones) para estabilizar las medias.

## 4. Tareas representativas medidas

Cada tarea corresponde a una necesidad de información real en el piso de planta.
El "método antes" describe cómo se resolvía sin SmartSack.

| Tarea | Método antes (tradicional) | Con SmartSack |
|---|---|---|
| Estado y avance de una máquina | Recorrido físico o llamada al operario | Vista de operario / Digital Twin |
| Cola de órdenes pendientes | Consulta al ERP o al planificador | Vista de operario |
| Órdenes retrasadas del día | Exportar y filtrar reporte del ERP | Pregunta al chatbot / dashboard |
| Máquina detenida y su causa | Llamada o recorrido a la línea | Mapa de planta (Digital Twin) |
| OEE / cumplimiento del turno | Armar el cálculo manualmente en Excel | Dashboard de KPIs |
| Consumo de material de una orden | Consulta al ERP de inventarios | Detalle de orden en SmartSack |

## 5. Protocolo de cronometraje

1. **Preparación:** entorno con datos de demostración representativos; un
   cronómetro; la ficha de captura ([`plantillas/impacto_tiempos_plantilla.csv`](./plantillas/impacto_tiempos_plantilla.csv)).
2. **Medición "antes":** se pide al participante resolver la tarea con su método
   habitual (sin SmartSack). Se cronometra desde que se formula la necesidad
   hasta que obtiene el dato. Se registra en `tiempo_antes_seg`.
3. **Medición "después":** se pide la misma tarea usando SmartSack. Se cronometra
   igual y se registra en `tiempo_despues_seg`.
4. **Repetición:** se repite por cada tarea y participante, anotando el rol.

> Para tareas cuyo método tradicional es inviable de cronometrar en el momento
> (p. ej. esperar un reporte del ERP), se admite una **estimación validada** con
> el personal, dejándolo documentado.

## 6. Encuesta de satisfacción

Tras la sesión, cada participante responde 5 afirmaciones en escala Likert de
1 (Totalmente en desacuerdo) a 5 (Totalmente de acuerdo)
([`plantillas/impacto_satisfaccion_plantilla.csv`](./plantillas/impacto_satisfaccion_plantilla.csv)):

| # | Afirmación |
|---|---|
| S1 | Con SmartSack obtengo la información que necesito más rápido que antes. |
| S2 | La información que muestra SmartSack es confiable y está actualizada. |
| S3 | SmartSack mejora la comunicación entre áreas (operario, supervisor, despacho). |
| S4 | El asistente conversacional me resulta útil para consultar el estado de producción. |
| S5 | En general estoy satisfecho/a con SmartSack y lo recomendaría. |

## 7. Análisis y herramienta

Los datos se procesan con [`plantillas/impacto_score.py`](./plantillas/impacto_score.py)
(sin dependencias externas):

```bash
python3 docs/plantillas/impacto_score.py docs/plantillas/impacto_tiempos_ejemplo.csv \
    --satisfaccion docs/plantillas/impacto_satisfaccion_ejemplo.csv
```

Calcula, por tarea y global: media del tiempo antes y después, reducción
absoluta y porcentual, y el factor de aceleración; y para la satisfacción: media
por ítem y media global.

### 7.1. Ejemplo de salida (datos ilustrativos, no reales)

Con los archivos de ejemplo (`impacto_tiempos_ejemplo.csv`,
`impacto_satisfaccion_ejemplo.csv`):

```
IMPACTO EN TIEMPO DE ACCESO A LA INFORMACIÓN
Tarea                                     n  Antes(s) Después(s)  Reduc.
Estado y avance de una máquina            3       177          8     95%
Cola de órdenes pendientes                3       150          7     95%
Órdenes retrasadas del día                3       600         12     98%
Máquina detenida y su causa               3       240         10     96%
OEE / cumplimiento del turno              3       900          6     99%
Consumo de material de una orden          3       303         15     95%
GLOBAL                                   18       395         10     97%

Reducción media del tiempo: 97% (395s → 10s, ≈ 40× más rápido).

SATISFACCIÓN PERCIBIDA (Likert 1-5)   ·   N = 10
  S1 4.70  S2 4.40  S3 4.50  S4 4.20  S5 4.70
Satisfacción media global: 4.50/5 (90%)
```

> Estos valores son ficticios y sirven para validar el instrumento y la
> calculadora. Los resultados reales se obtendrán al aplicar el protocolo a los
> participantes de la planta.

## 8. Limitaciones

- El "tiempo antes" de algunas tareas se basa en estimaciones validadas con el
  personal cuando su cronometraje directo no es viable.
- La muestra es pequeña y por conveniencia; los resultados son indicativos del
  impacto, no generalizables estadísticamente a toda la industria.
- El efecto novedad puede influir en la satisfacción inicial; se sugiere una
  medición de seguimiento tras varias semanas de uso.

## 9. Reproducibilidad

Todos los archivos viven en [`docs/plantillas/`](./plantillas/). La calculadora
es determinista y no requiere instalación: basta el Python del sistema
(`python3`).
