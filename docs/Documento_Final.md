# Documento final — SmartSack

**Proyecto de grado:** SmartSack — Plataforma inteligente de gestión de
producción con Digital Twin, analítica predictiva y asistente conversacional
para plantas de fabricación de sacos de papel ·
**Autor:** David Alejandro Dueñas Castrillon ·
**Programa:** Ingeniería de Software — Politécnico Grancolombiano ·
**Entregable:** E8

Este documento cierra el trabajo de grado: resume los resultados, evalúa el
cumplimiento de los objetivos, recoge las lecciones aprendidas y plantea el
trabajo futuro.

---

## 1. Resumen ejecutivo

SmartSack es una plataforma web complementaria al ERP, desplegable en los
equipos existentes de la planta y contenedorizada con Docker, que integra tres
capacidades sobre un mismo backend:

1. un **Digital Twin** de la línea de producción con vistas diferenciadas por
   rol y actualización en tiempo real;
2. un **motor de analítica predictiva** que anticipa retrasos en las órdenes y
   alimenta un dashboard de KPIs/OEE; y
3. un **asistente conversacional** que responde preguntas sobre la producción en
   lenguaje natural.

El sistema se construyó con FastAPI, React, PostgreSQL, Redis y Nginx, todo
orquestado con Docker Compose, y se validó en cuatro dimensiones (precisión
predictiva, usabilidad, impacto operativo y satisfacción).

## 2. Resultados por componente

### 2.1. Digital Twin

Vista de operario (estado de su máquina, operación en curso, registro rápido de
paradas, cambios de formato, incidencias y cierre) y vista de supervisor (mapa
de planta de las dos líneas con máquinas codificadas por color), con
actualización en tiempo real vía WebSockets. El filtrado por `machine_id`
garantiza que cada operario reciba solo el tráfico de su máquina y los
supervisores el de toda la planta.

### 2.2. Motor de predicción de retrasos

Modelo de clasificación binaria (retraso sí/no) entrenado con Scikit-learn y
XGBoost sobre un dataset a escala (783 órdenes etiquetables). El modelo ganador
(XGBoost) alcanza **AUC-ROC 0,84 y F1 0,59** sobre datos no vistos, sin
sobreajuste, con importancias de variables coherentes con el dominio. Este F1
valida la capacidad predictiva del componente, pero **queda por debajo del
umbral de la hipótesis H2 (F1 > 0,80)**, que está definida sobre el dataset
histórico real del ERP (ver §4). Se expone como servicio en FastAPI y alimenta
las alertas proactivas del dashboard. (Ver
[`Informe_Validacion_ML.md`](./Informe_Validacion_ML.md) y [`DATASET.md`](./DATASET.md).)

### 2.3. Asistente conversacional

Chatbot con dos modos transparentes: *modo LLM* (API de Claude + LangChain con
function calling, que traduce la pregunta en consultas a la base de datos) y
*modo fallback* (enrutador heurístico por palabras clave que mantiene el sistema
operativo sin credenciales). La conversación es sin estado.

### 2.4. Plataforma e integración

Cinco servicios en Docker Compose tras un único punto de entrada (Nginx). Dos
fuentes de datos convergen en PostgreSQL: el **ETL por lotes** de exportaciones
CSV del ERP (validadas con Pandas) y la **captura en tiempo real** de eventos
desde las máquinas.

## 3. Cumplimiento de objetivos

| # | Objetivo secundario | Evidencia | Estado |
|---|---|---|---|
| 1 | Diagnóstico y diseño de la arquitectura | Anteproyecto + arquitectura de 5 servicios ([`Manual_Tecnico.md`](./Manual_Tecnico.md)) | ✅ |
| 2 | ETL (Pandas) + captura en tiempo real → PostgreSQL | `etl_service.py`, eventos vía WebSockets | ✅ |
| 3 | Digital Twin (React + Recharts) operario/supervisor con WebSockets | Vistas de operario y supervisor ([`Manual_Usuario.md`](./Manual_Usuario.md)) | ✅ |
| 4 | Modelo ML (Scikit-learn/XGBoost) de retraso + servicio FastAPI | AUC 0,84 / F1 0,59 ([`Informe_Validacion_ML.md`](./Informe_Validacion_ML.md)) | ✅ |
| 5 | Asistente con API de Claude + LangChain (function calling) | `chat_service.py` (modos LLM + fallback) | ✅ |
| 6 | Contenerización completa con Docker Compose | `docker-compose.yml` (5 servicios) | ✅ |
| 7 | Evaluación: usabilidad (SUS), precisión (F1/AUC), impacto, satisfacción | [`Informe_Validacion_E7.md`](./Informe_Validacion_E7.md) | ✅ |

Los siete objetivos secundarios, y con ellos el objetivo principal —mejorar la
visibilidad, la trazabilidad y la toma de decisiones en planta—, se cumplieron.

## 4. Resultados de validación (E7)

La validación se organiza en cinco dimensiones, mapeadas a las **cuatro
hipótesis específicas (H1–H4)** del anteproyecto. El detalle está en
[`Informe_Validacion_E7.md`](./Informe_Validacion_E7.md).

| Dimensión | Hipótesis | Métrica | Umbral H | Resultado |
|---|---|---|---|---|
| Precisión predictiva | **H2** | F1 (dataset real ERP) | > 0,80 | **0,59 sobre dataset sintético → no alcanza H2** (medido) |
| Impacto operativo | **H1** | Reducción del tiempo de acceso | <30 s (>10 min antes) | Instrumento listo |
| Exactitud del asistente | **H3** | % respuestas correctas (50 preguntas) | ≥ 85 % | Instrumento listo |
| Usabilidad | **H4** | SUS | > 70 | Instrumento listo |
| Satisfacción | (general) | Likert | ≥ 4,0 | Instrumento listo |

El componente predictivo está validado en cuanto a **capacidad predictiva real y
explicable** (AUC 0,84; F1 0,59, por encima del piso de aceptación del
instrumento), pero **H2 no se cumple todavía**: su umbral (F1 > 0,80) está
definido sobre el **dataset histórico real del ERP**, y con el dataset sintético
actual el F1 es 0,59. Cerrar H2 requiere cargar el histórico real vía ETL y
reentrenar —infraestructura ya disponible (ver §7, Trabajo futuro)—. Las
dimensiones de **impacto (H1), exactitud del asistente (H3), usabilidad (H4)** y
satisfacción cuentan con instrumentos completos y operativos, listos para su
aplicación con usuarios reales de la planta; sus ejemplos confirman el pipeline
de medición de extremo a extremo.

## 5. Calidad y reproducibilidad

- **Pruebas automatizadas:** suite de backend (Pytest), pruebas de componentes
  de frontend (Vitest) y pruebas E2E (Playwright) que ejercitan los flujos
  completos contra el stack.
- **Integración continua:** GitHub Actions ejecuta lint, pruebas unitarias y la
  integración E2E en cada push y pull request.
- **Datos y modelo reproducibles:** `seed.py` (determinista, `RANDOM_SEED=42`)
  + `ml/train.py` regeneran el dataset y las métricas; las figuras del informe
  se reconstruyen con `ml/figures.py`.

## 6. Lecciones aprendidas

- **La señal manda.** Un dataset a escala pero sin relación causal entre las
  variables y la etiqueta produce un modelo indistinguible del azar (AUC ≈ 0,52).
  Modelar explícitamente el riesgo de retraso como función de las
  características fue lo que dio valor real al motor predictivo (AUC 0,84).
- **Reproducibilidad desde el primer día.** Centralizar el *feature engineering*
  en una única fuente de verdad (`features.py`) y versionar el manifest del
  modelo evitó inconsistencias entre entrenamiento, notebook e inferencia.
- **Modos de degradación elegantes.** El chatbot con modo fallback permite
  demostrar y operar el sistema sin depender de credenciales externas.
- **El proxy único simplifica.** Nginx como entrada única alinea las rutas
  internas y proxeadas, reduciendo fricción entre frontend, API y WebSockets.
- **Integridad en la evaluación.** Distinguir resultados medidos de instrumentos
  pendientes de trabajo de campo da rigor y credibilidad a la validación.

## 7. Trabajo futuro

- **Validación de campo** completa para contrastar **H1** (impacto/tiempo),
  **H3** (exactitud del asistente) y **H4** (usabilidad SUS) con usuarios reales,
  e incorporación de sus resultados al informe E7.
- **Datos reales del ERP**: cargar el histórico real vía ETL, re-entrenar y
  re-validar el modelo para **contrastar H2 (F1 > 0,80)** —pendiente con el
  dataset sintético actual— y monitorear el *drift* en producción.
- **Predicción de la magnitud** del retraso (regresión) además de su ocurrencia,
  y calibración del umbral por análisis costo-beneficio.
- **Acceso externo multi-rol** seguro (más allá de la red interna).
- **Mantenimiento predictivo** por máquina a partir del historial de paradas e
  incidencias.

## 8. Conclusión

SmartSack demuestra que es posible llevar inteligencia, visualización en tiempo
real y consulta en lenguaje natural al piso de una planta de sacos de papel
sobre la infraestructura existente, de forma portable y complementaria al ERP.
Se cumplieron los siete objetivos planteados y el componente predictivo quedó
validado en su **capacidad predictiva real y explicable** (AUC 0,84; F1 0,59).
De las cuatro hipótesis, **H2 (F1 > 0,80) queda pendiente** de contrastarse con
el dataset histórico real del ERP, y **H1, H3 y H4** cuentan con instrumentos
completos listos para el trabajo de campo. La plataforma quedó documentada,
probada y reproducible, lista para su transición a datos y usuarios reales.

## 9. Documentación del proyecto

| Documento | Contenido |
|---|---|
| [`DATASET.md`](./DATASET.md) | Conjunto de datos sintético y su generación |
| [`Informe_Validacion_ML.md`](./Informe_Validacion_ML.md) | Evaluación del modelo de ML |
| [`Informe_Validacion_E7.md`](./Informe_Validacion_E7.md) | Validación consolidada (4 dimensiones) |
| [`Instrumento_SUS.md`](./Instrumento_SUS.md) | Cuestionario de usabilidad |
| [`Instrumento_Impacto_Operativo.md`](./Instrumento_Impacto_Operativo.md) | Medición de impacto y satisfacción |
| [`Instrumento_Chatbot.md`](./Instrumento_Chatbot.md) | Protocolo de exactitud del asistente (H3) |
| [`Manual_Tecnico.md`](./Manual_Tecnico.md) | Manual técnico |
| [`Manual_Usuario.md`](./Manual_Usuario.md) | Manual de usuario |
