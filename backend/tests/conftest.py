"""
Configuración compartida de Pytest para los tests del backend.

Estrategia de aislamiento:
- Cada test corre dentro de una transacción que se hace ROLLBACK al final,
  de modo que las mutaciones (creación de eventos, edición de máquinas, etc.)
  no contaminan la BD compartida con desarrollo.
- La dependencia `get_db` de FastAPI se sobreescribe para que los endpoints
  usen la misma sesión transaccional que el test.
- El TestClient ataca directamente a la app FastAPI sin pasar por Nginx,
  así que las URL son /api/auth/login, /api/machines, etc.

Requisitos:
- La BD debe estar migrada y con datos de seed previos a correr los tests
  (los tests asumen la presencia de los usuarios y catálogos del seed).
"""

from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.database import engine, get_db
from app.main import app
from app.services.auth_service import authenticate_user, create_access_token


@pytest.fixture
def db_session() -> Iterator[Session]:
    """
    Sesión de BD aislada por test mediante transacción + rollback.

    Inicia una conexión y una transacción reales contra PostgreSQL, ata una
    Session a esa conexión y hace ROLLBACK al terminar. Cualquier mutación
    realizada por el test desaparece después.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection, expire_on_commit=False)
    session = session_factory()

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    """TestClient con `get_db` sobreescrito para usar la sesión aislada."""

    def _override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


# -----------------------------------------------------------------------------
# Helpers de autenticación reutilizables
# -----------------------------------------------------------------------------
def _token_for(db_session: Session, username: str, password: str = "smartsack123") -> str:
    """Genera un JWT válido para `username` usando el flujo de auth real."""
    user = authenticate_user(db_session, username, password)
    assert user is not None, f"Usuario semilla '{username}' no autenticó (seed pendiente)"
    return create_access_token(
        subject=user.username,
        role=user.role.value,
        user_id=user.id,
        machine_id=user.machine_id,
    )


@pytest.fixture
def admin_token(db_session: Session) -> str:
    return _token_for(db_session, "admin")


@pytest.fixture
def supervisor_token(db_session: Session) -> str:
    return _token_for(db_session, "supervisor1")


@pytest.fixture
def operator_token(db_session: Session) -> str:
    """Operario asignado a la máquina TUB-01 (ver scripts/seed.py)."""
    return _token_for(db_session, "op_tub-01_1")


def auth_header(token: str) -> dict:
    """Header Authorization listo para inyectar en client.get/post/etc."""
    return {"Authorization": f"Bearer {token}"}


# Catálogo de máquinas creado por scripts/seed.py:MACHINES_CATALOG.
# Los tests verifican que estas 8 estén presentes pero no que sean las
# únicas — la BD puede contener máquinas extra añadidas en runtime vía
# /api/machines (admin) sin que eso invalide el resto del sistema.
SEED_MACHINE_CODES = frozenset(
    {
        "TUB-01", "TUB-02",
        "IMP-01", "IMP-02",
        "FON-01", "FON-02",
        "EMP-01", "EMP-02",
    }
)
