"""
Punto de entrada de la aplicación FastAPI de SmartSack.

Crea la instancia `app`, configura CORS, registra los routers de la API y
expone endpoints de salud (`/`, `/health`) para verificar que el backend
está operativo. Al avanzar en los siguientes pasos del proyecto se irán
montando aquí los routers de auth, máquinas, órdenes, dashboard, etc.
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import admin as admin_router
from app.routers import auth as auth_router
from app.routers import chat as chat_router
from app.routers import dashboard as dashboard_router
from app.routers import etl as etl_router
from app.routers import events as events_router
from app.routers import machines as machines_router
from app.routers import operations as operations_router
from app.routers import orders as orders_router
from app.routers import predictions as predictions_router
from app.routers import users as users_router
from app.routers import websocket as ws_router


# -----------------------------------------------------------------------------
# Configuración de logging
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("smartsack")


# -----------------------------------------------------------------------------
# Lifespan: hooks de arranque y apagado
# -----------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Reemplaza @app.on_event(startup|shutdown) (deprecado en FastAPI 0.110+)."""
    logger.info(
        "Iniciando %s en entorno '%s'", settings.project_name, settings.environment
    )
    yield
    logger.info("Apagando %s", settings.project_name)


# -----------------------------------------------------------------------------
# Instancia de la aplicación FastAPI
# -----------------------------------------------------------------------------
app = FastAPI(
    title=settings.project_name,
    version="0.1.0",
    description=(
        "API del sistema SmartSack: Digital Twin de planta de sacos de papel, "
        "motor de ML predictivo de retrasos y chatbot conversacional con IA."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


# -----------------------------------------------------------------------------
# Middleware: CORS
# -----------------------------------------------------------------------------
# Permite que el frontend (servido en otro origen durante desarrollo) consuma
# la API. En producción se restringe a los dominios reales del despliegue.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------------------------------------------------------
# Endpoints básicos
# -----------------------------------------------------------------------------
@app.get("/", tags=["meta"], summary="Información raíz de la API")
async def root() -> dict:
    """Devuelve información mínima de la API y enlaces útiles."""
    return {
        "name": settings.project_name,
        "version": "0.1.0",
        "environment": settings.environment,
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", tags=["meta"], summary="Health check del servicio")
async def health_check() -> dict:
    """
    Endpoint de salud usado por Docker, Nginx y monitoreo.

    Devuelve un payload simple con el estado y la hora actual en UTC.
    En pasos posteriores se ampliará para verificar conexión a PostgreSQL
    y Redis antes de reportar 'ok'.
    """
    return {
        "status": "ok",
        "service": settings.project_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# -----------------------------------------------------------------------------
# Registro de routers
# -----------------------------------------------------------------------------
# Todos los recursos REST viven bajo /api/* cuando se accede a través del
# reverse proxy de Nginx (ver nginx/nginx.conf). Internamente FastAPI los
# expone con el mismo prefijo para que la documentación coincida.
api_router = APIRouter(prefix="/api")


@api_router.get("/health", tags=["meta"], summary="Health check (alias bajo /api)")
async def api_health_check() -> dict:
    """Mismo payload que /health, accesible bajo el prefijo /api del proxy."""
    return await health_check()


api_router.include_router(auth_router.router)
api_router.include_router(machines_router.router)
api_router.include_router(orders_router.router)
api_router.include_router(operations_router.router)
api_router.include_router(operations_router.trace_router)
api_router.include_router(events_router.router)
api_router.include_router(dashboard_router.router)
api_router.include_router(etl_router.router)
api_router.include_router(predictions_router.router)
api_router.include_router(chat_router.router)
api_router.include_router(users_router.router)
api_router.include_router(admin_router.router)
app.include_router(api_router)

# WebSocket del Digital Twin: queda en la raíz para que Nginx lo enrute por
# /ws/* sin el prefijo de la API REST.
app.include_router(ws_router.router)
