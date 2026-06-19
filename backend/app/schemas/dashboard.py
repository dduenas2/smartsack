"""
Schemas Pydantic del módulo Dashboard.

DTOs para los endpoints de KPIs y OEE consumidos por la página /dashboard del
frontend. Cada response está pensado para alimentar un widget concreto:
KPIs en cabecera, gráficas Recharts (líneas, barras apiladas, área), tabla
de ranking de máquinas y panel de alertas predictivas del modelo de ML.
"""

from datetime import date as date_t, datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models import MachineType, OrderStatus, ShiftName


# ---------------------------------------------------------------------------
# /api/dashboard/overview — KPIs resumen de planta.
# ---------------------------------------------------------------------------
class OverviewResponse(BaseModel):
    """Tarjetas KPI superiores: snapshot agregado de toda la planta."""

    # OEE consolidado (promedio simple sobre los registros del día más reciente).
    plant_oee: float = Field(..., ge=0.0, le=1.0)
    plant_oee_yesterday: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    availability: float = Field(..., ge=0.0, le=1.0)
    performance: float = Field(..., ge=0.0, le=1.0)
    quality: float = Field(..., ge=0.0, le=1.0)

    # Estado de las órdenes "hoy" (zona horaria del servidor).
    orders_completed_today: int = Field(..., ge=0)
    orders_in_progress: int = Field(..., ge=0)
    orders_pending: int = Field(..., ge=0)
    orders_delayed: int = Field(..., ge=0)

    # Sacos producidos vs. objetivo del día (suma sobre órdenes activas + completadas hoy).
    production_today: int = Field(..., ge=0)
    production_target_today: int = Field(..., ge=0)

    # Máquinas en estado RUNNING vs. total.
    active_machines: int = Field(..., ge=0)
    total_machines: int = Field(..., ge=0)

    # Fecha de referencia con la que se calcularon los KPIs (la más reciente con OEE).
    reference_date: Optional[date_t] = None


# ---------------------------------------------------------------------------
# /api/dashboard/oee-trend — tendencia diaria.
# ---------------------------------------------------------------------------
class OEETrendPoint(BaseModel):
    """Un punto diario del gráfico de tendencia de OEE."""

    date: date_t
    availability: float = Field(..., ge=0.0, le=1.0)
    performance: float = Field(..., ge=0.0, le=1.0)
    quality: float = Field(..., ge=0.0, le=1.0)
    oee: float = Field(..., ge=0.0, le=1.0)
    sample_count: int = Field(..., ge=0, description="Nº de registros que componen el promedio del día.")


class OEETrendResponse(BaseModel):
    machine_id: Optional[int] = Field(
        default=None, description="None ⇒ tendencia agregada de planta."
    )
    days: int = Field(..., ge=1, le=180)
    points: List[OEETrendPoint]


# ---------------------------------------------------------------------------
# /api/dashboard/production-by-shift — barras apiladas por turno.
# ---------------------------------------------------------------------------
class ShiftProduction(BaseModel):
    shift: ShiftName
    quantity: int = Field(..., ge=0)


class ProductionByShiftPoint(BaseModel):
    """Producción agregada de un día desglosada en los 3 turnos."""

    date: date_t
    turno_1: int = Field(default=0, ge=0)
    turno_2: int = Field(default=0, ge=0)
    turno_3: int = Field(default=0, ge=0)
    total: int = Field(..., ge=0)


class ProductionByShiftResponse(BaseModel):
    days: int = Field(..., ge=1, le=60)
    points: List[ProductionByShiftPoint]


# ---------------------------------------------------------------------------
# /api/dashboard/order-fulfillment — cumplimiento de órdenes.
# ---------------------------------------------------------------------------
class OrderFulfillmentPoint(BaseModel):
    """Conteo de órdenes por estado en un día concreto (eje X = planned_end::date)."""

    date: date_t
    completed: int = Field(default=0, ge=0)
    in_progress: int = Field(default=0, ge=0)
    pending: int = Field(default=0, ge=0)
    delayed: int = Field(default=0, ge=0)


class OrderFulfillmentResponse(BaseModel):
    days: int = Field(..., ge=1, le=180)
    points: List[OrderFulfillmentPoint]
    # Totales del rango — útil para subtítulos y cálculos de % cumplimiento.
    total_completed: int = Field(..., ge=0)
    total_delayed: int = Field(..., ge=0)
    total_pending: int = Field(..., ge=0)
    total_in_progress: int = Field(..., ge=0)


# ---------------------------------------------------------------------------
# /api/dashboard/machine-ranking — ranking por OEE promedio.
# ---------------------------------------------------------------------------
class MachineRankingItem(BaseModel):
    """Una fila de la tabla de ranking ordenada por avg_oee DESC."""

    machine_id: int
    code: str
    name: str
    type: MachineType
    avg_oee: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    avg_availability: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    avg_performance: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    avg_quality: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    sample_count: int = Field(..., ge=0)


class MachineRankingResponse(BaseModel):
    days: int = Field(..., ge=1, le=180)
    items: List[MachineRankingItem]


# ---------------------------------------------------------------------------
# /api/dashboard/alerts — alertas predictivas de retraso.
# ---------------------------------------------------------------------------
class AlertItem(BaseModel):
    """Una orden que el modelo marcó como propensa a retraso."""

    order_id: int
    order_number: str
    product_type: str
    machine_id: Optional[int] = None
    machine_code: Optional[str] = None
    machine_name: Optional[str] = None
    status: OrderStatus
    delay_probability: float = Field(..., ge=0.0, le=1.0)
    predicted_delay_hours: float = Field(..., ge=0.0)
    planned_end: datetime
    model_version: str
    predicted_at: datetime


class AlertsResponse(BaseModel):
    threshold: float = Field(..., ge=0.0, le=1.0)
    items: List[AlertItem]


# ---------------------------------------------------------------------------
# /api/dashboard/scrap-by-machine — desperdicio diario por máquina.
# ---------------------------------------------------------------------------
class ScrapByMachineDayPoint(BaseModel):
    """Scrap acumulado en un día para una máquina específica."""

    date: date_t
    machine_id: int
    machine_code: str
    machine_type: MachineType
    scrap_kg: float = Field(..., ge=0.0)


class ScrapByMachineResponse(BaseModel):
    days: int = Field(..., ge=1, le=180)
    points: List[ScrapByMachineDayPoint]
    # Acumulado por máquina del rango completo (para Pareto).
    totals_by_machine: List["ScrapMachineTotal"]


class ScrapMachineTotal(BaseModel):
    machine_id: int
    machine_code: str
    machine_type: MachineType
    scrap_kg: float = Field(..., ge=0.0)


# ---------------------------------------------------------------------------
# /api/dashboard/yield-by-operation — rendimiento out/in por máquina.
# ---------------------------------------------------------------------------
class YieldByMachineItem(BaseModel):
    machine_id: int
    machine_code: str
    machine_type: MachineType
    quantity_in_total: int = Field(..., ge=0)
    quantity_out_total: int = Field(..., ge=0)
    yield_ratio: Optional[float] = Field(default=None, ge=0.0, le=1.5)
    operations_count: int = Field(..., ge=0)


class YieldByOperationResponse(BaseModel):
    days: int = Field(..., ge=1, le=180)
    items: List[YieldByMachineItem]


# ---------------------------------------------------------------------------
# /api/dashboard/wip — Work In Progress en este momento.
# ---------------------------------------------------------------------------
class WIPMachineSlot(BaseModel):
    machine_id: int
    machine_code: str
    machine_type: MachineType
    operations_in_progress: int = Field(..., ge=0)
    operations_ready: int = Field(..., ge=0)
    units_in_progress: int = Field(default=0, ge=0)
    units_ready: int = Field(default=0, ge=0)


class WIPResponse(BaseModel):
    """Snapshot de WIP por máquina; suma todo lo que está activo o esperando."""

    machines: List[WIPMachineSlot]
    total_units_in_line: int = Field(..., ge=0)


# Forward refs
ScrapByMachineResponse.model_rebuild()
