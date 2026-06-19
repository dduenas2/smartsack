"""
Pipeline de entrenamiento del motor de retraso (CRISP-DM · fase Modeling).

Ejecuta:
  1. Carga + featurización del dataset etiquetable.
  2. Split estratificado train/test 80/20.
  3. GridSearchCV (5-fold estratificado) sobre Random Forest y XGBoost.
  4. Evaluación en test: F1, Precision, Recall, AUC-ROC, matriz de confusión,
     feature importance.
  5. Selección del mejor por F1 y serialización con joblib en
     `ml/models/delay_predictor.joblib`. También guarda un manifest JSON
     con métricas, hiperparámetros y lista de features.

Ejecutar dentro del contenedor backend:
    docker compose exec backend python -m ml.train
    docker compose exec backend python -m ml.train --quick   # grid reducido
    docker compose exec backend python -m ml.train --output /app/ml/models
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    auc,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import GridSearchCV, StratifiedKFold, train_test_split
from xgboost import XGBClassifier

from app.database import SessionLocal
from ml.features import build_training_dataset


logger = logging.getLogger("smartsack.ml.train")
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")


MODEL_VERSION_PREFIX = "delay"  # versión: "delay-{rf|xgb}-YYYYMMDDhhmmss" (≤ 28 chars)
DEFAULT_MODELS_DIR = Path(__file__).resolve().parent / "models"


# -----------------------------------------------------------------------------
# Definición de los grids (full y quick)
# -----------------------------------------------------------------------------
def _rf_grid(quick: bool) -> Dict[str, List[Any]]:
    if quick:
        return {
            "n_estimators": [120],
            "max_depth": [None, 12],
            "min_samples_leaf": [2],
            "class_weight": ["balanced"],
        }
    return {
        "n_estimators": [120, 240],
        "max_depth": [None, 12, 20],
        "min_samples_leaf": [1, 2, 4],
        "class_weight": ["balanced"],
    }


def _xgb_grid(quick: bool) -> Dict[str, List[Any]]:
    if quick:
        return {
            "n_estimators": [200],
            "max_depth": [4],
            "learning_rate": [0.1],
            "subsample": [0.9],
        }
    return {
        "n_estimators": [200, 400],
        "max_depth": [3, 5, 7],
        "learning_rate": [0.05, 0.1],
        "subsample": [0.8, 1.0],
        "colsample_bytree": [0.8, 1.0],
    }


# -----------------------------------------------------------------------------
# Búsqueda + evaluación de un modelo
# -----------------------------------------------------------------------------
def _run_grid_search(
    name: str,
    estimator,
    grid: Dict[str, List[Any]],
    X_train: pd.DataFrame,
    y_train: pd.Series,
    cv: StratifiedKFold,
) -> Tuple[Any, Dict[str, Any]]:
    """Ejecuta GridSearchCV y devuelve el best_estimator + metadata."""
    started = time.monotonic()
    search = GridSearchCV(
        estimator=estimator,
        param_grid=grid,
        cv=cv,
        scoring="f1",
        n_jobs=-1,
        verbose=0,
        refit=True,
    )
    search.fit(X_train, y_train)
    elapsed = time.monotonic() - started
    logger.info(
        "%-8s · best F1 (CV): %.4f · tiempo: %.1fs · params: %s",
        name, search.best_score_, elapsed, search.best_params_,
    )
    meta = {
        "best_f1_cv": float(search.best_score_),
        "best_params": search.best_params_,
        "fit_seconds": round(elapsed, 2),
    }
    return search.best_estimator_, meta


def _evaluate(
    model, X_test: pd.DataFrame, y_test: pd.Series, *, threshold: float = 0.5
) -> Dict[str, Any]:
    """Métricas en el conjunto test usando un umbral fijo."""
    y_proba = model.predict_proba(X_test)[:, 1]
    y_pred = (y_proba >= threshold).astype(int)

    f1 = f1_score(y_test, y_pred, zero_division=0)
    prec = precision_score(y_test, y_pred, zero_division=0)
    rec = recall_score(y_test, y_pred, zero_division=0)
    try:
        auc_roc = roc_auc_score(y_test, y_proba)
    except ValueError:
        auc_roc = float("nan")
    cm = confusion_matrix(y_test, y_pred).tolist()

    return {
        "threshold": threshold,
        "f1": float(f1),
        "precision": float(prec),
        "recall": float(rec),
        "auc_roc": float(auc_roc),
        "confusion_matrix": cm,
        "support_test": int(len(y_test)),
        "support_positives_test": int(y_test.sum()),
    }


def _feature_importance(model, columns: List[str]) -> Dict[str, float]:
    """Devuelve las importancias del modelo serializables como JSON."""
    importances = getattr(model, "feature_importances_", None)
    if importances is None:
        return {}
    return {col: float(v) for col, v in zip(columns, importances.tolist())}


# -----------------------------------------------------------------------------
# Pipeline principal
# -----------------------------------------------------------------------------
def train(
    *,
    output_dir: Path = DEFAULT_MODELS_DIR,
    quick: bool = False,
    test_size: float = 0.2,
    random_state: int = 42,
) -> Dict[str, Any]:
    """Entrena los dos modelos y guarda el mejor. Devuelve el manifest."""
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    db = SessionLocal()
    try:
        logger.info("Cargando dataset desde la BD...")
        X, y, columns = build_training_dataset(db)
    finally:
        db.close()

    if len(X) < 50:
        raise RuntimeError(
            f"Dataset demasiado pequeño ({len(X)} filas): "
            f"corre `scripts.seed` antes de entrenar."
        )

    logger.info(
        "Dataset: X=%s, positives=%d/%d (%.2f%%)",
        X.shape, int(y.sum()), len(y), 100 * float(y.mean()),
    )

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )
    logger.info("Train: %d (%d pos)  ·  Test: %d (%d pos)", len(X_train), int(y_train.sum()), len(X_test), int(y_test.sum()))

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=random_state)

    # -------- Random Forest --------
    rf_estimator = RandomForestClassifier(random_state=random_state, n_jobs=-1)
    rf_best, rf_meta = _run_grid_search("RF", rf_estimator, _rf_grid(quick), X_train, y_train, cv)

    # -------- XGBoost --------
    pos = int(y_train.sum())
    neg = int(len(y_train) - pos)
    spw = max(1.0, neg / max(1, pos))  # `scale_pos_weight` para desbalance.
    xgb_estimator = XGBClassifier(
        random_state=random_state,
        n_jobs=-1,
        objective="binary:logistic",
        eval_metric="logloss",
        scale_pos_weight=spw,
        tree_method="hist",
    )
    xgb_best, xgb_meta = _run_grid_search("XGB", xgb_estimator, _xgb_grid(quick), X_train, y_train, cv)

    # -------- Evaluación en test --------
    rf_eval = _evaluate(rf_best, X_test, y_test)
    xgb_eval = _evaluate(xgb_best, X_test, y_test)
    logger.info("RF  · test F1=%.3f AUC=%.3f Precision=%.3f Recall=%.3f", rf_eval["f1"], rf_eval["auc_roc"], rf_eval["precision"], rf_eval["recall"])
    logger.info("XGB · test F1=%.3f AUC=%.3f Precision=%.3f Recall=%.3f", xgb_eval["f1"], xgb_eval["auc_roc"], xgb_eval["precision"], xgb_eval["recall"])

    # Selección por F1 (priorizamos detectar retrasos sobre falsos positivos).
    if xgb_eval["f1"] >= rf_eval["f1"]:
        winner_name, winner_model, winner_eval, winner_meta = "xgboost", xgb_best, xgb_eval, xgb_meta
    else:
        winner_name, winner_model, winner_eval, winner_meta = "random_forest", rf_best, rf_eval, rf_meta

    timestamp = datetime.now(tz=timezone.utc)
    short_name = "xgb" if winner_name == "xgboost" else "rf"
    version = f"{MODEL_VERSION_PREFIX}-{short_name}-{timestamp.strftime('%Y%m%d%H%M%S')}"
    artifact_path = output_dir / "delay_predictor.joblib"
    manifest_path = output_dir / "delay_predictor.manifest.json"

    bundle = {
        "version": version,
        "winner": winner_name,
        "trained_at": timestamp.isoformat(),
        "feature_columns": columns,
        "model": winner_model,
    }
    joblib.dump(bundle, artifact_path)
    logger.info("Modelo serializado en %s (%.0f KB)", artifact_path, artifact_path.stat().st_size / 1024)

    manifest = {
        "version": version,
        "winner": winner_name,
        "trained_at": timestamp.isoformat(),
        "dataset": {
            "rows": int(len(X)),
            "positives": int(y.sum()),
            "positive_rate": float(y.mean()),
            "test_size": test_size,
            "feature_columns": columns,
        },
        "models": {
            "random_forest": {**rf_meta, "test_metrics": rf_eval},
            "xgboost": {**xgb_meta, "test_metrics": xgb_eval},
        },
        "feature_importance": _feature_importance(winner_model, columns),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2))
    logger.info("Manifest en %s", manifest_path)

    return manifest


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Entrena el predictor de retraso de SmartSack")
    parser.add_argument("--output", type=str, default=str(DEFAULT_MODELS_DIR), help="Directorio de salida para joblib + manifest")
    parser.add_argument("--quick", action="store_true", help="Grid reducido (entrena en segundos)")
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    train(
        output_dir=Path(args.output),
        quick=args.quick,
        test_size=args.test_size,
        random_state=args.seed,
    )


if __name__ == "__main__":
    main()
