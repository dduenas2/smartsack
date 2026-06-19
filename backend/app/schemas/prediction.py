"""
Schemas Pydantic para las respuestas de /api/predictions.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.schemas.common import ORMConfig


class MLPredictionResponse(BaseModel):
    """Una fila de la tabla `ml_predictions`."""

    model_config = ORMConfig

    id: int
    order_id: int
    delay_probability: float = Field(..., ge=0.0, le=1.0)
    predicted_delay_hours: float = Field(..., ge=0.0)
    features_json: Optional[Dict[str, Any]] = None
    model_version: str
    created_at: datetime


class FeatureImportanceItem(BaseModel):
    feature: str
    importance: float


class FeatureImportanceResponse(BaseModel):
    version: str
    items: List[FeatureImportanceItem]


class ModelInfoResponse(BaseModel):
    """Metadata del modelo cargado en memoria."""

    loaded: bool
    available: bool
    version: Optional[str] = None
    winner: Optional[str] = None
    trained_at: Optional[str] = None
    feature_count: Optional[int] = None
    loaded_at: Optional[str] = None
    dataset: Optional[Dict[str, Any]] = None
    models: Optional[Dict[str, Any]] = None


class BatchPredictionResponse(BaseModel):
    """Respuesta de /predict-active: cuántas órdenes se predijeron."""

    count: int = Field(..., ge=0)
    model_version: Optional[str] = None
    items: List[MLPredictionResponse]
