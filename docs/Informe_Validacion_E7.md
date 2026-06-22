# Informe de validación de SmartSack (E7)

**Proyecto:** SmartSack · **Entregable:** E7 — Informe de validación ·
**Objetivo asociado:** Objetivo secundario 7 del anteproyecto

> *"Evaluar SmartSack mediante pruebas con usuarios reales, midiendo usabilidad
> (SUS), precisión predictiva (F1-score, AUC-ROC), impacto operativo (reducción
> de tiempo de respuesta ante consultas) y satisfacción del usuario."*

Este documento **consolida** las cuatro dimensiones de validación de SmartSack y
remite a los informes e instrumentos detallados de cada una.

---

## 1. Marco de validación

La validación se estructura en cinco dimensiones, cada una con su instrumento,
métrica y criterio de éxito:

| # | Dimensión | Instrumento | Métrica | Criterio de éxito |
|---|---|---|---|---|
| D1 | Precisión predictiva | Pipeline ML (`ml/train.py`) | AUC-ROC, F1-score | AUC ≥ 0,75 y F1 ≥ 0,50 |
| D2 | Usabilidad | Cuestionario SUS | Puntaje SUS (0–100) | Media ≥ 68 (media poblacional) |
| D3 | Impacto operativo | Cronometraje pre/post | Reducción del tiempo de acceso | Reducción ≥ 50 % |
| D4 | Satisfacción | Encuesta Likert | Puntaje medio (1–5) | Media ≥ 4,0 |
| D5 | Exactitud del asistente | Protocolo de 50 preguntas | % de respuestas correctas | ≥ 85 % |

### 1.1. Correspondencia con las hipótesis del anteproyecto

El anteproyecto formula una hipótesis general y **cuatro hipótesis específicas
(H1–H4)**, cada una con un umbral cuantitativo. Las dimensiones de validación de
este informe se corresponden con ellas como sigue. Donde el **criterio de la
dimensión** y el **umbral de la hipótesis** difieren, se reportan **ambos**: la
dimensión fija un piso de aceptación del instrumento y la hipótesis fija la meta
declarada en el anteproyecto.

| Hipótesis (anteproyecto) | Umbral H | Dimensión | Estado |
|---|---|---|---|
| **H1** — el Digital Twin reduce el tiempo de respuesta de >10 min a <30 s | <30 s (≈ 97 % de reducción) | D3 (impacto operativo) | Instrumento listo; ejemplo cumple |
| **H2** — el modelo ML logra F1 > 0,80 **sobre el dataset histórico real del ERP** | F1 > 0,80 | D1 (precisión predictiva) | **Medido sobre dataset sintético: F1 = 0,59 → NO alcanza H2** (ver §3.bis) |
| **H3** — el asistente responde correctamente ≥ 85 % del protocolo de 50 preguntas | ≥ 85 % | D5 (exactitud del asistente) | Instrumento listo; ejemplo cumple |
| **H4** — la usabilidad medida con SUS supera 70 | SUS > 70 | D2 (usabilidad) | Instrumento listo; ejemplo cumple |

La dimensión **D4 (satisfacción)** no corresponde a una hipótesis específica
numerada: sustenta de forma complementaria la **hipótesis general** (el sistema
mejora el acceso a la información y la percepción de valor del personal).

> **Nota sobre los umbrales.** D1 fija un piso propio (AUC ≥ 0,75 y F1 ≥ 0,50)
> que el modelo sí supera; ese piso valida que el componente predictivo *tiene
> señal real y explicable*. La **hipótesis H2**, en cambio, exige F1 > 0,80
> **sobre datos reales del ERP**, condición que el dataset sintético actual no
> permite alcanzar. Se mantienen separados para no presentar como cumplida una
> hipótesis que aún no lo está.

## 2. Estado de cada dimensión

- **D1 — Precisión predictiva: MEDIDA.** Evaluada sobre el dataset a escala
  (783 órdenes etiquetables), con métricas reales y reproducibles. Supera el
  criterio propio de D1 pero **no el umbral de H2** (ver §3.bis).
- **D2, D3, D4, D5 — INSTRUMENTOS LISTOS.** Los instrumentos están diseñados,
  documentados y validados con su herramienta de cálculo (probada con datos de
  ejemplo). La **aplicación a usuarios reales de la planta** es el paso de campo
  pendiente; sus resultados se incorporarán a este informe cuando se ejecuten.

> Esta distinción se hace de forma explícita por integridad académica: las cifras
> de D1 son resultados de evaluación; las de D2–D4 mostradas más abajo son
> **ejemplos ilustrativos** que demuestran el funcionamiento del instrumento.

## 3. Resultados consolidados

### D1 · Precisión predictiva — *resultado medido*

Modelo ganador **XGBoost** (ver [`Informe_Validacion_ML.md`](./Informe_Validacion_ML.md)):

| Métrica | Resultado | Criterio | Cumple |
|---|---|---|---|
| AUC-ROC | **0,84** | ≥ 0,75 | ✅ |
| F1-score | **0,59** | ≥ 0,50 | ✅ |
| Precisión | 0,58 | — | — |
| Recall | 0,60 | — | — |

Sin sobreajuste (F1 en validación cruzada ≈ F1 en test) e importancias de
variables coherentes con el dominio.

#### 3.bis · Contraste con H2 (F1 > 0,80) — *no alcanzado todavía*

El criterio de D1 se cumple, pero la **hipótesis H2 no**: H2 exige F1 > 0,80
**sobre el dataset histórico real del ERP**, y el F1 medido es **0,59** sobre el
dataset sintético a escala. Esto es coherente con lo ya anticipado en la Entrega 2,
donde se documentó que el modelo se entrenaba únicamente con datos del *seed* y
que la métrica final se contrastaría al disponer del dataset real. La brecha no
indica un defecto del modelo ni del *pipeline* (que son correctos y explicables),
sino la **ausencia de las correlaciones reales** entre carga de máquina,
prioridad, producto y retraso que un dataset sintético no reproduce en su
totalidad. **Cierre de H2:** cargar vía ETL ≥ 6 meses de histórico real del ERP,
reentrenar (`python -m ml.train`) y volver a medir; la infraestructura para
hacerlo ya está implementada (ver [`DATASET.md`](./DATASET.md) y trabajo futuro
del [`Documento_Final.md`](./Documento_Final.md)).

### D2 · Usabilidad (SUS) — *instrumento listo*

Instrumento y herramienta: [`Instrumento_SUS.md`](./Instrumento_SUS.md) ·
`plantillas/sus_score.py`. Resultado con datos de ejemplo (10 respuestas):

| Métrica | Valor (ejemplo) | Criterio | — |
|---|---|---|---|
| SUS promedio | 83,8 (Excelente, grado A) | ≥ 68 | ✅ (ejemplo) |

### D3 · Impacto operativo — *instrumento listo*

Instrumento y herramienta: [`Instrumento_Impacto_Operativo.md`](./Instrumento_Impacto_Operativo.md) ·
`plantillas/impacto_score.py`. Resultado con datos de ejemplo (18 mediciones):

| Métrica | Valor (ejemplo) | Criterio | — |
|---|---|---|---|
| Reducción media del tiempo de acceso | 97 % (≈ 40× más rápido) | ≥ 50 % | ✅ (ejemplo) |

### D4 · Satisfacción — *instrumento listo*

Encuesta incluida en el instrumento de impacto operativo. Resultado con datos de
ejemplo (10 participantes):

| Métrica | Valor (ejemplo) | Criterio | — |
|---|---|---|---|
| Satisfacción media | 4,50 / 5 (90 %) | ≥ 4,0 | ✅ (ejemplo) |

### D5 · Exactitud del asistente conversacional (H3) — *instrumento listo*

Instrumento y herramienta: [`Instrumento_Chatbot.md`](./Instrumento_Chatbot.md) ·
`plantillas/chatbot_score.py`. Protocolo cerrado de 50 preguntas estandarizadas.
Resultado con datos de ejemplo (50 preguntas evaluadas):

| Métrica | Valor (ejemplo) | Criterio | — |
|---|---|---|---|
| Exactitud global | 92,0 % (46/50) | ≥ 85 % (H3) | ✅ (ejemplo) |

## 4. Lectura conjunta

Las cinco dimensiones cubren el objetivo de validación de forma complementaria:

- **D1** demuestra que el componente inteligente (predicción de retrasos) tiene
  capacidad predictiva real y explicable, apta para alimentar alertas
  proactivas.
- **D2** evalúa si la plataforma es fácil de usar para el personal de planta,
  condición necesaria para su adopción.
- **D3** cuantifica el beneficio tangible: la velocidad con que el personal
  accede a información que antes requería recorridos, llamadas o reportes del
  ERP.
- **D4** captura la percepción global de valor y la intención de uso.
- **D5** verifica que el asistente conversacional traduce correctamente
  preguntas en lenguaje natural a datos de planta fiables (hipótesis H3).

En conjunto, responden a las tres metas del objetivo principal —mejorar la
**visibilidad**, la **trazabilidad** y la **toma de decisiones**— con evidencia
cuantitativa (D1, D3, D5) y cualitativa/percepción (D2, D4).

## 5. Conclusión

La dimensión de **precisión predictiva (D1)** está validada en cuanto a
capacidad predictiva real y explicable (AUC 0,84; F1 0,59, por encima del piso
de D1), pero **la hipótesis H2 (F1 > 0,80) no se alcanza todavía** porque
requiere el dataset histórico real del ERP (ver §3.bis): es el único contraste
de hipótesis que queda pendiente de un insumo externo. Las dimensiones de
**usabilidad (H4), impacto operativo (H1), satisfacción y exactitud del
asistente (H3)** cuentan con **instrumentos completos, documentados y
operativos**, listos para su aplicación con usuarios reales de la planta; los
ejemplos incluidos confirman que el pipeline de medición y cálculo funciona de
extremo a extremo. Al completar el trabajo de campo, sus resultados se
integrarán en las tablas de la sección 3 y permitirán contrastar formalmente
H1, H3 y H4.

## 6. Documentos e instrumentos de referencia

| Dimensión | Documento | Herramienta |
|---|---|---|
| Datos | [`DATASET.md`](./DATASET.md) | `scripts/seed.py`, `scripts/generate_sample_csvs.py` |
| D1 | [`Informe_Validacion_ML.md`](./Informe_Validacion_ML.md) | `ml/train.py`, `ml/figures.py` |
| D2 | [`Instrumento_SUS.md`](./Instrumento_SUS.md) | `plantillas/sus_score.py` |
| D3 / D4 | [`Instrumento_Impacto_Operativo.md`](./Instrumento_Impacto_Operativo.md) | `plantillas/impacto_score.py` |
| D5 | [`Instrumento_Chatbot.md`](./Instrumento_Chatbot.md) | `plantillas/chatbot_score.py` |
