# Guion de sustentación — SmartSack

**Proyecto de grado:** SmartSack · **Autor:** David Alejandro Dueñas Castrillon ·
**Entregable:** E8 (preparación de la sustentación)

Material de apoyo para la defensa: estructura de la presentación, esquema de
diapositivas con notas del orador, guion del demo en vivo y preguntas
anticipadas. Duración objetivo: **15–20 minutos** + preguntas.

---

## 1. Estructura y tiempos

| Bloque | Diapositivas | Tiempo |
|---|---|---|
| Apertura y problema | 1–3 | 3 min |
| Solución y arquitectura | 4–6 | 4 min |
| Los tres módulos | 7–9 | 4 min |
| Demo en vivo | — | 4 min |
| Validación y resultados | 10–12 | 3 min |
| Conclusiones y trabajo futuro | 13–14 | 2 min |

> Regla práctica: ~1 minuto por diapositiva. Tener el demo grabado como respaldo
> por si falla la conexión o el entorno.

## 2. Esquema de diapositivas

**D1 · Portada**
- Título, autor, programa, asesor, fecha. *(Notas: presentarse en una frase.)*

**D2 · El problema**
- Las plantas tienen ERP, pero el piso de producción carece de visibilidad en
  tiempo real, comunicación entre áreas y trazabilidad.
- *(Notas: aterrizar con un ejemplo: un supervisor que no sabe por qué una
  máquina está parada sin caminar hasta ella.)*

**D3 · Objetivo**
- Plataforma web inteligente, complementaria al ERP, sobre los equipos
  existentes, que mejore visibilidad, trazabilidad y toma de decisiones.

**D4 · Arquitectura**
- Diagrama: 5 servicios (PostgreSQL, Redis, FastAPI, React, Nginx) en Docker
  Compose; Nginx como entrada única.
- *(Notas: destacar portabilidad — un solo `docker compose up`.)*

**D5 · Dos fuentes de datos**
- ETL por lotes (CSV del ERP, validado con Pandas) + captura en tiempo real
  (eventos de máquina vía WebSockets), unificadas en PostgreSQL.

**D6 · Stack tecnológico**
- Python/FastAPI, React/Recharts/Tailwind, Scikit-learn/XGBoost, LangChain +
  API de Claude, PostgreSQL, Redis, Nginx, Docker.

**D7 · Módulo 1 — Digital Twin**
- Captura: vista de operario + mapa de planta del supervisor en tiempo real.
- *(Notas: explicar el filtrado por máquina en WebSockets.)*

**D8 · Módulo 2 — Predicción de retrasos**
- Captura: dashboard de KPIs/OEE con alertas.
- Mencionar features y etiqueta; que el modelo aprende factores de riesgo reales.

**D9 · Módulo 3 — Asistente conversacional**
- Captura: chat con preguntas de ejemplo. Dos modos (LLM / fallback).

**D10 · Validación — marco**
- Cinco dimensiones mapeadas a las hipótesis del anteproyecto: precisión (H2),
  impacto operativo (H1), exactitud del asistente (H3), usabilidad SUS (H4) y
  satisfacción (hipótesis general). Criterios y umbrales por hipótesis.

**D11 · Resultados — modelo ML**
- Curva ROC (AUC 0,84) + tabla F1/precisión/recall. Importancia de variables.
- *(Notas: subrayar que sin señal el modelo daba AUC ≈ 0,52; el aporte fue
  modelar el riesgo de retraso. Ser explícito: el F1 0,59 valida la capacidad
  predictiva pero **aún no alcanza H2 (F1>0,80)**, que exige el dataset real del
  ERP — es el único contraste de hipótesis pendiente de un insumo externo.)*

**D12 · Resultados — usabilidad, impacto y asistente**
- SUS (H4), reducción de tiempo (H1), exactitud del asistente (H3, protocolo de
  50 preguntas) y satisfacción: instrumentos listos (con ejemplos); trabajo de
  campo como siguiente paso.

**D13 · Cumplimiento de objetivos**
- Tabla: 7/7 objetivos cumplidos, con su evidencia.

**D14 · Conclusiones y trabajo futuro**
- Conclusión + líneas futuras (datos reales del ERP, validación de campo,
  mantenimiento predictivo, acceso externo).

## 3. Guion del demo en vivo (≈4 min)

Preparación previa: `docker compose up -d`, BD migrada y sembrada
(`scripts.seed --reset`), modelo entrenado (`ml.train`). Tener tres pestañas
abiertas y sesión iniciada.

1. **Operario** (`op_tub-01_1`): mostrar la estación asignada y registrar una
   parada ("Detener" → motivo). *Frase:* "esto se captura en el acto".
2. **Supervisor** (`supervisor1`, otra pestaña): mostrar cómo la máquina cambia
   de color en el Digital Twin **en tiempo real** tras la parada del operario.
3. **Dashboard:** señalar el OEE y una alerta de retraso generada por el modelo.
4. **Asistente:** preguntar *"¿qué alertas de retraso hay?"* y *"¿cuál es el
   cuello de botella de la planta?"*; mostrar la respuesta con datos reales.

> Plan B: si el demo en vivo falla, usar las capturas de
> [`Manual_Usuario.md`](./Manual_Usuario.md) o un video grabado.

## 4. Preguntas anticipadas (Q&A)

**¿Por qué datos sintéticos y no reales?**
El ERP es de un tercero con información sensible. Se construyó un dataset
sintético a escala que reproduce las dinámicas reales; el ETL está listo para
consumir las exportaciones reales con el mismo esquema cuando estén disponibles.

**¿AUC 0,84 no es "demasiado bueno" para datos sintéticos?**
Al contrario: se calibró deliberadamente con ruido para que **no** fuera
perfecto. La señal proviene de un modelo de riesgo explícito y explicable; las
importancias de variables confirman que aprende factores plausibles.

**¿Se cumplió la hipótesis H2 (F1 > 0,80)?**
Todavía no. H2 está definida sobre el dataset histórico real del ERP, y con el
dataset sintético el F1 es 0,59. Lo que sí se demuestra es que el modelo y el
pipeline tienen capacidad predictiva real y explicable (AUC 0,84, sin
sobreajuste). Cerrar H2 requiere cargar el histórico real vía el ETL ya
implementado y reentrenar; se reporta de forma transparente y queda como el
contraste pendiente. Las hipótesis H1, H3 y H4 tienen sus instrumentos listos
para el trabajo de campo.

**¿Cómo se midió la exactitud del asistente (H3)?**
Con un protocolo cerrado de 50 preguntas estandarizadas sobre datos de
producción, cada una calificada como acierto/fallo; la calculadora
`chatbot_score.py` reporta el porcentaje global y por categoría y lo contrasta
con el umbral de H3 (≥ 85 %).

**¿Cómo se evita el sobreajuste?**
Validación cruzada estratificada 5-fold para los hiperparámetros y evaluación en
un test retenido; el F1 de CV y el de test casi coinciden.

**¿Qué pasa si no hay clave de la API de Claude?**
El chatbot opera en modo fallback (heurística por palabras clave); el sistema
sigue siendo demostrable y operativo.

**¿Cómo se garantiza que un operario no vea datos de otra máquina?**
El gestor de WebSockets filtra por `machine_id`; además las rutas están
protegidas por rol con JWT.

**¿Es desplegable en una planta real?**
Sí: todo está contenedorizado; basta un equipo con Docker en la red interna.
El acceso externo multi-rol queda como trabajo futuro.

**¿Cómo se midió el impacto operativo?**
Con un diseño pre/post intra-sujeto que cronometra el tiempo de acceso a la
información antes (ERP/recorrido/llamada) y después (SmartSack), más una encuesta
de satisfacción.

## 5. Checklist final antes de la defensa

- [ ] Stack levantado y probado (`docker compose ps` todo *healthy*).
- [ ] BD sembrada y modelo entrenado.
- [ ] Sesiones de operario y supervisor abiertas en pestañas separadas.
- [ ] Video del demo como respaldo.
- [ ] Diapositivas exportadas a PDF (independiente de software).
- [ ] Repositorio accesible y README al día.
