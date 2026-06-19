"""
Esquemas Pydantic de SmartSack.

Reexporta los DTOs más usados para facilitar imports cortos en routers:
    from app.schemas import LoginRequest, TokenResponse, MachineResponse, ...
"""

from app.schemas.auth import CurrentUserResponse, LoginRequest, TokenResponse
from app.schemas.chat import (
    ChatMessageDTO,
    ChatRequest,
    ChatResponseDTO,
    ChatStatusResponse,
    ToolCallDTO,
)
from app.schemas.common import PaginatedResponse
from app.schemas.dashboard import (
    AlertItem,
    AlertsResponse,
    MachineRankingItem,
    MachineRankingResponse,
    OEETrendPoint,
    OEETrendResponse,
    OrderFulfillmentPoint,
    OrderFulfillmentResponse,
    OverviewResponse,
    ProductionByShiftPoint,
    ProductionByShiftResponse,
    ScrapByMachineDayPoint,
    ScrapByMachineResponse,
    ScrapMachineTotal,
    ShiftProduction,
    WIPMachineSlot,
    WIPResponse,
    YieldByMachineItem,
    YieldByOperationResponse,
)
from app.schemas.etl import ETLLoadListResponse, ETLLoadResponse
from app.schemas.prediction import (
    BatchPredictionResponse,
    FeatureImportanceItem,
    FeatureImportanceResponse,
    MLPredictionResponse,
    ModelInfoResponse,
)
from app.schemas.event import ProductionEventCreate, ProductionEventResponse
from app.schemas.operation import (
    OperationMachineSummary,
    OperationOrderSummary,
    OperationProductionReport,
    OperationResponse,
)
from app.schemas.machine import (
    MachineBase,
    MachineCreate,
    MachineResponse,
    MachineUpdate,
)
from app.schemas.order import (
    ProductionOrderBase,
    ProductionOrderCreate,
    ProductionOrderResponse,
    ProductionOrderUpdate,
)
from app.schemas.user import (
    UserAssignMachine,
    UserCreate,
    UserPasswordReset,
    UserResponse,
    UserUpdate,
)

__all__ = [
    # auth
    "LoginRequest",
    "TokenResponse",
    "CurrentUserResponse",
    # common
    "PaginatedResponse",
    # user
    "UserAssignMachine",
    "UserCreate",
    "UserPasswordReset",
    "UserResponse",
    "UserUpdate",
    # machine
    "MachineBase",
    "MachineCreate",
    "MachineResponse",
    "MachineUpdate",
    # order
    "ProductionOrderBase",
    "ProductionOrderCreate",
    "ProductionOrderResponse",
    "ProductionOrderUpdate",
    # event
    "ProductionEventCreate",
    "ProductionEventResponse",
    # operation
    "OperationResponse",
    "OperationOrderSummary",
    "OperationMachineSummary",
    "OperationProductionReport",
    # etl
    "ETLLoadResponse",
    "ETLLoadListResponse",
    # ml predictions
    "MLPredictionResponse",
    "FeatureImportanceItem",
    "FeatureImportanceResponse",
    "ModelInfoResponse",
    "BatchPredictionResponse",
    # chat
    "ChatMessageDTO",
    "ChatRequest",
    "ChatResponseDTO",
    "ChatStatusResponse",
    "ToolCallDTO",
    # dashboard
    "OverviewResponse",
    "OEETrendPoint",
    "OEETrendResponse",
    "ShiftProduction",
    "ProductionByShiftPoint",
    "ProductionByShiftResponse",
    "OrderFulfillmentPoint",
    "OrderFulfillmentResponse",
    "MachineRankingItem",
    "MachineRankingResponse",
    "AlertItem",
    "AlertsResponse",
    "ScrapByMachineDayPoint",
    "ScrapByMachineResponse",
    "ScrapMachineTotal",
    "WIPMachineSlot",
    "WIPResponse",
    "YieldByMachineItem",
    "YieldByOperationResponse",
]
