"""
Router /api/etl — carga de CSVs desde el ERP y consulta del historial.

Endpoints:
- POST /upload                    : sube un CSV (multipart). Roles: admin, supervisor.
- GET  /status                    : historial paginado de cargas. Auth requerida.
- GET  /status/{load_id}          : detalle de una carga (incluye error_log).
- GET  /sample-csv/{kind}         : descarga una plantilla CSV de cabecera vacía.

El upload es síncrono: el supervisor recibe el resumen al terminar.
Para archivos muy grandes, en una versión futura se podría hacer asíncrono
con un job de Celery + WebSocket, pero para el alcance de la tesis basta.
"""

from io import StringIO
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_active_user, require_roles
from app.models import ETLLoad, ETLLoadKind, User, UserRole
from app.schemas import ETLLoadListResponse, ETLLoadResponse
from app.services import etl_service
from app.services.etl_service import REQUIRED_COLUMNS


router = APIRouter(prefix="/etl", tags=["etl"])

# Límite por archivo: 10 MB. Los CSVs reales de SAP rara vez superan esto;
# si el límite se alcanza es señal de que conviene cargar incrementalmente.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


# Cabeceras adicionales que sugerimos en las plantillas (no obligatorias).
SUGGESTED_COLUMNS = {
    ETLLoadKind.PRODUCTION_ORDERS: ["order_number", "product_type", "product_description",
                                    "quantity_ordered", "machine_code", "planned_start",
                                    "planned_end", "priority"],
    ETLLoadKind.CONFIRMATIONS:     ["order_number", "machine_code", "quantity_produced",
                                    "actual_start", "actual_end", "scrap_kg", "scrap_reason"],
    ETLLoadKind.MATERIALS:         ["order_number", "material_code", "material_name",
                                    "unit", "quantity_planned", "quantity_used"],
    ETLLoadKind.SHIPMENTS:         ["order_number", "shipped_at", "destination",
                                    "quantity_shipped", "carrier"],
}


# -----------------------------------------------------------------------------
# /upload
# -----------------------------------------------------------------------------
@router.post(
    "/upload",
    response_model=ETLLoadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Subir un CSV de SAP para procesar (admin o supervisor)",
)
async def upload_csv(
    kind: ETLLoadKind = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPERVISOR)),
) -> ETLLoad:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo debe tener extensión .csv",
        )

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Archivo vacío"
        )
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Archivo > {MAX_UPLOAD_BYTES // (1024 * 1024)} MB",
        )

    return etl_service.process_upload(
        db,
        content=content,
        filename=file.filename,
        kind=kind,
        uploaded_by_id=user.id,
    )


# -----------------------------------------------------------------------------
# /status
# -----------------------------------------------------------------------------
@router.get(
    "/status",
    response_model=ETLLoadListResponse,
    summary="Historial paginado de cargas ETL",
)
def list_loads(
    kind: Optional[ETLLoadKind] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_active_user),
) -> ETLLoadListResponse:
    base = select(ETLLoad)
    if kind is not None:
        base = base.where(ETLLoad.kind == kind)

    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    items = list(
        db.scalars(
            base.order_by(ETLLoad.uploaded_at.desc()).offset(offset).limit(limit)
        )
    )
    return ETLLoadListResponse(
        total=int(total),
        limit=limit,
        offset=offset,
        items=[ETLLoadResponse.model_validate(it) for it in items],
    )


@router.get(
    "/status/{load_id}",
    response_model=ETLLoadResponse,
    summary="Detalle de una carga ETL (incluye error_log)",
)
def get_load(
    load_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_active_user),
) -> ETLLoad:
    load = db.get(ETLLoad, load_id)
    if load is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Carga no encontrada")
    return load


# -----------------------------------------------------------------------------
# /sample-csv/{kind}
# -----------------------------------------------------------------------------
@router.get(
    "/sample-csv/{kind}",
    summary="Descarga una plantilla CSV (cabecera vacía) para ese tipo",
)
def download_sample_csv(
    kind: ETLLoadKind,
    _user: User = Depends(get_current_active_user),
):
    columns = SUGGESTED_COLUMNS[kind]
    buf = StringIO()
    buf.write(",".join(columns))
    buf.write("\n")
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{kind.value}_template.csv"',
        },
    )
