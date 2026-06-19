"""
Servicio de autenticación de SmartSack.

Centraliza:
- Hashing y verificación de contraseñas con bcrypt (passlib).
- Emisión y decodificación de JSON Web Tokens (PyJWT).
- Búsqueda y autenticación de usuarios contra la base de datos.

Las contraseñas NUNCA se almacenan en texto plano: siempre se persiste el
hash. La clave secreta del JWT se lee de la configuración (.env).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import User


# CryptContext único para todo el backend; bcrypt es el algoritmo en uso.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# -----------------------------------------------------------------------------
# Contraseñas
# -----------------------------------------------------------------------------
def hash_password(plain_password: str) -> str:
    """Devuelve el hash bcrypt de una contraseña en texto plano."""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica que una contraseña en texto plano corresponda a su hash."""
    return pwd_context.verify(plain_password, hashed_password)


# -----------------------------------------------------------------------------
# Usuarios
# -----------------------------------------------------------------------------
def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """Busca un usuario por su `username` exacto."""
    return db.scalar(select(User).where(User.username == username))


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """
    Autentica un usuario por username + contraseña.

    Devuelve el modelo User si las credenciales son válidas y el usuario está
    activo; en caso contrario devuelve None. No lanza excepciones por
    credenciales inválidas: deja al router decidir qué HTTP status emitir.
    """
    user = get_user_by_username(db, username)
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


# -----------------------------------------------------------------------------
# JWT
# -----------------------------------------------------------------------------
def create_access_token(
    *,
    subject: str,
    role: str,
    user_id: int,
    machine_id: Optional[int] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Crea un JWT firmado con la clave del backend.

    Claims incluidos:
    - sub: nombre de usuario (estándar del estándar OAuth2)
    - uid: id numérico del usuario en la BD
    - role: rol (operario/supervisor/admin)
    - machine_id: máquina asignada al operario (si aplica)
    - iat: instante de emisión (UTC)
    - exp: instante de expiración (UTC)
    """
    now = datetime.now(tz=timezone.utc)
    expire = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )

    payload: Dict[str, Any] = {
        "sub": subject,
        "uid": user_id,
        "role": role,
        "machine_id": machine_id,
        "iat": now,
        "exp": expire,
    }

    return jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decodifica y valida un JWT.

    Lanza `jwt.PyJWTError` (incluye expirados, firma inválida, etc.) si el
    token no es válido. Es responsabilidad del caller mapear esa excepción
    a un HTTP 401.
    """
    return jwt.decode(
        token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
    )
