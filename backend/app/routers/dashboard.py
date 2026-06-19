"""
Router /api/dashboard — endpoints para la vista de KPIs y OEE.

Todos los endpoints son de solo lectura y exigen estar autenticado. La lógica
de agregación vive en `app.services.dashboard_service`; este router es una
capa fina que valida parámetros y delega.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_active_user
from app.models import User
from app.schemas import (
    AlertsResponse,
    MachineRankingResponse,
    OEETrendResponse,
    OrderFulfillmentResponse,
    OverviewResponse,
    ProductionByShiftResponse,
    ScrapByMachineResponse,
    WIPResponse,
    YieldByOperationResponse,
)
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get(
    "/overview",
    response_model=OverviewResponse,
    summary="KPIs resumen de la planta (cabecera del dashboard)",
)
def overview(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_active_user),
) -> OverviewResponse:
    return dashboard_service.get_overview(db)


@router.get(
    "/oee-trend",
    response_model=OEETrendResponse,
    summary="Tendencia diaria del OEE (planta o por máquina)",
)
def oee_trend(
    days: int = Query(default=30, ge=1, le=180),
    machine_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_active_user),
) -> OEETrendResponse:
    return dashboard_service.get_oee_trend(db, days=days, machine_id=machine_id)


@router.get(
    "/production-by-shift",
    response_model=ProductionByShiftResponse,
    summary="Producción diaria desglosada por turno (barras apiladas)",
)
def production_by_shift(
    days: int = Query(default=7, ge=1, le=60),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_active_user),
) -> ProductionByShiftResponse:
    return dashboard_service.get_production_by_shift(db, days=days)


@router.get(
    "/order-fulfillment",
    response_model=OrderFulfillmentResponse,
    summary="Conteo diario de órdenes por estado",
)
def order_fulfillment(
    days: int = Query(default=30, ge=1, le=180),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_active_user),
) -> OrderFulfillmentResponse:
    return dashboard_service.get_order_fulfillment(db, days=days)


@router.get(
    "/machine-ranking",
    response_model=MachineRankingResponse,
    summary="Ranking de máquinas por OEE promedio",
)
def machine_ranking(
    days: int = Query(default=30, ge=1, le=180),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_active_user),
) -> MachineRankingResponse:
    return dashboard_service.get_machine_ranking(db, days=days)


@router.get(
    "/alerts",
    response_model=AlertsResponse,
    summary="Alertas predictivas: órdenes con probabilidad de retraso",
)
def alerts(
    threshold: float = Query(default=0.6, ge=0.0, le=1.0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_active_user),
) -> AlertsResponse:
    return dashboard_service.get_alerts(db, threshold=threshold, limit=limit)


@router.get(
    "/scrap-by-machine",
    response_model=ScrapByMachineResponse,
    summary="Desperdicio (kg) diario por máquina + acumulado tipo Pareto",
)
def scrap_by_machine(
    days: int = Query(default=30, ge=1, le=180),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_active_user),
) -> ScrapByMachineResponse:
    return dashboard_service.get_scrap_by_machine(db, days=days)


@router.get(
    "/yield-by-operation",
    response_model=YieldByOperationResponse,
    summary="Rendimiento out/in por máquina (cuello de botella de calidad)",
)
def yield_by_operation(
    days: int = Query(default=30, ge=1, le=180),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_active_user),
) -> YieldByOperationResponse:
    return dashboard_service.get_yield_by_operation(db, days=days)


@router.get(
    "/wip",
    response_model=WIPResponse,
    summary="Snapshot de WIP en línea (operaciones in_progress y ready)",
)
def wip(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_active_user),
) -> WIPResponse:
    return dashboard_service.get_wip(db)
