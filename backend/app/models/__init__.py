"""
Modelos SQLAlchemy de SmartSack.

Importa aquí todos los modelos para que Alembic los descubra al ejecutar
`alembic revision --autogenerate`. Importar este paquete carga todas las
clases en `Base.metadata`.
"""

from app.models.enums import (
    EventType,
    MachineStatus,
    MachineType,
    OperationStatus,
    OrderPriority,
    OrderStatus,
    ScrapReason,
    ShiftName,
    UserRole,
)
from app.models.admin_audit import AdminAuditLog
from app.models.etl_load import ETLLoad, ETLLoadKind, ETLLoadStatus
from app.models.event import ProductionEvent
from app.models.machine import Machine
from app.models.material import Material
from app.models.oee import OEERecord
from app.models.operation import OrderOperation
from app.models.order import ProductionOrder
from app.models.prediction import MLPrediction
from app.models.quality import QualityRecord
from app.models.shift import Shift
from app.models.system_setting import SystemSetting
from app.models.user import User

__all__ = [
    # enums
    "EventType",
    "MachineStatus",
    "MachineType",
    "OperationStatus",
    "OrderPriority",
    "OrderStatus",
    "ScrapReason",
    "ShiftName",
    "UserRole",
    # tablas
    "AdminAuditLog",
    "ETLLoad",
    "ETLLoadKind",
    "ETLLoadStatus",
    "Machine",
    "Material",
    "MLPrediction",
    "OEERecord",
    "OrderOperation",
    "ProductionEvent",
    "ProductionOrder",
    "QualityRecord",
    "Shift",
    "SystemSetting",
    "User",
]
