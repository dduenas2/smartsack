"""
Servicio de predicción de retraso.

Carga lazy del modelo serializado (`ml/models/delay_predictor.joblib`) y expone:

  · predict_for_order(db, order_id)            → MLPrediction persistida
  · predict_for_active_orders(db)              → list[MLPrediction]
  · get_feature_importance()                   → dict
  · get_model_info()                           → metadata + manifest

El modelo se mantiene cacheado en memoria; `reload_model()` permite
sustituirlo sin reiniciar el proceso (útil tras un re-entrenamiento).

Decisiones:
- La predicción sobre una orden NO COMPLETED siempre persiste un nuevo
  MLPrediction (auditoría histórica). Si la orden ya está COMPLETED,
  predecir es inútil → se rechaza.
- `predicted_delay_hours` se aproxima a partir de la probabilidad y de
  la duración planificada: por ahora un proxy lineal
  `prob * 0.4 * planned_duration_h`. El modelo de regresión real
  queda fuera del alcance de la tesis.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import joblib
import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    MLPrediction,
    OrderStatus,
    ProductionOrder,
)
from ml.features import build_inference_dataset, load_orders_dataframe


logger = logging.getLogger("smartsack.prediction")

DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[2] / "ml" / "models" / "delay_predictor.joblib"
DEFAULT_MANIFEST_PATH = DEFAULT_MODEL_PATH.with_suffix(".manifest.json")


class ModelNotLoaded(RuntimeError):
    """El joblib no existe todavía. Caller debe instruir al usuario a entrenar."""


# -----------------------------------------------------------------------------
# Singleton thread-safe del modelo
# -----------------------------------------------------------------------------
class _ModelHandle:
    """Encapsula el bundle joblib + manifest. Acceso vía `get_model()`."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._bundle: Optional[Dict[str, Any]] = None
        self._manifest: Optional[Dict[str, Any]] = None
        self._loaded_at: Optional[datetime] = None

    def load(self, *, model_path: Path = DEFAULT_MODEL_PATH, manifest_path: Path = DEFAULT_MANIFEST_PATH) -> None:
        with self._lock:
            if not model_path.exists():
                raise ModelNotLoaded(
                    f"No existe {model_path}. Ejecuta `python -m ml.train` "
                    f"para entrenar y serializar el modelo."
                )
            self._bundle = joblib.load(model_path)
            self._manifest = (
                json.loads(manifest_path.read_text()) if manifest_path.exists() else None
            )
            self._loaded_at = datetime.now(tz=timezone.utc)
            logger.info(
                "Modelo cargado: %s (%d features)",
                self._bundle.get("version"), len(self._bundle.get("feature_columns", [])),
            )

    def ensure_loaded(self) -> None:
        if self._bundle is None:
            self.load()

    @property
    def bundle(self) -> Dict[str, Any]:
        self.ensure_loaded()
        return self._bundle  # type: ignore[return-value]

    @property
    def manifest(self) -> Optional[Dict[str, Any]]:
        self.ensure_loaded()
        return self._manifest

    @property
    def loaded_at(self) -> Optional[datetime]:
        return self._loaded_at


_handle = _ModelHandle()


def reload_model() -> None:
    """Fuerza recarga desde disco (útil tras un re-entrenamiento)."""
    _handle.load()


def is_model_available() -> bool:
    """True si el joblib existe en disco (sin cargarlo a memoria)."""
    return DEFAULT_MODEL_PATH.exists()


# -----------------------------------------------------------------------------
# Helpers internos
# -----------------------------------------------------------------------------
def _proba_for(orders_df: pd.DataFrame, db: Session) -> np.ndarray:
    """Featuriza y predice probabilidades para `orders_df`."""
    bundle = _handle.bundle
    expected_cols: List[str] = bundle["feature_columns"]
    model = bundle["model"]

    X, cols = build_inference_dataset(db, target_orders=orders_df)
    # Reordenar/asegurar columnas según el bundle.
    missing = [c for c in expected_cols if c not in cols]
    extra = [c for c in cols if c not in expected_cols]
    if missing:
        for c in missing:
            X[c] = 0
    if extra:
        X = X.drop(columns=extra)
    X = X[expected_cols]
    return model.predict_proba(X)[:, 1]


def _make_prediction_row(
    order: ProductionOrder, probability: float, version: str, features_used: Dict[str, Any]
) -> MLPrediction:
    duration_h = max(
        0.0,
        (order.planned_end - order.planned_start).total_seconds() / 3600.0,
    )
    # Proxy: un retraso esperado proporcional a la probabilidad y la duración planeada.
    predicted_hours = round(float(probability) * 0.4 * duration_h, 2)
    return MLPrediction(
        order_id=order.id,
        delay_probability=float(probability),
        predicted_delay_hours=predicted_hours,
        features_json=features_used,
        model_version=version,
    )


# -----------------------------------------------------------------------------
# API pública
# -----------------------------------------------------------------------------
def predict_for_order(db: Session, *, order_id: int) -> MLPrediction:
    """
    Calcula y persiste una nueva predicción para `order_id`.

    Si la orden ya está COMPLETED se lanza ValueError (predecir el pasado
    es ruido). Si no existe se lanza KeyError.
    """
    order = db.get(ProductionOrder, order_id)
    if order is None:
        raise KeyError(f"order_id={order_id}")
    if order.status == OrderStatus.COMPLETED:
        raise ValueError(f"order {order.order_number} ya está COMPLETED — no se predice")

    # Convertir la sola orden a DataFrame para reutilizar la pipeline.
    df = load_orders_dataframe(db, only_labeled=False)
    df = df[df["id"] == order.id]
    if df.empty:
        raise KeyError(f"order_id={order_id} no encontrada en el dataframe")

    proba = _proba_for(df, db)[0]
    bundle = _handle.bundle
    pred = _make_prediction_row(
        order=order,
        probability=proba,
        version=bundle["version"],
        features_used={"feature_count": len(bundle["feature_columns"])},
    )
    db.add(pred)
    db.commit()
    db.refresh(pred)
    return pred


def predict_for_active_orders(db: Session) -> List[MLPrediction]:
    """
    Itera sobre todas las órdenes activas (PENDING / IN_PROGRESS / DELAYED),
    calcula su probabilidad de retraso y persiste una `MLPrediction` por
    cada una. Devuelve la lista commiteada.

    Pensado para ejecutarse después de subir CSVs nuevos o re-entrenar el
    modelo, para refrescar el panel de alertas.
    """
    active_statuses = (OrderStatus.PENDING, OrderStatus.IN_PROGRESS, OrderStatus.DELAYED)
    active = db.scalars(
        select(ProductionOrder).where(ProductionOrder.status.in_(active_statuses))
    ).all()
    if not active:
        return []

    df = load_orders_dataframe(db, only_labeled=False)
    df = df[df["id"].isin([o.id for o in active])]
    if df.empty:
        return []

    probas = _proba_for(df, db)
    bundle = _handle.bundle
    version = bundle["version"]
    feature_count = len(bundle["feature_columns"])

    by_id: Dict[int, ProductionOrder] = {o.id: o for o in active}
    new_rows: List[MLPrediction] = []
    for pos, order_id in enumerate(df["id"].tolist()):
        order = by_id.get(int(order_id))
        if order is None:
            continue
        new_rows.append(
            _make_prediction_row(
                order=order,
                probability=probas[pos],
                version=version,
                features_used={"feature_count": feature_count},
            )
        )

    db.add_all(new_rows)
    db.commit()
    for r in new_rows:
        db.refresh(r)
    return new_rows


def get_feature_importance(*, top_k: Optional[int] = None) -> Dict[str, Any]:
    """Devuelve {feature_name: importance} ordenado descendentemente."""
    bundle = _handle.bundle
    cols: List[str] = bundle["feature_columns"]
    model = bundle["model"]
    importances = getattr(model, "feature_importances_", None)
    if importances is None:
        return {"version": bundle["version"], "items": []}
    pairs = sorted(zip(cols, importances.tolist()), key=lambda p: p[1], reverse=True)
    if top_k is not None:
        pairs = pairs[:top_k]
    return {
        "version": bundle["version"],
        "items": [{"feature": k, "importance": float(v)} for k, v in pairs],
    }


def get_model_info() -> Dict[str, Any]:
    """Metadata abreviada del modelo cargado + métricas si hay manifest."""
    if not is_model_available():
        return {"loaded": False, "available": False}
    bundle = _handle.bundle
    info: Dict[str, Any] = {
        "loaded": True,
        "available": True,
        "version": bundle["version"],
        "winner": bundle.get("winner"),
        "trained_at": bundle.get("trained_at"),
        "feature_count": len(bundle.get("feature_columns", [])),
        "loaded_at": _handle.loaded_at.isoformat() if _handle.loaded_at else None,
    }
    if _handle.manifest is not None:
        m = _handle.manifest
        info["dataset"] = m.get("dataset", {})
        info["models"] = m.get("models", {})
    return info
