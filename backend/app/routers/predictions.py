"""
Router /api/predictions — inferencia del motor de retraso.

Endpoints:
  · POST /predict/{order_id}    Predice una orden concreta. Auth requerida.
  · POST /predict-active        Predice todas las órdenes activas (admin/sup).
  · POST /reload                Recarga el joblib desde disco (admin).
  · GET  /feature-importance    Top features del modelo cargado.
  · GET  /model-info            Metadata del modelo (manifest + métricas).
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_active_user, require_roles
from app.models import User, UserRole
from app.schemas import (
    BatchPredictionResponse,
    FeatureImportanceResponse,
    MLPredictionResponse,
    ModelInfoResponse,
)
from app.services import audit_service, prediction_service
from app.services.prediction_service import ModelNotLoaded


router = APIRouter(prefix="/predictions", tags=["predictions"])


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _ensure_loaded():
    if not prediction_service.is_model_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Modelo no disponible. Ejecuta `python -m ml.train` y luego "
                "POST /api/predictions/reload."
            ),
        )


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------
@router.post(
    "/predict/{order_id}",
    response_model=MLPredictionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Predice retraso para una orden y persiste el resultado",
)
def predict_one(
    order_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_active_user),
):
    _ensure_loaded()
    try:
        return prediction_service.predict_for_order(db, order_id=order_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"order_id={order_id} no encontrada",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        )


@router.post(
    "/predict-active",
    response_model=BatchPredictionResponse,
    summary="Predice todas las órdenes activas y persiste cada predicción",
)
def predict_active(
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPERVISOR)),
) -> BatchPredictionResponse:
    _ensure_loaded()
    preds = prediction_service.predict_for_active_orders(db)
    version = preds[0].model_version if preds else None
    return BatchPredictionResponse(
        count=len(preds),
        model_version=version,
        items=[MLPredictionResponse.model_validate(p) for p in preds],
    )


@router.post(
    "/reload",
    response_model=ModelInfoResponse,
    summary="Recarga el modelo desde disco (admin)",
)
def reload_model(
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.ADMIN)),
) -> ModelInfoResponse:
    _ensure_loaded()
    try:
        prediction_service.reload_model()
    except ModelNotLoaded as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )
    info = prediction_service.get_model_info()
    audit_service.log_admin_action(
        db,
        actor=admin,
        action="reload_model",
        entity_type="ml_model",
        entity_id=None,
        after={"version": info.get("version"), "loaded": info.get("loaded")},
    )
    db.commit()
    return ModelInfoResponse(**info)


@router.get(
    "/feature-importance",
    response_model=FeatureImportanceResponse,
    summary="Importancia de cada feature según el modelo entrenado",
)
def feature_importance(
    top_k: Optional[int] = Query(default=None, ge=1, le=100),
    _user: User = Depends(get_current_active_user),
) -> FeatureImportanceResponse:
    _ensure_loaded()
    return FeatureImportanceResponse(**prediction_service.get_feature_importance(top_k=top_k))


@router.get(
    "/model-info",
    response_model=ModelInfoResponse,
    summary="Metadata del modelo + métricas en test",
)
def model_info(
    _user: User = Depends(get_current_active_user),
) -> ModelInfoResponse:
    if not prediction_service.is_model_available():
        return ModelInfoResponse(loaded=False, available=False)
    return ModelInfoResponse(**prediction_service.get_model_info())
