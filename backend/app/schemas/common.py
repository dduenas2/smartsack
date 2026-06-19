"""
Esquemas Pydantic compartidos por todos los recursos.

Incluye un envoltorio estándar de paginación y un alias de ConfigDict para
modelos que se construyen desde objetos ORM (`from_attributes=True`).
"""

from typing import Generic, List, TypeVar

from pydantic import BaseModel, ConfigDict


# Configuración común para schemas que reciben instancias de SQLAlchemy.
ORMConfig = ConfigDict(from_attributes=True)


T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Respuesta estándar para endpoints paginados."""

    total: int
    limit: int
    offset: int
    items: List[T]
