"""
Genera las figuras del informe de validación del modelo ML (entregable E7).

Carga el modelo entrenado (`models/delay_predictor.joblib`), reconstruye el
MISMO split de test que `ml/train.py` (test_size=0.2, random_state=42,
estratificado) y produce tres figuras PNG:

  1. roc_curve.png            — curva ROC con AUC.
  2. confusion_matrix.png     — matriz de confusión (umbral 0,5).
  3. feature_importance.png   — top-12 de importancia de variables.

Las cifras coinciden con `delay_predictor.manifest.json`, ya que se usan el
mismo modelo, datos y partición.

Ejecución (dentro del contenedor backend):
    docker compose exec backend python -m ml.figures
    docker compose exec backend python -m ml.figures --output /app/ml/figures
"""

from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")  # backend sin display (contenedor)

import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    confusion_matrix,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import train_test_split

from app.database import SessionLocal
from ml.features import build_training_dataset

DEFAULT_MODELS_DIR = Path(__file__).resolve().parent / "models"
TEST_SIZE = 0.2
RANDOM_STATE = 42
DPI = 150

# Paleta sobria y consistente entre figuras.
PRIMARY = "#1f5f8b"
ACCENT = "#d9534f"
GRAY = "#9aa5b1"


def _load_test_predictions(models_dir: Path):
    """Carga modelo + datos y devuelve (y_test, y_pred, y_proba, importancias)."""
    bundle = joblib.load(models_dir / "delay_predictor.joblib")
    model = bundle["model"]
    columns = bundle["feature_columns"]
    winner = bundle["winner"]

    db = SessionLocal()
    try:
        X, y, _cols = build_training_dataset(db)
    finally:
        db.close()

    # Reindexar X a las columnas exactas con las que se entrenó.
    X = X[columns]

    _X_train, X_test, _y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
    )
    y_proba = model.predict_proba(X_test)[:, 1]
    y_pred = (y_proba >= 0.5).astype(int)

    importances = getattr(model, "feature_importances_", None)
    imp = (
        sorted(zip(columns, importances.tolist()), key=lambda t: t[1], reverse=True)
        if importances is not None
        else []
    )
    return y_test, y_pred, y_proba, imp, winner


def plot_roc(y_test, y_proba, out: Path) -> None:
    fpr, tpr, _ = roc_curve(y_test, y_proba)
    auc = roc_auc_score(y_test, y_proba)

    fig, ax = plt.subplots(figsize=(6, 5))
    ax.plot(fpr, tpr, color=PRIMARY, lw=2.5, label=f"XGBoost (AUC = {auc:.3f})")
    ax.plot([0, 1], [0, 1], color=GRAY, lw=1.5, ls="--", label="Azar (AUC = 0.500)")
    ax.set_xlabel("Tasa de falsos positivos (1 − especificidad)")
    ax.set_ylabel("Tasa de verdaderos positivos (sensibilidad)")
    ax.set_title("Curva ROC — Predicción de retrasos")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    ax.legend(loc="lower right", frameon=True)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(out, dpi=DPI)
    plt.close(fig)


def plot_confusion(y_test, y_pred, out: Path) -> None:
    cm = confusion_matrix(y_test, y_pred)
    disp = ConfusionMatrixDisplay(
        confusion_matrix=cm, display_labels=["A tiempo", "Retraso"]
    )
    fig, ax = plt.subplots(figsize=(5.5, 5))
    disp.plot(ax=ax, cmap="Blues", colorbar=False, values_format="d")
    ax.set_xlabel("Predicción")
    ax.set_ylabel("Valor real")
    ax.set_title("Matriz de confusión (umbral 0,5)")
    fig.tight_layout()
    fig.savefig(out, dpi=DPI)
    plt.close(fig)


def plot_feature_importance(importances, out: Path, top: int = 12) -> None:
    top_items = importances[:top][::-1]  # invertido para barh ascendente
    labels = [k for k, _ in top_items]
    values = [v for _, v in top_items]

    fig, ax = plt.subplots(figsize=(8, 6))
    y_pos = np.arange(len(labels))
    ax.barh(y_pos, values, color=PRIMARY)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel("Importancia (ganancia relativa)")
    ax.set_title(f"Top {top} — Importancia de variables (XGBoost)")
    for i, v in enumerate(values):
        ax.text(v + max(values) * 0.01, i, f"{v:.3f}", va="center", fontsize=8)
    ax.margins(x=0.12)
    fig.tight_layout()
    fig.savefig(out, dpi=DPI)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera figuras del informe ML")
    parser.add_argument("--models-dir", type=str, default=str(DEFAULT_MODELS_DIR))
    parser.add_argument("--output", type=str, default=str(DEFAULT_MODELS_DIR.parent / "figures"))
    args = parser.parse_args()

    models_dir = Path(args.models_dir)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    y_test, y_pred, y_proba, importances, winner = _load_test_predictions(models_dir)

    plot_roc(y_test, y_proba, out_dir / "roc_curve.png")
    plot_confusion(y_test, y_pred, out_dir / "confusion_matrix.png")
    plot_feature_importance(importances, out_dir / "feature_importance.png")

    print(f"Figuras generadas en {out_dir}/ (modelo ganador: {winner}):")
    for name in ("roc_curve.png", "confusion_matrix.png", "feature_importance.png"):
        p = out_dir / name
        print(f"  · {name:26s} ({p.stat().st_size:>6} bytes)")


if __name__ == "__main__":
    main()
