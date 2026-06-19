"""
Router de autenticación.

Expone:
- POST /auth/login : intercambia username + password por un JWT.
- GET  /auth/me    : devuelve el usuario asociado al JWT.

El endpoint de login acepta el formulario OAuth2PasswordRequestForm
estándar (compatible con el botón "Authorize" de Swagger UI). Para clientes
SPA es indistinto: Axios envía `application/x-www-form-urlencoded`
con campos `username` y `password`.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.middleware.auth import get_current_active_user
from app.models import User
from app.schemas import CurrentUserResponse, TokenResponse
from app.services import auth_service


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Iniciar sesión y obtener un JWT",
)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Autentica un usuario y devuelve un access token de tipo Bearer."""
    user = auth_service.authenticate_user(db, form_data.username, form_data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_service.create_access_token(
        subject=user.username,
        role=user.role.value,
        user_id=user.id,
        machine_id=user.machine_id,
    )
    return TokenResponse(
        access_token=token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    summary="Obtener el usuario asociado al token actual",
)
def get_me(user: User = Depends(get_current_active_user)) -> User:
    """Útil para que el frontend cachee la info del usuario tras el login."""
    return user
