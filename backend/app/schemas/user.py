"""
Schemas Pydantic para la entidad User.

Por ahora se usan principalmente para responder /auth/me y para listar
usuarios desde el panel admin. La creación/edición masiva de usuarios se
modelará en pasos posteriores.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models import UserRole
from app.schemas.common import ORMConfig


class UserResponse(BaseModel):
    model_config = ORMConfig

    id: int
    username: str
    full_name: Optional[str] = None
    role: UserRole
    machine_id: Optional[int] = None
    is_active: bool
    created_at: datetime


class UserCreate(BaseModel):
    """Payload usado por el admin para crear un nuevo usuario."""

    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: Optional[str] = Field(default=None, max_length=128)
    role: UserRole
    machine_id: Optional[int] = None


class UserUpdate(BaseModel):
    """
    Patch parcial de un usuario.

    Campos opcionales: solo se modifican los que vengan en el payload.
    Validamos longitudes en el modelo y reglas de negocio (machine_id sólo
    para operarios) en el router para devolver mensajes claros.
    """

    full_name: Optional[str] = Field(default=None, max_length=128)
    role: Optional[UserRole] = None
    machine_id: Optional[int] = None
    is_active: Optional[bool] = None


class UserPasswordReset(BaseModel):
    """Payload del admin para forzar una nueva contraseña a un usuario."""

    new_password: str = Field(..., min_length=8, max_length=128)


class UserAssignMachine(BaseModel):
    """Asignar (o desasignar con None) la máquina de un operario."""

    machine_id: Optional[int] = None
