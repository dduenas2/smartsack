"""
Tests del módulo de predicciones de retraso.

Cubren:
- features.py: etiqueta correcta, columnas determinísticas entre train e inference.
- prediction_service: predict_for_order/predict_for_active_orders/feature_importance.
- Router /api/predictions: auth, permisos, formato de respuesta.

Los tests requieren que el modelo entrenado esté serializado en
`ml/models/delay_predictor.joblib`. Si no existe, los tests del servicio
y del router se saltan con `pytest.skip` para no bloquear CI sin datos.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from app.models import OrderStatus
from app.services import prediction_service
from ml.features import (
    CATEGORICAL_VOCAB,
    NUMERIC_COLUMNS,
    build_feature_frame,
    build_training_dataset,
    extract_label,
)
from tests.conftest import auth_header


MODEL_AVAILABLE = prediction_service.is_model_available()
SKIP_NO_MODEL = pytest.mark.skipif(
    not MODEL_AVAILABLE, reason="ml/models/delay_predictor.joblib no existe — corre `python -m ml.train`"
)


# =============================================================================
# features.py
# =============================================================================
def test_extract_label_marks_delayed_status() -> None:
    """status==DELAYED → 1 sin importar timestamps."""
    base = datetime(2026, 5, 1, tzinfo=timezone.utc)
    df = pd.DataFrame(
        {
            "status": ["completed", "delayed", "completed"],
            "actual_end": [base, base, base + timedelta(hours=4)],
            "planned_end": [base + timedelta(hours=2), base + timedelta(hours=8), base],
        }
    )
    y = extract_label(df)
    assert y.tolist() == [0, 1, 1]


def test_extract_label_tolerance_window() -> None:
    """Una hora extra no cuenta (tolerancia operativa)."""
    base = datetime(2026, 5, 1, tzinfo=timezone.utc)
    df = pd.DataFrame(
        {
            "status": ["completed"],
            "actual_end": [base + timedelta(minutes=45)],
            "planned_end": [base],
        }
    )
    assert extract_label(df).tolist() == [0]


def test_extract_label_empty_df() -> None:
    df = pd.DataFrame(columns=["status", "actual_end", "planned_end"])
    y = extract_label(df)
    assert len(y) == 0
    assert y.dtype == np.int8


def test_build_feature_frame_columns_are_deterministic(db_session) -> None:
    """El frame de inferencia tiene exactamente las mismas columnas que training."""
    X_train, y_train, cols_train = build_training_dataset(db_session)
    # Subset de inferencia: las primeras 5 órdenes
    df = pd.DataFrame(
        {
            "id": [1],
            "product_type": ["Saco-no-existente"],  # → debe ir a _UNK
            "quantity_ordered": [1000],
            "machine_code": ["TUB-01"],
            "priority": ["normal"],
            "planned_start": [pd.Timestamp("2026-06-01 06:00:00", tz="UTC")],
            "planned_end": [pd.Timestamp("2026-06-01 14:00:00", tz="UTC")],
            "actual_start": [pd.NaT],
            "actual_end": [pd.NaT],
        }
    )
    Xi, cols_i = build_feature_frame(
        df, history_df=pd.DataFrame(columns=df.columns), history_label=pd.Series(dtype=np.int8)
    )
    assert cols_i == cols_train


def test_categorical_vocab_includes_all_machines() -> None:
    """Sanity: el vocabulario cubre las 8 máquinas del seed."""
    machines = CATEGORICAL_VOCAB["machine_code"]
    expected = {"TUB-01", "TUB-02", "IMP-01", "IMP-02", "FON-01", "FON-02", "EMP-01", "EMP-02"}
    assert expected.issubset(set(machines))


# =============================================================================
# prediction_service
# =============================================================================
@SKIP_NO_MODEL
def test_predict_for_active_orders_persists(db_session) -> None:
    n = len(prediction_service.predict_for_active_orders(db_session))
    assert n > 0


@SKIP_NO_MODEL
def test_predict_for_completed_order_rejects(db_session) -> None:
    from sqlalchemy import select
    from app.models import ProductionOrder

    completed = db_session.scalar(
        select(ProductionOrder).where(ProductionOrder.status == OrderStatus.COMPLETED).limit(1)
    )
    assert completed is not None
    with pytest.raises(ValueError):
        prediction_service.predict_for_order(db_session, order_id=completed.id)


@SKIP_NO_MODEL
def test_predict_for_unknown_order_raises(db_session) -> None:
    with pytest.raises(KeyError):
        prediction_service.predict_for_order(db_session, order_id=99_999_999)


@SKIP_NO_MODEL
def test_feature_importance_top_k() -> None:
    fi = prediction_service.get_feature_importance(top_k=5)
    assert "version" in fi
    assert len(fi["items"]) == 5
    # Debe estar ordenado descendente.
    importances = [it["importance"] for it in fi["items"]]
    assert importances == sorted(importances, reverse=True)


# =============================================================================
# Router /api/predictions
# =============================================================================
def test_predictions_require_auth(client) -> None:
    assert client.post("/api/predictions/predict/1").status_code == 401
    assert client.post("/api/predictions/predict-active").status_code == 401
    assert client.get("/api/predictions/feature-importance").status_code == 401
    assert client.get("/api/predictions/model-info").status_code == 401


@SKIP_NO_MODEL
def test_model_info_endpoint(client, admin_token) -> None:
    r = client.get("/api/predictions/model-info", headers=auth_header(admin_token))
    assert r.status_code == 200
    body = r.json()
    assert body["loaded"] is True
    assert body["available"] is True
    assert body["feature_count"] == 30


@SKIP_NO_MODEL
def test_feature_importance_endpoint(client, admin_token) -> None:
    r = client.get(
        "/api/predictions/feature-importance?top_k=10",
        headers=auth_header(admin_token),
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 10


@SKIP_NO_MODEL
def test_predict_active_requires_admin_or_supervisor(client, operator_token) -> None:
    r = client.post(
        "/api/predictions/predict-active", headers=auth_header(operator_token)
    )
    assert r.status_code == 403


@SKIP_NO_MODEL
def test_reload_requires_admin(client, supervisor_token) -> None:
    r = client.post(
        "/api/predictions/reload", headers=auth_header(supervisor_token)
    )
    assert r.status_code == 403


@SKIP_NO_MODEL
def test_predict_active_endpoint_returns_count(client, supervisor_token) -> None:
    r = client.post(
        "/api/predictions/predict-active", headers=auth_header(supervisor_token)
    )
    assert r.status_code == 200
    body = r.json()
    assert body["count"] >= 0
    if body["count"] > 0:
        assert body["model_version"] is not None
        first = body["items"][0]
        assert 0.0 <= first["delay_probability"] <= 1.0
        assert first["predicted_delay_hours"] >= 0.0


@SKIP_NO_MODEL
def test_predict_one_completed_order_returns_400(client, admin_token, db_session) -> None:
    from sqlalchemy import select
    from app.models import ProductionOrder

    completed = db_session.scalar(
        select(ProductionOrder).where(ProductionOrder.status == OrderStatus.COMPLETED).limit(1)
    )
    r = client.post(
        f"/api/predictions/predict/{completed.id}", headers=auth_header(admin_token)
    )
    assert r.status_code == 400


@SKIP_NO_MODEL
def test_predict_one_unknown_order_returns_404(client, admin_token) -> None:
    r = client.post(
        "/api/predictions/predict/99999999", headers=auth_header(admin_token)
    )
    assert r.status_code == 404
