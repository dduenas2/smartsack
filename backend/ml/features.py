"""
Feature engineering compartido entre el entrenamiento (`ml/train.py`),
el notebook (`ml/notebooks/delay_prediction.ipynb`) y el servicio de
inferencia (`app/services/prediction_service.py`).

Definiciones:

  Etiqueta (target):
    `is_delayed = 1` si la orden quedó marcada como DELAYED en BD
    *o* si su `actual_end` superó `planned_end` por más de
    `DELAY_TOLERANCE_HOURS` horas. Esta etiqueta sólo está disponible
    cuando la orden ya terminó (`actual_end IS NOT NULL`).

  Features (las 11 columnas que entran al modelo):
    Numéricas:
      - quantity_ordered
      - planned_duration_hours
      - hour_of_day
      - day_of_week
      - is_weekend
      - machine_concurrent_load   # cuántas órdenes en la misma máquina con planned_start ≤ ts ≤ planned_end
      - machine_delay_rate_30d    # tasa histórica de retraso de la máquina (últimos 30d hasta planned_start)
      - product_delay_rate_30d    # tasa histórica de retraso del producto (últimos 30d hasta planned_start)
    Categóricas (one-hot):
      - product_type
      - machine_code
      - shift  (turno_1 / turno_2 / turno_3 según hora de planned_start)
      - priority

El módulo expone `build_feature_frame()` que devuelve un DataFrame ya
preparado (incluye one-hot) y la lista de columnas usadas, además de
`extract_label()` para el target.

Decisiones explícitas:
- La codificación one-hot se define con un *vocabulario fijo* (ver
  CATEGORICAL_VOCAB) para que el frame de inferencia tenga exactamente
  las mismas columnas que el frame de entrenamiento. Cualquier valor
  desconocido en inferencia se mapea a "_UNK".
- Las tasas históricas se calculan con un join "as-of": para cada orden
  miramos sólo órdenes con `actual_end < planned_start` de la orden
  predicha → no hay leakage temporal.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Machine,
    OrderPriority,
    OrderStatus,
    ProductionOrder,
)


# Tolerancia: una orden que terminó 1h después de planned_end NO se
# considera retraso (variabilidad operativa esperada).
DELAY_TOLERANCE_HOURS = 1.0

# Ventana para calcular tasas históricas de retraso.
HISTORY_WINDOW_DAYS = 30

# Vocabularios fijos para one-hot. Mantener ordenados para reproducibilidad.
CATEGORICAL_VOCAB: Dict[str, List[str]] = {
    "product_type": [
        "Saco cemento 50kg",
        "Saco cemento 25kg",
        "Saco cal 25kg",
        "Saco fertilizante 25kg",
        "Saco harina 50kg",
        "_UNK",
    ],
    "machine_code": [
        "TUB-01", "TUB-02",
        "IMP-01", "IMP-02",
        "FON-01", "FON-02",
        "EMP-01", "EMP-02",
        "_UNK",
    ],
    "shift": ["turno_1", "turno_2", "turno_3"],
    "priority": ["low", "normal", "high", "urgent"],
}

# Orden canónico de columnas numéricas.
NUMERIC_COLUMNS: List[str] = [
    "quantity_ordered",
    "planned_duration_hours",
    "hour_of_day",
    "day_of_week",
    "is_weekend",
    "machine_concurrent_load",
    "machine_delay_rate_30d",
    "product_delay_rate_30d",
]


# -----------------------------------------------------------------------------
# Utilidades
# -----------------------------------------------------------------------------
def _shift_for_hour(hour: int) -> str:
    """Asigna turno por hora del planned_start."""
    if 6 <= hour < 14:
        return "turno_1"
    if 14 <= hour < 22:
        return "turno_2"
    return "turno_3"


def _onehot(series: pd.Series, prefix: str, vocabulary: List[str]) -> pd.DataFrame:
    """One-hot determinista contra un vocabulario fijo."""
    s = series.where(series.isin(vocabulary), other="_UNK" if "_UNK" in vocabulary else vocabulary[-1])
    cols = {f"{prefix}__{v}": (s == v).astype(np.int8) for v in vocabulary}
    return pd.DataFrame(cols, index=series.index)


# -----------------------------------------------------------------------------
# Carga del dataset desde la BD
# -----------------------------------------------------------------------------
def load_orders_dataframe(db: Session, *, only_labeled: bool = True) -> pd.DataFrame:
    """
    Trae todas las órdenes con sus campos planos + machine_code joined.

    Si `only_labeled` es True, sólo devuelve órdenes con `actual_end IS NOT NULL`
    (las únicas etiquetables). Para inferencia se usa False y se filtra después.
    """
    stmt = select(
        ProductionOrder.id,
        ProductionOrder.order_number,
        ProductionOrder.product_type,
        ProductionOrder.quantity_ordered,
        ProductionOrder.machine_id,
        Machine.code.label("machine_code"),
        ProductionOrder.status,
        ProductionOrder.priority,
        ProductionOrder.planned_start,
        ProductionOrder.planned_end,
        ProductionOrder.actual_start,
        ProductionOrder.actual_end,
    ).join(Machine, Machine.id == ProductionOrder.machine_id, isouter=True)

    if only_labeled:
        stmt = stmt.where(ProductionOrder.actual_end.is_not(None))

    rows = db.execute(stmt).all()
    df = pd.DataFrame([dict(r._mapping) for r in rows])
    if df.empty:
        return df

    # Normalizar enums a strings.
    df["status"] = df["status"].apply(lambda s: s.value if hasattr(s, "value") else s)
    df["priority"] = df["priority"].apply(lambda s: s.value if hasattr(s, "value") else s)

    # Asegurar tipos datetime.
    for col in ("planned_start", "planned_end", "actual_start", "actual_end"):
        df[col] = pd.to_datetime(df[col], utc=True, errors="coerce")
    return df


# -----------------------------------------------------------------------------
# Etiqueta
# -----------------------------------------------------------------------------
def extract_label(df: pd.DataFrame) -> pd.Series:
    """
    Construye la etiqueta `is_delayed`.

    Una orden es positiva si:
      · su status es DELAYED, o
      · actual_end > planned_end + DELAY_TOLERANCE_HOURS.

    Devuelve `pd.Series` de int8 con índice = índice de `df`.
    """
    if df.empty:
        return pd.Series(dtype=np.int8, name="is_delayed")
    status_delayed = df["status"].astype(str) == OrderStatus.DELAYED.value
    overruns = (df["actual_end"] - df["planned_end"]).dt.total_seconds() / 3600.0 > DELAY_TOLERANCE_HOURS
    label = (status_delayed | overruns.fillna(False)).astype(np.int8)
    label.name = "is_delayed"
    return label


# -----------------------------------------------------------------------------
# Cálculos derivados (concurrencia y tasas históricas)
# -----------------------------------------------------------------------------
def _compute_concurrent_load(df: pd.DataFrame) -> pd.Series:
    """
    Para cada orden, cuenta órdenes EN LA MISMA MÁQUINA cuyo intervalo
    [planned_start, planned_end] solapa con `planned_start` de la orden.

    Implementación O(N²) por máquina pero con ~4000 filas es instantáneo.
    """
    out = pd.Series(0, index=df.index, dtype=np.int32)
    for code, grp in df.groupby("machine_code", dropna=True):
        starts = grp["planned_start"].values
        ends = grp["planned_end"].values
        for idx, ts in zip(grp.index, starts):
            # Concurrentes: starts <= ts <= ends, excluyéndose a sí misma.
            mask = (starts <= ts) & (ends >= ts)
            out.loc[idx] = int(mask.sum() - 1)
    return out.clip(lower=0)


# NOTA: la versión simétrica anterior se reemplazó por `_history_rate_against`
# para evitar leakage en setups con history ≠ target. Se mantiene la firma por
# si algún test antiguo la usa.


# -----------------------------------------------------------------------------
# Frame de features
# -----------------------------------------------------------------------------
def build_feature_frame(
    df: pd.DataFrame,
    *,
    label_for_history: Optional[pd.Series] = None,
    history_df: Optional[pd.DataFrame] = None,
    history_label: Optional[pd.Series] = None,
) -> Tuple[pd.DataFrame, List[str]]:
    """
    Construye la matriz de features X.

    Parámetros:
      df                : orders a featurizar (puede tener actual_end null en inferencia).
      label_for_history : etiqueta del MISMO `df` (sólo útil cuando entrenamos sobre todo el set).
      history_df        : conjunto de órdenes históricas (etiquetadas) que se usa para
                          calcular las tasas de retraso. Cuando entrenamos = df. En
                          inferencia sobre órdenes activas = el dataset etiquetado.
      history_label     : etiqueta correspondiente a `history_df`.

    Devuelve `(X, columnas)`. Las columnas siempre vienen en el mismo orden,
    independiente del valor de los datos, gracias a CATEGORICAL_VOCAB.
    """
    if df.empty:
        return pd.DataFrame(), []

    # Si no se pasó historial explícito, usamos el mismo df (caso entrenamiento).
    if history_df is None:
        history_df = df
    if history_label is None:
        history_label = label_for_history if label_for_history is not None else extract_label(history_df)

    base = pd.DataFrame(index=df.index)
    base["quantity_ordered"] = df["quantity_ordered"].astype(np.int32)

    duration_h = (df["planned_end"] - df["planned_start"]).dt.total_seconds() / 3600.0
    base["planned_duration_hours"] = duration_h.fillna(0).astype(np.float32)

    base["hour_of_day"] = df["planned_start"].dt.hour.fillna(0).astype(np.int8)
    base["day_of_week"] = df["planned_start"].dt.dayofweek.fillna(0).astype(np.int8)
    base["is_weekend"] = (base["day_of_week"] >= 5).astype(np.int8)

    base["machine_concurrent_load"] = _compute_concurrent_load(df).astype(np.int32)

    # Tasas históricas: usan history_df, NO df. Para que cada fila i mire al pasado
    # tomamos las planned_start del df actual y comparamos contra actual_end del histórico.
    base["machine_delay_rate_30d"] = _history_rate_against(
        df, history_df, history_label, group_col="machine_code"
    ).astype(np.float32)
    base["product_delay_rate_30d"] = _history_rate_against(
        df, history_df, history_label, group_col="product_type"
    ).astype(np.float32)

    # Categóricas → derivar shift.
    shift_series = df["planned_start"].dt.hour.fillna(0).astype(int).map(_shift_for_hour)
    cat_blocks: List[pd.DataFrame] = []
    cat_blocks.append(_onehot(df["product_type"].astype(str), "product_type", CATEGORICAL_VOCAB["product_type"]))
    cat_blocks.append(_onehot(df["machine_code"].astype(str), "machine_code", CATEGORICAL_VOCAB["machine_code"]))
    cat_blocks.append(_onehot(shift_series, "shift", CATEGORICAL_VOCAB["shift"]))
    cat_blocks.append(_onehot(df["priority"].astype(str), "priority", CATEGORICAL_VOCAB["priority"]))

    X = pd.concat([base[NUMERIC_COLUMNS]] + cat_blocks, axis=1)
    return X, list(X.columns)


def _history_rate_against(
    target_df: pd.DataFrame,
    history_df: pd.DataFrame,
    history_label: pd.Series,
    *,
    group_col: str,
) -> pd.Series:
    """
    Versión asimétrica: cada fila i de `target_df` mira hacia atrás contra
    `history_df` para calcular la tasa histórica de retraso.
    """
    base_rate = float(history_label.mean()) if len(history_label) else 0.0
    if history_df.empty or target_df.empty:
        return pd.Series(base_rate, index=target_df.index, dtype=np.float32)

    h_actual_end = history_df["actual_end"].values
    h_group = history_df[group_col].fillna("_UNK").values
    h_label = history_label.values.astype(bool)

    window = pd.Timedelta(days=HISTORY_WINDOW_DAYS).to_timedelta64()

    target_starts = target_df["planned_start"].values
    target_groups = target_df[group_col].fillna("_UNK").values

    rates = np.full(len(target_df), base_rate, dtype=np.float64)
    for idx_pos, (t_i, g_i) in enumerate(zip(target_starts, target_groups)):
        if pd.isna(t_i):
            continue
        lower = t_i - window
        same_group = h_group == g_i
        in_window = (h_actual_end < t_i) & (h_actual_end >= lower) & ~pd.isna(h_actual_end)
        mask = same_group & in_window
        n = int(mask.sum())
        if n >= 5:
            rates[idx_pos] = float(h_label[mask].mean())
    return pd.Series(rates.astype(np.float32), index=target_df.index)


# -----------------------------------------------------------------------------
# Helper de alto nivel
# -----------------------------------------------------------------------------
def build_training_dataset(
    db: Session,
) -> Tuple[pd.DataFrame, pd.Series, List[str]]:
    """Carga + featuriza + etiqueta. Atajo para `train.py`."""
    df = load_orders_dataframe(db, only_labeled=True)
    y = extract_label(df)
    X, cols = build_feature_frame(df, label_for_history=y)
    return X, y, cols


def build_inference_dataset(
    db: Session,
    *,
    target_orders: pd.DataFrame,
) -> Tuple[pd.DataFrame, List[str]]:
    """
    Featuriza un conjunto de órdenes para inferencia, usando como histórico
    todas las órdenes etiquetables disponibles en BD. Garantiza que las
    columnas resultantes sean idénticas a las del entrenamiento.
    """
    history_df = load_orders_dataframe(db, only_labeled=True)
    history_label = extract_label(history_df)
    X, cols = build_feature_frame(
        target_orders,
        history_df=history_df,
        history_label=history_label,
    )
    return X, cols
