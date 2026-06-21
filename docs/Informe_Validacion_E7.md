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

La validación se estructura en cuatro dimensiones, cada una con su instrumento,
métrica y criterio de éxito:

| # | Dimensión | Instrumento | Métrica | Criterio de éxito |
|---|---|---|---|---|
| D1 | Precisión predictiva | Pipeline ML (`ml/train.py`) | AUC-ROC, F1-score | AUC ≥ 0,75 y F1 ≥ 0,50 |
| D2 | Usabilidad | Cuestionario SUS | Puntaje SUS (0–100) | Media ≥ 68 (media poblacional) |
| D3 | Impacto operativo | Cronometraje pre/post | Reducción del tiempo de acceso | Reducción ≥ 50 % |
| D4 | Satisfacción | Encuesta Likert | Puntaje medio (1–5) | Media ≥ 4,0 |

## 2. Estado de cada dimensión

- **D1 — Precisión predictiva: MEDIDA.** Evaluada sobre el dataset a escala
  (783 órdenes etiquetables), con métricas reales y reproducibles.
- **D2, D3, D4 — INSTRUMENTOS LISTOS.** Los instrumentos están diseñados,
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

## 4. Lectura conjunta

Las cuatro dimensiones cubren el objetivo de validación de forma complementaria:

- **D1** demuestra que el componente inteligente (predicción de retrasos) tiene
  capacidad predictiva real y explicable, apta para alimentar alertas
  proactivas.
- **D2** evalúa si la plataforma es fácil de usar para el personal de planta,
  condición necesaria para su adopción.
- **D3** cuantifica el beneficio tangible: la velocidad con que el personal
  accede a información que antes requería recorridos, llamadas o reportes del
  ERP.
- **D4** captura la percepción global de valor y la intención de uso.

En conjunto, responden a las tres metas del objetivo principal —mejorar la
**visibilidad**, la **trazabilidad** y la **toma de decisiones**— con evidencia
cuantitativa (D1, D3) y cualitativa/percepción (D2, D4).

## 5. Conclusión

La dimensión de **precisión predictiva está validada** con resultados que
superan los criterios de éxito (AUC 0,84; F1 0,59). Las dimensiones de
**usabilidad, impacto operativo y satisfacción** cuentan con **instrumentos
completos, documentados y operativos**, listos para su aplicación con usuarios
reales de la planta; los ejemplos incluidos confirman que el pipeline de
medición y cálculo funciona de extremo a extremo. Al completar el trabajo de
campo, sus resultados se integrarán en las tablas de la sección 3.

## 6. Documentos e instrumentos de referencia

| Dimensión | Documento | Herramienta |
|---|---|---|
| Datos | [`DATASET.md`](./DATASET.md) | `scripts/seed.py`, `scripts/generate_sample_csvs.py` |
| D1 | [`Informe_Validacion_ML.md`](./Informe_Validacion_ML.md) | `ml/train.py`, `ml/figures.py` |
| D2 | [`Instrumento_SUS.md`](./Instrumento_SUS.md) | `plantillas/sus_score.py` |
| D3 / D4 | [`Instrumento_Impacto_Operativo.md`](./Instrumento_Impacto_Operativo.md) | `plantillas/impacto_score.py` |
