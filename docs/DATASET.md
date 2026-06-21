# Conjunto de datos de SmartSack

Documentación del **dataset sintético realista** que alimenta a SmartSack:
modelo operativo del Digital Twin, dashboard de KPIs y, sobre todo, el motor
de analítica predictiva (predicción de retrasos).

## 1. Justificación: por qué sintético

El sistema ERP de una planta de sacos de papel es propiedad de un tercero y su
exportación contiene información comercial sensible. Para el trabajo de grado se
construyó un **dataset sintético a escala** que reproduce las distribuciones,
catálogos y dinámicas operativas reales del sector (rutas de fabricación,
turnos, rendimientos por máquina, estacionalidad de retrasos), de modo que el
sistema y el motor de ML pueden validarse de forma rigurosa y **reproducible**
sin exponer datos confidenciales. Es una práctica habitual y aceptada cuando la
fuente real es de un tercero.

El proceso ETL (`app/services/etl_service.py`) está diseñado para consumir
exportaciones CSV con el formato típico del módulo PP (Production Planning) de
SAP, por lo que la migración a datos reales del ERP consistiría únicamente en
sustituir las fuentes por las exportaciones reales con el mismo esquema.

## 2. Dos generadores, dos propósitos

| Script | Salida | Propósito |
|---|---|---|
| `scripts/seed.py` | Base de datos PostgreSQL poblada | Estado operativo + historia de 6 meses. **Es la fuente de entrenamiento del modelo ML.** |
| `scripts/generate_sample_csvs.py` | 4 CSV en `samples/` | Entradas de ejemplo para ejercitar el flujo de carga **ETL** (incluyen errores intencionales). |

Ambos comparten catálogos coherentes (productos, máquinas, turnos) con el
vocabulario de features de ML (`ml/features.py · CATEGORICAL_VOCAB`).

## 3. Volumetría (seed por defecto, `RANDOM_SEED = 42`)

Horizonte: **6 meses de historia + 30 días de planificación futura**
(rango de `planned_start`: 2025-12-23 → 2026-07-20).

| Entidad | Registros |
|---|---|
| Órdenes de producción | **918** |
| — completadas | 544 |
| — retrasadas (DELAYED) | 239 |
| — en curso | 2 |
| — pendientes (futuras) | 133 |
| Operaciones (ruta IMP→TUB→FON→EMP) | 3 672 |
| Eventos de producción | 10 373 |
| Registros OEE (máquina × turno × día) | 4 344 |
| Movimientos de material | 2 568 |
| Registros de calidad | 785 |
| Predicciones ML históricas | 126 |
| Usuarios (1 admin, 3 supervisores, 16 operarios) | 20 |
| Máquinas (2 líneas × IMP/TUB/FON/EMP) | 8 |

El subconjunto **etiquetable** para ML (órdenes con `actual_end`, es decir
completadas + retrasadas) es de **783 órdenes**, con una tasa de positivos
(retraso) del **30,5 %**.

## 4. Catálogos de dominio

- **Máquinas (8):** dos líneas paralelas (A y B), cada una con la secuencia
  Impresora (IMP) → Tubuladora (TUB) → Fondadora (FON) → Empacadora (EMP).
- **Productos (5):** Saco cemento 50 kg, Saco cemento 25 kg, Saco harina 50 kg,
  Saco fertilizante 25 kg, Saco cal 25 kg.
- **Turnos (3):** Turno 1 (06:00–14:00), Turno 2 (14:00–22:00), Turno 3
  (22:00–06:00).
- **Prioridades:** low / normal / high / urgent.

Cada orden cabecera se descompone en **4 operaciones encadenadas** con sus
propios tiempos, rendimiento (yield out/in) y desperdicio en kg (la Empacadora
no genera scrap).

## 5. Features y etiqueta del modelo ML

Definidos como única fuente de verdad en `ml/features.py`.

**Etiqueta** `is_delayed = 1` si la orden tiene status `DELAYED` **o** si
`actual_end` superó `planned_end` en más de `DELAY_TOLERANCE_HOURS` (1 h).

**11 features** (las categóricas se codifican one-hot con vocabulario fijo):

- Numéricas: `quantity_ordered`, `planned_duration_hours`, `hour_of_day`,
  `day_of_week`, `is_weekend`, `machine_concurrent_load`,
  `machine_delay_rate_30d`, `product_delay_rate_30d`.
- Categóricas: `product_type`, `machine_code`, `shift`, `priority`.

Las tasas históricas se calculan con un join *as-of* (sólo miran al pasado de
cada orden) para evitar fuga temporal (*leakage*).

## 6. Modelo de riesgo latente (la señal aprendible)

Para que el motor de ML tenga una relación real que aprender, **el retraso de
una orden no es aleatorio**: se genera como una función logística de sus
características más un término de ruido gaussiano irreducible
(`scripts/seed.py · _delay_probability`). Los coeficientes están en escala
log-odds y calibrados para una tasa global de retraso ~30 % y un AUC realista
(~0,84), no perfecto:

| Factor | Efecto sobre el riesgo |
|---|---|
| Prioridad | urgent (+1,8) y high (+1,0) elevan el riesgo; low lo baja (−0,7) |
| Producto | fertilizante 25 kg (+1,2, barrera laminada) y cemento 50 kg (+0,8) son los más propensos; cemento 25 kg lo baja (−0,6) |
| Línea | la Línea B corre más caliente (+0,6) |
| Cantidad | lotes grandes (>15 000) aumentan el riesgo proporcionalmente |
| Turno | turno noche (+0,9) y tarde (+0,3) acumulan más incidencias |
| Fin de semana | +0,8 (menos personal de soporte) |
| Ruido | `N(0, 0,3)` — variabilidad operativa no explicada |

El `actual_end` de cada orden se ajusta para ser coherente con la decisión
(las retrasadas terminan efectivamente tarde), y `machine_id` se puebla en las
órdenes históricas con la Fondadora de su línea (cuello de botella).

## 7. Resultados de validación del modelo

Tras introducir la señal latente (ver `ml/models/delay_predictor.manifest.json`):

| Modelo | F1 | AUC-ROC | Precisión | Recall |
|---|---|---|---|---|
| **XGBoost** (ganador) | **0,59** | **0,84** | 0,58 | 0,60 |
| Random Forest | 0,56 | 0,80 | 0,60 | 0,52 |

Validación cruzada estratificada 5-fold para la selección de hiperparámetros;
evaluación sobre un conjunto de test del 20 %. Las *feature importances* más
altas (cantidad, turno noche, producto fertilizante, línea, prioridad, fin de
semana) son coherentes con el modelo de riesgo, lo que confirma que el modelo
aprende los factores correctos.

> Antes de introducir la señal, el dataset asignaba el retraso con una
> probabilidad fija del 15 % sin relación con las features, y el modelo no
> superaba el azar (AUC ≈ 0,52, F1 ≈ 0,21).

## 8. Reproducibilidad

```bash
# 1. Poblar la BD (reinicia secuencias de identidad → IDs estables)
docker compose exec backend python -m scripts.seed --reset

# 2. Entrenar y evaluar (escribe joblib + manifest con las métricas)
docker compose exec backend python -m ml.train

# 3. (Opcional) Regenerar CSV de muestra del ETL a escala
docker compose exec backend python -m scripts.generate_sample_csvs --count 60
```

Con `RANDOM_SEED = 42` el dataset es determinista. `reset_database` usa
`TRUNCATE ... RESTART IDENTITY CASCADE`, de modo que cada re-seed produce los
mismos IDs (máquinas 1–8) y el mismo conjunto de datos.
