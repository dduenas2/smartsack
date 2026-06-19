"""
Router /api/users — gestión de usuarios (admin-only).

Endpoints:
  · GET    /api/users                       Lista paginada con filtros.
  · GET    /api/users/{id}                  Detalle de un usuario.
  · POST   /api/users                       Crea un usuario.
  · PATCH  /api/users/{id}                  Actualiza campos parciales.
  · DELETE /api/users/{id}                  Soft-delete (is_active=false).
  · POST   /api/users/{id}/reset-password   Forzar nueva contraseña.
  · POST   /api/users/{id}/assign-machine   Asignar/desasignar máquina.

Reglas de negocio:
  - Username único.
  - `machine_id` sólo aplica si `role == operario`. Para otros roles se
    fuerza a None.
  - No se permite que el admin se desactive a sí mismo (anti-lockout).
  - No se permite quedarse sin admins activos (al menos 1 siempre).
  - Toda mutación queda registrada en `admin_audit_log` por audit_service.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import require_roles
from app.models import Machine, User, UserRole
from app.schemas import (
    PaginatedResponse,
    UserAssignMachine,
    UserCreate,
    UserPasswordReset,
    UserResponse,
    UserUpdate,
)
from app.services import audit_service, auth_service


router = APIRouter(prefix="/users", tags=["users"])


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _get_or_404(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado"
        )
    return user


def _ensure_machine_exists(db: Session, machine_id: int) -> Machine:
    machine = db.get(Machine, machine_id)
    if machine is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"machine_id={machine_id} no existe",
        )
    return machine


def _validate_role_machine(role: UserRole, machine_id: Optional[int]) -> Optional[int]:
    """Sólo operarios llevan machine_id; el resto siempre None."""
    if role == UserRole.OPERATOR:
        return machine_id
    return None


def _count_active_admins(db: Session, *, exclude_id: Optional[int] = None) -> int:
    stmt = select(func.count()).select_from(User).where(
        User.role == UserRole.ADMIN,
        User.is_active.is_(True),
    )
    if exclude_id is not None:
        stmt = stmt.where(User.id != exclude_id)
    return int(db.scalar(stmt) or 0)


def _ensure_not_last_admin(
    db: Session, target: User, *, will_be_inactive: bool = False, will_change_role: bool = False
) -> None:
    """Bloquea operaciones que dejarían el sistema sin admins activos."""
    if target.role != UserRole.ADMIN or not target.is_active:
        return
    if not (will_be_inactive or will_change_role):
        return
    remaining = _count_active_admins(db, exclude_id=target.id)
    if remaining == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede dejar el sistema sin administradores activos",
        )


# -----------------------------------------------------------------------------
# Listado / detalle
# -----------------------------------------------------------------------------
@router.get(
    "",
    response_model=PaginatedResponse[UserResponse],
    summary="Listar usuarios (admin)",
)
def list_users(
    role: Optional[UserRole] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    search: Optional[str] = Query(default=None, description="Búsqueda por username/full_name"),
    machine_id: Optional[int] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_roles(UserRole.ADMIN)),
) -> PaginatedResponse[UserResponse]:
    base = select(User)
    if role is not None:
        base = base.where(User.role == role)
    if is_active is not None:
        base = base.where(User.is_active.is_(is_active))
    if machine_id is not None:
        base = base.where(User.machine_id == machine_id)
    if search:
        like = f"%{search.lower()}%"
        base = base.where(
            func.lower(User.username).like(like)
            | func.lower(func.coalesce(User.full_name, "")).like(like)
        )

    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    items = list(
        db.scalars(
            base.order_by(User.username).offset(offset).limit(limit)
        )
    )
    return PaginatedResponse[UserResponse](
        total=int(total),
        limit=limit,
        offset=offset,
        items=[UserResponse.model_validate(u) for u in items],
    )


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Detalle de un usuario (admin)",
)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_roles(UserRole.ADMIN)),
) -> User:
    return _get_or_404(db, user_id)


# -----------------------------------------------------------------------------
# Mutaciones
# -----------------------------------------------------------------------------
@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear usuario (admin)",
)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.ADMIN)),
) -> User:
    if db.scalar(select(User).where(User.username == payload.username)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe un usuario con username '{payload.username}'",
        )

    machine_id = _validate_role_machine(payload.role, payload.machine_id)
    if machine_id is not None:
        _ensure_machine_exists(db, machine_id)

    user = User(
        username=payload.username,
        full_name=payload.full_name,
        password_hash=auth_service.hash_password(payload.password),
        role=payload.role,
        machine_id=machine_id,
        is_active=True,
    )
    db.add(user)
    db.flush()  # popula id antes de loggear
    audit_service.log_admin_action(
        db,
        actor=admin,
        action="create",
        entity_type="user",
        entity_id=user.id,
        after=audit_service.serialize_user(user),
    )
    db.commit()
    db.refresh(user)
    return user


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Actualizar usuario (admin)",
)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.ADMIN)),
) -> User:
    user = _get_or_404(db, user_id)
    before = audit_service.serialize_user(user)
    data = payload.model_dump(exclude_unset=True)

    # Anti-lockout: el admin no puede desactivarse a sí mismo, ni cambiarse de rol.
    if user.id == admin.id:
        if data.get("is_active") is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No puedes desactivar tu propia cuenta",
            )
        if "role" in data and data["role"] != user.role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No puedes cambiar tu propio rol",
            )

    new_is_active = data.get("is_active", user.is_active)
    new_role = data.get("role", user.role)
    _ensure_not_last_admin(
        db,
        user,
        will_be_inactive=new_is_active is False,
        will_change_role=new_role != user.role,
    )

    if "full_name" in data:
        user.full_name = data["full_name"]
    if "is_active" in data:
        user.is_active = bool(data["is_active"])
    if "role" in data:
        user.role = data["role"]
        # Cambiar de rol limpia la máquina si ya no aplica.
        if user.role != UserRole.OPERATOR:
            user.machine_id = None
    if "machine_id" in data:
        if user.role != UserRole.OPERATOR and data["machine_id"] is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="machine_id sólo aplica para operarios",
            )
        if data["machine_id"] is not None:
            _ensure_machine_exists(db, data["machine_id"])
        user.machine_id = data["machine_id"]

    audit_service.log_admin_action(
        db,
        actor=admin,
        action="update",
        entity_type="user",
        entity_id=user.id,
        before=before,
        after=audit_service.serialize_user(user),
    )
    db.commit()
    db.refresh(user)
    return user


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desactivar usuario (admin) — soft delete via is_active=false",
)
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.ADMIN)),
) -> Response:
    user = _get_or_404(db, user_id)
    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes desactivar tu propia cuenta",
        )
    _ensure_not_last_admin(db, user, will_be_inactive=True)

    before = audit_service.serialize_user(user)
    user.is_active = False
    audit_service.log_admin_action(
        db,
        actor=admin,
        action="deactivate",
        entity_type="user",
        entity_id=user.id,
        before=before,
        after=audit_service.serialize_user(user),
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{user_id}/reset-password",
    response_model=UserResponse,
    summary="Forzar nueva contraseña a un usuario (admin)",
)
def reset_password(
    user_id: int,
    payload: UserPasswordReset,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.ADMIN)),
) -> User:
    user = _get_or_404(db, user_id)
    user.password_hash = auth_service.hash_password(payload.new_password)
    audit_service.log_admin_action(
        db,
        actor=admin,
        action="reset_password",
        entity_type="user",
        entity_id=user.id,
        after={"id": user.id, "username": user.username},
    )
    db.commit()
    db.refresh(user)
    return user


@router.post(
    "/{user_id}/assign-machine",
    response_model=UserResponse,
    summary="Asignar/desasignar la máquina de un operario (admin)",
)
def assign_machine(
    user_id: int,
    payload: UserAssignMachine,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.ADMIN)),
) -> User:
    user = _get_or_404(db, user_id)
    if user.role != UserRole.OPERATOR:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sólo los operarios tienen máquina asignada",
        )
    if payload.machine_id is not None:
        _ensure_machine_exists(db, payload.machine_id)

    before = audit_service.serialize_user(user)
    user.machine_id = payload.machine_id
    audit_service.log_admin_action(
        db,
        actor=admin,
        action="assign_machine",
        entity_type="user",
        entity_id=user.id,
        before=before,
        after=audit_service.serialize_user(user),
    )
    db.commit()
    db.refresh(user)
    return user
