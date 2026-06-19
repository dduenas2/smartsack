"""
Dependencias de autenticación y autorización para FastAPI.

- `oauth2_scheme`         : extrae el token Bearer del header Authorization.
- `get_current_user`      : decodifica el JWT, recarga el usuario desde la BD.
- `get_current_active_user`: además exige que el usuario esté activo.
- `require_roles(*roles)` : factoría que devuelve una dependencia que valida
                            que el usuario tenga uno de los roles permitidos.

Uso típico en routers:

    @router.get("/admin/area")
    def admin_area(user: User = Depends(require_roles(UserRole.ADMIN))):
        ...
"""

from typing import Iterable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole
from app.services import auth_service


# tokenUrl apunta al endpoint público de login. Swagger UI usa esta ruta para
# emular el flujo OAuth2 password y permitir "Authorize" desde /docs.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# Mensaje y status comunes para credenciales inválidas o ausentes.
_credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Credenciales inválidas o token expirado",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    """Decodifica el JWT y devuelve el usuario al que pertenece."""
    try:
        payload = auth_service.decode_access_token(token)
    except jwt.PyJWTError as exc:
        raise _credentials_exception from exc

    username: str | None = payload.get("sub")
    if not username:
        raise _credentials_exception

    user = auth_service.get_user_by_username(db, username)
    if user is None:
        raise _credentials_exception

    return user


def get_current_active_user(
    user: User = Depends(get_current_user),
) -> User:
    """Garantiza que el usuario autenticado esté activo (no deshabilitado)."""
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inactivo",
        )
    return user


def require_roles(*allowed_roles: UserRole):
    """
    Factoría de dependencia: restringe el endpoint a uno o varios roles.

    Ejemplo:
        Depends(require_roles(UserRole.ADMIN))
        Depends(require_roles(UserRole.ADMIN, UserRole.SUPERVISOR))
    """
    allowed: Iterable[UserRole] = allowed_roles

    def _checker(user: User = Depends(get_current_active_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Requiere rol {[r.value for r in allowed]}; "
                    f"el usuario tiene rol '{user.role.value}'"
                ),
            )
        return user

    return _checker
