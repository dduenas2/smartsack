# Informe de validación — Motor de predicción de retrasos

**Proyecto:** SmartSack · **Entregable:** E7 (validación del modelo de Machine
Learning) · **Modelo evaluado:** `delay-xgb-20260621043455`

> Las cifras de este informe se generan de forma reproducible y quedan
> registradas en `backend/ml/models/delay_predictor.manifest.json`. El dataset
> se documenta en [`DATASET.md`](./DATASET.md).

---

## 1. Objetivo y alcance

Evaluar la capacidad del motor de analítica predictiva de SmartSack para
**anticipar si una orden de producción terminará retrasada**, a partir de sus
características conocidas en el momento de la planificación. La predicción
alimenta el sistema de alertas proactivas del dashboard de supervisión.

Se trata de un problema de **clasificación binaria supervisada**:

- Clase positiva (`is_delayed = 1`): la orden termina retrasada.
- Clase negativa (`is_delayed = 0`): la orden termina a tiempo.

## 2. Datos

| Concepto | Valor |
|---|---|
| Órdenes etiquetables (con `actual_end`) | 783 |
| Positivos (retrasadas) | 239 (30,5 %) |
| Negativos (a tiempo) | 544 (69,5 %) |
| Partición entrenamiento / test | 80 % / 20 %, **estratificada** |
| Test: total / positivos / negativos | 157 / 48 / 109 |

La definición de la etiqueta y de las 11 variables predictoras está centralizada
en `ml/features.py` (única fuente de verdad para entrenamiento, notebook e
inferencia). Las tasas históricas de retraso usan un *join as-of* que sólo
observa el pasado de cada orden, evitando fuga temporal (*data leakage*).

**Etiqueta:** `is_delayed = 1` si el status es `DELAYED` **o** si `actual_end`
supera `planned_end` en más de 1 h (tolerancia operativa).

**Variables (11):**
- *Numéricas:* `quantity_ordered`, `planned_duration_hours`, `hour_of_day`,
  `day_of_week`, `is_weekend`, `machine_concurrent_load`,
  `machine_delay_rate_30d`, `product_delay_rate_30d`.
- *Categóricas (one-hot, vocabulario fijo):* `product_type`, `machine_code`,
  `shift`, `priority`.

## 3. Metodología

Se entrenaron y compararon **dos algoritmos de ensamble**, estándar de la
industria para datos tabulares:

1. **Random Forest** (`scikit-learn`)
2. **Gradient Boosting** (`XGBoost`)

**Selección de hiperparámetros:** `GridSearchCV` con **validación cruzada
estratificada de 5 particiones** (`StratifiedKFold`), optimizando **F1** (la
métrica adecuada ante el desbalance de clases). Espacios de búsqueda:

| Modelo | Combinaciones | Hiperparámetros explorados |
|---|---|---|
| Random Forest | 18 | `n_estimators` {120, 240}, `max_depth` {None, 12, 20}, `min_samples_leaf` {1, 2, 4}, `class_weight=balanced` |
| XGBoost | 48 | `n_estimators` {200, 400}, `max_depth` {3, 5, 7}, `learning_rate` {0.05, 0.1}, `subsample` {0.8, 1.0}, `colsample_bytree` {0.8, 1.0} |

El mejor estimador de cada algoritmo se re-entrena sobre todo el conjunto de
entrenamiento y se evalúa **una sola vez** sobre el conjunto de test retenido,
con umbral de decisión 0,5. El modelo ganador se elige por F1 en test.

**Hiperparámetros ganadores:**
- *XGBoost:* `max_depth=3`, `n_estimators=200`, `learning_rate=0.05`,
  `subsample=0.8`, `colsample_bytree=1.0`.
- *Random Forest:* `max_depth=12`, `n_estimators=120`, `min_samples_leaf=4`,
  `class_weight=balanced`.

## 4. Resultados

### 4.1. Métricas comparativas (conjunto de test)

| Métrica | **XGBoost (ganador)** | Random Forest |
|---|---|---|
| F1-score | **0,592** | 0,556 |
| AUC-ROC | **0,837** | 0,795 |
| Precisión | 0,580 | 0,595 |
| Recall (sensibilidad) | **0,604** | 0,521 |
| F1 en validación cruzada (5-fold) | 0,583 | 0,568 |

La cercanía entre el F1 de validación cruzada (0,583) y el de test (0,592)
indica que el modelo **no presenta sobreajuste**: generaliza de forma estable a
datos no vistos.

### 4.2. Matriz de confusión (XGBoost, umbral 0,5)

|  | Predicho: a tiempo | Predicho: retraso |
|---|---|---|
| **Real: a tiempo** | 88 (VN) | 21 (FP) |
| **Real: retraso** | 19 (FN) | 29 (VP) |

Métricas derivadas:

- **Exactitud (accuracy):** (88 + 29) / 157 = **74,5 %**
- **Especificidad:** 88 / 109 = **80,7 %**
- **Recall (retrasos detectados):** 29 / 48 = **60,4 %**
- **Precisión (alertas acertadas):** 29 / 50 = **58,0 %**

Lectura operativa: el modelo **detecta 6 de cada 10 órdenes que se retrasarán**,
y cuando emite una alerta acierta el 58 % de las veces. Un AUC-ROC de 0,84
confirma una buena capacidad de discriminación independiente del umbral.

## 5. Interpretabilidad (importancia de variables)

Importancias del modelo ganador (XGBoost), ordenadas:

| # | Variable | Importancia |
|---|---|---|
| 1 | `quantity_ordered` | 0,110 |
| 2 | `product_type = Saco fertilizante 25kg` | 0,090 |
| 3 | `priority = high` | 0,079 |
| 4 | `hour_of_day` | 0,070 |
| 5 | `machine_code = FON-01` | 0,068 |
| 6 | `product_delay_rate_30d` | 0,063 |
| 7 | `day_of_week` | 0,059 |
| 8 | `product_type = Saco cemento 50kg` | 0,058 |
| 9 | `priority = normal` | 0,053 |
| 10 | `product_type = Saco harina 50kg` | 0,049 |

Las variables más influyentes son **coherentes con el conocimiento del dominio**:
el tamaño del lote, los productos técnicamente más complejos (fertilizante
laminado, cemento 50 kg), la prioridad, la hora/turno y la propensión histórica
del producto y la máquina. Esto valida que el modelo aprende **relaciones
causales plausibles** y no artefactos espurios.

## 6. Análisis crítico

**Fortalezas**
- AUC-ROC de 0,84: buena discriminación entre clases.
- Sin sobreajuste (CV ≈ test).
- Importancias interpretables y alineadas con el dominio.
- Pipeline reproducible y versionado (manifest JSON).

**Limitaciones**
- Datos sintéticos (ver justificación en `DATASET.md`): las métricas serán
  re-validadas cuando se disponga de exportaciones reales del ERP.
- Desbalance de clases (30,5 % positivos): mitigado con `class_weight=balanced`
  (RF) y la optimización por F1, pero limita la precisión alcanzable.
- Umbral fijo en 0,5: ajustarlo permitiría priorizar recall (detectar más
  retrasos a costa de más falsas alertas) según la tolerancia operativa.

**Trabajo futuro**
- Calibración de probabilidades y ajuste del umbral por análisis costo-beneficio.
- Re-entrenamiento periódico con datos reales y monitoreo de *drift*.
- Predicción de la *magnitud* del retraso (regresión) además de su ocurrencia.

## 7. Conclusión

El motor de predicción de retrasos de SmartSack alcanza un **AUC-ROC de 0,84 y
un F1 de 0,59** sobre datos no vistos, con un comportamiento estable y
explicable. El modelo es **apto para alimentar el sistema de alertas
proactivas** del dashboard de supervisión, y su pipeline reproducible permite
re-evaluarlo de inmediato sobre datos reales del ERP cuando estén disponibles.

## 8. Reproducibilidad

```bash
docker compose exec backend python -m scripts.seed --reset   # dataset determinista
docker compose exec backend python -m ml.train               # entrena + escribe manifest
```

Las métricas quedan en `backend/ml/models/delay_predictor.manifest.json`
(`RANDOM_SEED = 42`, `test_size = 0.2`, `random_state = 42`).
