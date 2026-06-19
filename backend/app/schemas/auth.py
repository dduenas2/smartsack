"""
Schemas de autenticación.

Define los payloads de request y response del flujo de login y la forma
del usuario autenticado expuesta al frontend. La contraseña se transporta
únicamente en el request de login y NUNCA se devuelve en respuestas.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models import UserRole
from app.schemas.common import ORMConfig


class LoginRequest(BaseModel):
    """Body alternativo en JSON para POST /auth/login (útil desde el frontend)."""

    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class TokenResponse(BaseModel):
    """JWT devuelto tras un login exitoso."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Vigencia del token en segundos")


class CurrentUserResponse(BaseModel):
    """Forma simplificada del usuario que el frontend cachea tras /auth/me."""

    model_config = ORMConfig

    id: int
    username: str
    full_name: Optional[str] = None
    role: UserRole
    machine_id: Optional[int] = None
    is_active: bool
    created_at: datetime
